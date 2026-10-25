"""Concurrency tests run only against dedicated *_test MySQL database."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from threading import Barrier, Event

import pytest
from sqlalchemy import create_engine, text, select, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.db import migrate
from app.domain import Counts, validate_rsvp
from app.models import Base, EventSettings
from app.rsvp import RsvpStore, RevisionConflict
from app import create_app


def party(name):
    return validate_rsvp({
        "contact_name": name,
        "attending": True,
        "participants": [
            {"name": name, "kind": "OVER_12", "age_years": None},
            {"name": name + " criança 5", "kind": "CHILD", "age_years": 5},
            {"name": name + " criança 6", "kind": "CHILD", "age_years": 6},
            {"name": name + " criança 12", "kind": "CHILD", "age_years": 12},
        ],
    })


@pytest.fixture
def mysql_store():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Somente no banco MySQL de teste.")
    if not make_url(url).database.endswith("_test"):
        pytest.fail("TEST_DATABASE_URL deve apontar para banco descartável *_test.")
    engine = create_engine(url, pool_pre_ping=True, pool_size=24, max_overflow=6)
    try:
        Base.metadata.drop_all(engine)
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS schema_migrations"))
        migrate(engine)
        yield RsvpStore(
            sessionmaker(engine, expire_on_commit=False),
            "mysql-concurrency-test-only-secret-12345678",
        )
    finally:
        engine.dispose()


def test_concurrent_same_idempotency_key_creates_one_family(mysql_store):
    now = datetime.now(timezone.utc)
    data = party("Maria")
    key = "concurrent-shared-key-0001"

    def send(_):
        return mysql_store.create(data, key, now)

    with ThreadPoolExecutor(max_workers=20) as executor:
        receipts = list(executor.map(send, range(20)))

    assert len({receipt.id for receipt in receipts}) == 1
    assert len({receipt.edit_token for receipt in receipts}) == 1
    assert len(mysql_store.summary()["confirmed"]) == 1
    assert mysql_store.summary()["counts"] == Counts(4, 3, 1, 3, 1)


def test_parallel_distinct_families_preserve_exact_totals(mysql_store):
    now = datetime.now(timezone.utc)

    def send(index):
        return mysql_store.create(party("Família " + str(index)),
                                  "concurrent-family-" + str(index).zfill(6), now)

    with ThreadPoolExecutor(max_workers=20) as executor:
        receipts = list(executor.map(send, range(20)))

    assert len({receipt.id for receipt in receipts}) == 20
    assert len(mysql_store.summary()["confirmed"]) == 20
    assert mysql_store.summary()["counts"] == Counts(80, 60, 20, 60, 20)
    assert mysql_store.summary()["buffet_limit_reached"] is True


def test_concurrent_family_edits_keep_only_one_revision(mysql_store):
    now = datetime.now(timezone.utc)
    receipt = mysql_store.create(party("Ana"), "concurrent-edit-family-01", now)
    start = Barrier(2)

    def edit(name):
        start.wait(timeout=10)
        try:
            return mysql_store.update(receipt.id, receipt.edit_token, 1, party(name), now)
        except RevisionConflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(edit, ["Beatriz", "Carolina"]))
    winners = [result for result in results if result is not None]
    assert len(winners) == 1
    own = mysql_store.get_own(receipt.id, receipt.edit_token)
    assert own["revision"] == 2
    assert own["contact_name"] in {"Beatriz", "Carolina"}
    assert [person["name"] for person in own["participants"]] == [
        own["contact_name"], own["contact_name"] + " criança 5",
        own["contact_name"] + " criança 6", own["contact_name"] + " criança 12",
    ]
    assert mysql_store.summary()["counts"] == Counts(4, 3, 1, 3, 1)


@pytest.mark.parametrize("change_deadline", [False, True], ids=["clock-crosses-cutoff", "organizer-closes-editing"])
def test_queued_http_edit_checks_deadline_after_mysql_lock(mysql_store, monkeypatch, change_deadline):
    """A stale pre-lock clock/settings snapshot must never authorize an edit."""
    import app.public as public_module

    before = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
    deadline = before + timedelta(seconds=1)
    clock = [before]

    class ControlledDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0].astimezone(tz) if tz else clock[0].replace(tzinfo=None)

    monkeypatch.setattr(public_module, "datetime", ControlledDatetime)
    receipt = mysql_store.create(party("Ana"), "queued-deadline-family-01", before)
    mysql_store.configure(None, None if change_deadline else deadline, before)
    app = create_app({"TESTING": True, "RSVP_STORE": mysql_store, "API_RATE_LIMIT": 0})
    engine = mysql_store.session_factory.kw["bind"]
    waiting = Event()

    def lock_query_started(conn, cursor, statement, parameters, context, executemany):
        if "event_settings" in statement.lower() and "FOR UPDATE" in statement.upper():
            waiting.set()

    def request_edit():
        with app.test_client() as client:
            return client.put(
                "/api/rsvps/" + receipt.id,
                headers={"Authorization": "Bearer " + receipt.edit_token},
                json={"revision": 1, "contact_name": "Ana", "attending": False, "participants": []},
            )

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = None
        try:
            with mysql_store.session_factory.begin() as session:
                settings = session.scalar(select(EventSettings).where(EventSettings.id == 1).with_for_update())
                event.listen(engine, "before_cursor_execute", lock_query_started)
                future = executor.submit(request_edit)
                assert waiting.wait(timeout=10), "Edit did not reach the locked settings row"
                if change_deadline:
                    settings.edit_deadline_utc = before.replace(tzinfo=None)
                else:
                    clock[0] = deadline
            response = future.result(timeout=15)
        finally:
            event.remove(engine, "before_cursor_execute", lock_query_started)
    assert response.status_code == 403
    assert response.json["error"]["code"] == "EDIT_CLOSED"
    own = mysql_store.get_own(receipt.id, receipt.edit_token)
    assert own["revision"] == 1
    assert own["attending"] is True
    assert len(own["participants"]) == 4
    assert mysql_store.summary()["counts"] == Counts(4, 3, 1, 3, 1)
