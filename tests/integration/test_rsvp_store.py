"""SQLite regression checks: MySQL end-to-end is a separate CI requirement."""
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.domain import validate_rsvp, Counts
from app.models import Base, EventSettings
from app.rsvp import RsvpStore, RevisionConflict, IdempotencyConflict, AccessDenied, EditClosed

NOW = datetime(2026, 10, 18, 21, tzinfo=timezone.utc)
TOKEN_SECRET = 'test-secret-not-for-production'

def payload(name='Ana', attending=True, ages=(5, 6)):
    people = [{'name': name, 'kind': 'OVER_12', 'age_years': None}]
    people += [{'name': f'Criança {i}', 'kind': 'CHILD', 'age_years': a} for i, a in enumerate(ages)]
    return validate_rsvp({'contact_name': name, 'attending': attending,
                          'participants': people if attending else []})

@pytest.fixture
def store():
    engine = create_engine('sqlite+pysqlite:///:memory:',
                           connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(engine, expire_on_commit=False)
    with session_factory.begin() as session:
        session.add(EventSettings(id=1, buffet_limit=40))
    yield RsvpStore(session_factory, TOKEN_SECRET)
    engine.dispose()

def test_create_and_retry_recover_one_response(store):
    initial = store.create(payload(), 'random-key-unique-0001', NOW)
    again = store.create(payload(), 'random-key-unique-0001', NOW)
    assert initial == again
    assert store.summary()['counts'] == Counts(3, 2, 1, 2, 1)
    assert len(store.summary()['confirmed']) == 1

def test_same_key_different_content_conflicts(store):
    store.create(payload(), 'random-key-unique-0002', NOW)
    with pytest.raises(IdempotencyConflict):
        store.create(payload('Beatriz'), 'random-key-unique-0002', NOW)

def test_stale_revision_cannot_overwrite(store):
    receipt = store.create(payload(), 'random-key-unique-0003', NOW)
    changed = store.update(receipt.id, receipt.edit_token, 1, payload('Ana', ages=(12,)), NOW)
    assert changed.revision == 2
    with pytest.raises(RevisionConflict):
        store.update(receipt.id, receipt.edit_token, 1, payload('Ana', ages=(0,)), NOW)
    assert store.summary()['counts'] == Counts(2, 2, 0, 1, 1)

def test_switch_to_declined_removes_all_participants(store):
    receipt = store.create(payload(), 'random-key-unique-0004', NOW)
    store.update(receipt.id, receipt.edit_token, 1, payload('Ana', False), NOW)
    summary = store.summary()
    assert summary['counts'] == Counts(0, 0, 0, 0, 0)
    assert len(summary['declined']) == 1
    assert summary['declined'][0]['participants'] == []

def test_access_token_cannot_access_other_family(store):
    a = store.create(payload(), 'random-key-unique-0005', NOW)
    b = store.create(payload('Beatriz'), 'random-key-unique-0006', NOW)
    with pytest.raises(AccessDenied):
        store.get_own(b.id, a.edit_token)
    assert store.get_own(a.id, a.edit_token)['revision'] == 1

def test_closed_edit_deadline(store):
    r = store.create(payload(), 'random-key-unique-0007', NOW)
    store.configure(venue='Salão', deadline_utc=NOW, now_utc=NOW)
    with pytest.raises(EditClosed):
        store.update(r.id, r.edit_token, 1, payload(), NOW)
    assert store.get_own(r.id, r.edit_token)['venue'] == 'Salão'

def test_update_is_atomic_on_invalid_child(store):
    r = store.create(payload(), 'random-key-unique-0008', NOW)
    engine = store.session_factory.kw['bind']
    def fail_insert(conn, cursor, statement, parameters, context, executemany):
        if statement.lower().lstrip().startswith('insert into participants'):
            raise RuntimeError('simulated database error')
    event.listen(engine, 'before_cursor_execute', fail_insert)
    try:
        with pytest.raises(RuntimeError, match='simulated database error'):
            store.update(r.id, r.edit_token, 1, payload('Ana', ages=(1, 2, 3)), NOW)
    finally:
        event.remove(engine, 'before_cursor_execute', fail_insert)
    own = store.get_own(r.id, r.edit_token)
    assert own['revision'] == 1
    assert len(own['participants']) == 3

def test_homonyms_and_accents_survive(store):
    r = store.create(validate_rsvp({'contact_name': "João D'Ávila", 'attending': True,
      'participants': [{'name': "João D'Ávila", 'kind': 'OVER_12'},
                       {'name': "João D'Ávila", 'kind': 'OVER_12'}]}), 'random-key-unique-0009', NOW)
    assert [p['name'] for p in store.get_own(r.id, r.edit_token)['participants']] == ["João D'Ávila"] * 2

def test_40_limit_is_alert_not_rejection(store):
    for i in range(41):
        store.create(payload(f'Adulto {i}', ages=()), f'random-key-40-{i:04d}', NOW)
    report = store.summary()
    assert report['counts'].buffet == 41
    assert report['buffet_limit_reached'] is True

def test_zero_deadline_can_be_removed(store):
    r = store.create(payload(), 'random-key-unique-0010', NOW)
    store.configure(venue=None, deadline_utc=NOW, now_utc=NOW)
    store.configure(venue=None, deadline_utc=None, now_utc=NOW)
    assert store.update(r.id, r.edit_token, 1, payload(), NOW).revision == 2
