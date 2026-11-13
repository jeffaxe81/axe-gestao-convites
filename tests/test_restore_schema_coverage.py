"""Prevent restore checks from silently omitting invitation tables."""
from io import BytesIO
import hashlib

import pytest

from app.models import Base
from scripts import backup_mysql


def test_every_database_table_is_covered_by_restore_validation():
    expected = set(Base.metadata.tables) | {"schema_migrations"}
    assert set(backup_mysql.DATA_COLUMNS) == expected
    assert len(expected) == 9


def test_all_persisted_model_columns_are_compared():
    for name, table in Base.metadata.tables.items():
        configured = {
            value.strip() for value in backup_mysql.DATA_COLUMNS[name].split(",")
        }
        assert configured == {column.name for column in table.columns}, name
        order_key = backup_mysql.ORDER_COLUMNS.get(name, "id")
        assert order_key in configured, name
        assert order_key in {column.name for column in table.primary_key.columns}, name
    assert backup_mysql.DATA_COLUMNS["schema_migrations"] == "version"
    assert backup_mysql.ORDER_COLUMNS["schema_migrations"] == "version"


class FakeQuery:
    def __init__(self, output=b"synthetic-row"):
        self.stdout = BytesIO(output)
    def wait(self):
        return 0


@pytest.mark.parametrize("table,sort_column", [
    ("families", "id"),
    ("invitation_responses", "invited_family_id"),
    ("invitation_dispatches", "invited_family_id"),
    ("invitation_interests", "invited_family_id"),
    ("schema_migrations", "version"),
])
def test_query_orders_by_each_table_primary_key(monkeypatch, table, sort_column):
    calls = []
    def fake_popen(command, **kwargs):
        calls.append(command)
        return FakeQuery()
    monkeypatch.setattr(backup_mysql.subprocess, "Popen", fake_popen)
    digest, length = backup_mysql.query_digest(
        "isadora_test", table, backup_mysql.DATA_COLUMNS[table]
    )
    assert len(calls) == 1
    assert "ORDER BY {};" .format(sort_column) in calls[0][-1]
    assert digest == hashlib.sha256(b"synthetic-row").hexdigest()
    assert length == len(b"synthetic-row")


def test_critical_invitation_fields_are_compared():
    for table, field in (
        ("invited_families", "phone"),
        ("invited_families", "status"),
        ("invitation_responses", "family_id"),
        ("invitation_dispatches", "marked_at_utc"),
        ("invitation_interests", "expressed_at_utc"),
    ):
        assert field in backup_mysql.DATA_COLUMNS[table].split(", ") or (
            field in backup_mysql.DATA_COLUMNS[table].replace(" ", "").split(",")
        )
