"""Histórico sem PII, migração aditiva e resumo quantitativo do buffet."""
import csv
from datetime import datetime, timezone
import io

from sqlalchemy import create_engine, select

from app.db import migrate
from app.models import AuditEvent, Base, EventSettings, Family, Participant
from tests.integration.test_organizer_api import client, login
from tests.integration.test_public_api import invitation, send, store


def _read_csv(blob):
    return list(csv.reader(io.StringIO(blob.decode("utf-8-sig")), delimiter=";"))


def test_activity_and_summary_requires_organizer_login(client):
    assert client.get("/api/admin/activity").status_code == 401
    assert client.get("/api/admin/planning.csv").status_code == 401


def test_new_and_duplicate_rsvp_activity_is_atomic_and_anonymous(client, store):
    first = send(client, invitation("Ana"), key="client-unique-key-isadora-0001")
    assert first.status_code == 201
    second = send(client, invitation("Ana"), key="client-unique-key-isadora-0001")
    assert second.status_code == 200
    assert send(client, invitation("Beatriz", attending=False)).status_code == 201

    edit = client.put("/api/rsvps/" + first.json["id"],
                      headers={"Authorization": "Bearer " + first.json["edit_token"]},
                      json={"revision": 1, **invitation("Ana", attending=False)})
    assert edit.status_code == 200
    store.configure("Salão Margaridas", None, datetime.now(timezone.utc))
    store.configure("Salão Margaridas", None, datetime.now(timezone.utc))
    # Attempts that do not commit changes must not create log rows.
    conflict = client.put("/api/rsvps/" + first.json["id"],
                          headers={"Authorization": "Bearer " + first.json["edit_token"]},
                          json={"revision": 1, **invitation("Ana")})
    assert conflict.status_code == 409

    assert login(client).status_code == 200
    response = client.get("/api/admin/activity")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    events = response.json["events"]
    assert [event["kind"] for event in events] == [
        "SETTINGS_CHANGED", "RSVP_UPDATED", "RSVP_DECLINED", "RSVP_CREATED",
    ]
    assert all(set(event) == {"kind", "occurred_at_utc"} for event in events)
    assert all(event["occurred_at_utc"].endswith("+00:00") for event in events)
    for private in ("Ana", "Beatriz", first.json["id"], first.json["edit_token"],
                    "Salão Margaridas"):
        assert private not in response.get_data(as_text=True)


def test_activity_limited_and_recent_first(client, store):
    initial = datetime.now(timezone.utc)
    for i in range(55):
        store.configure("Local " + str(i), None, initial)
    assert len(store.recent_activity()) == 50
    assert len(store.recent_activity(100)) == 55
    assert all(set(row) == {"kind", "occurred_at_utc"}
               for row in store.recent_activity())
    assert login(client).status_code == 200
    assert len(client.get("/api/admin/activity").json["events"]) == 50


def test_catering_csv_has_only_anonymous_totals(client):
    send(client, invitation("Ana"))
    send(client, invitation("Beatriz", attending=False))
    assert login(client).status_code == 200
    response = client.get("/api/admin/planning.csv")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert response.data.startswith(b"\xef\xbb\xbf")
    assert "no-store" in response.headers["Cache-Control"]
    assert "isadora-resumo-buffet.csv" in response.headers["Content-Disposition"]
    entries = dict(_read_csv(response.data)[1:])
    assert entries["Famílias confirmadas"] == "1"
    assert entries["Famílias que recusaram"] == "1"
    assert entries["Pessoas para buffet"] == "2"
    assert entries["Crianças até 12 anos / lembrancinhas"] == "2"
    assert entries["Crianças até 5 anos"] == "1"
    assert entries["Limite interno atingido"] == "Não"
    for private in ("Ana", "Beatriz", "contact_name", "edit_token"):
        assert private not in response.get_data(as_text=True)


def test_activity_schema_is_additive_and_migration_idempotent():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    # Simulate an existing v1 database without audit events.
    EventSettings.__table__.create(engine)
    Family.__table__.create(engine)
    Participant.__table__.create(engine)
    with engine.begin() as connection:
        connection.execute(EventSettings.__table__.insert().values(
            id=1, venue="Local anterior", buffet_limit=40
        ))
    migrate(engine)
    migrate(engine)
    with engine.connect() as connection:
        venue = connection.execute(select(EventSettings.venue)).scalar_one()
        versions = connection.exec_driver_sql(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).scalars().all()
        rows = connection.execute(select(AuditEvent)).all()
    assert venue == "Local anterior"
    assert versions == [1, 2, 3, 4, 5, 6]
    assert rows == []
    engine.dispose()
