"""Concurrency tests run only against dedicated *_test MySQL database."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.db import migrate
from app.domain import Counts, validate_rsvp
from app.models import Base
from app.rsvp import RsvpStore


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
