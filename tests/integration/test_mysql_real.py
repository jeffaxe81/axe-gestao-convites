"""Run only against a dedicated MySQL database named *_test."""
import os
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from app.db import migrate
from app.models import Base
from app.rsvp import RsvpStore
from tests.integration.test_rsvp_store import payload

@pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'), reason='MySQL dedicado ausente')
def test_mysql_transactions_and_idempotency():
    url = os.environ['TEST_DATABASE_URL']
    if not make_url(url).database.endswith('_test'):
        pytest.fail('TEST_DATABASE_URL deve apontar para banco com sufixo _test')
    engine = create_engine(url, pool_pre_ping=True)
    try:
        Base.metadata.drop_all(engine)
        with engine.begin() as conn:
            conn.execute(text('DROP TABLE IF EXISTS schema_migrations'))
        migrate(engine)
        store = RsvpStore(sessionmaker(engine, expire_on_commit=False), 'mysql-test-secret-for-ci-only')
        now = datetime(2026, 10, 18, tzinfo=timezone.utc)
        r1 = store.create(payload(), 'mysql-unique-key-00001', now)
        r2 = store.create(payload(), 'mysql-unique-key-00001', now)
        assert r1 == r2
        assert store.summary()['counts'].buffet == 2
        assert store.update(r1.id, r1.edit_token, 1, payload(ages=(0,)), now).revision == 2
        assert store.summary()['counts'].buffet == 1
        migrate(engine)
        assert store.get_own(r1.id, r1.edit_token)['revision'] == 2
    finally:
        engine.dispose()
