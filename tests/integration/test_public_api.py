"""HTTP contract: no buffet rules or other families leak through guest API."""
from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import create_app
from app.models import Base, EventSettings
from app.rsvp import RsvpStore


def invitation(name="Ana", attending=True):
    return {
        "contact_name": name,
        "attending": attending,
        "participants": (
            [{"name": name, "kind": "OVER_12", "age_years": None},
             {"name": "Cris", "kind": "CHILD", "age_years": 5},
             {"name": "Bia", "kind": "CHILD", "age_years": 6}]
            if attending else []
        ),
    }


@pytest.fixture
def store():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(EventSettings(id=1, buffet_limit=40))
    yield RsvpStore(factory, "only-for-api-testing-123456789")
    engine.dispose()


@pytest.fixture
def client(store):
    app = create_app({"TESTING": True, "RSVP_STORE": store, "API_RATE_LIMIT": 0})
    return app.test_client()


def send(client, data=None, key=None):
    return client.post(
        "/api/rsvps",
        json=data or invitation(),
        headers={"Idempotency-Key": key or str(uuid4())},
    )


def bearer(token):
    return {"Authorization": "Bearer " + token}


def test_event_has_only_safe_fields(client):
    response = client.get("/api/event")
    assert response.status_code == 200
    assert set(response.json) == {"name", "age", "starts_at", "timezone", "venue"}
    assert response.json["venue"] == "Local a confirmar"
    assert response.json["starts_at"].startswith("2026-12-13T15:00:00")


def test_positive_confirmation_does_not_expose_buffet(client):
    result = send(client)
    assert result.status_code == 201
    assert set(result.json) == {"id", "revision", "edit_token", "attending"}
    assert result.json["revision"] == 1
    assert result.json["attending"] is True
    assert "buffet" not in str(result.json).lower()


def test_retry_same_key_returns_exactly_one_family(client, store):
    key = str(uuid4())
    first = send(client, key=key)
    second = send(client, key=key)
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json == second.json
    assert len(store.summary()["confirmed"]) == 1


def test_reuse_key_with_different_payload_is_conflict(client):
    key = str(uuid4())
    assert send(client, key=key).status_code == 201
    assert send(client, invitation("Outra pessoa"), key=key).status_code == 409


def test_missing_idempotency_key_rejected(client):
    result = client.post("/api/rsvps", json=invitation())
    assert result.status_code == 422


def test_get_requires_own_bearer(client):
    a = send(client).json
    b = send(client, invitation("Beatriz")).json
    path = "/api/rsvps/" + b["id"]
    assert client.get(path).status_code == 401
    assert client.get(path, headers=bearer(a["edit_token"])).status_code == 401
    assert client.get(path, headers=bearer(b["edit_token"])).status_code == 200


def test_edit_uses_revision_and_preserves_id(client):
    data = send(client).json
    path = "/api/rsvps/" + data["id"]
    edit = client.put(
        path, headers=bearer(data["edit_token"]),
        json={"revision": 1, **invitation("Ana", attending=False)},
    )
    assert edit.status_code == 200
    assert edit.json["id"] == data["id"]
    assert edit.json["revision"] == 2
    assert client.get(path, headers=bearer(data["edit_token"])).json["participants"] == []


def test_stale_edits_get_conflict(client):
    data = send(client).json
    path = "/api/rsvps/" + data["id"]
    body = {"revision": 1, **invitation()}
    headers = bearer(data["edit_token"])
    assert client.put(path, json=body, headers=headers).status_code == 200
    assert client.put(path, json=body, headers=headers).status_code == 409


def test_expired_edit_is_forbidden(client, store):
    data = send(client).json
    store.configure(
        "Salão",
        datetime.now(timezone.utc) - timedelta(seconds=1),
        datetime.now(timezone.utc),
    )
    result = client.put(
        "/api/rsvps/" + data["id"],
        json={"revision": 1, **invitation()},
        headers=bearer(data["edit_token"]),
    )
    assert result.status_code == 403


def test_malformed_and_invalid_payloads(client):
    malformed = client.post(
        "/api/rsvps", data="{broken",
        content_type="application/json",
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert malformed.status_code == 400
    invalid = send(client, {"contact_name": "", "attending": False, "participants": []})
    assert invalid.status_code == 422


def test_liveness_and_database_readiness(client):
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200


def test_guest_does_not_receive_other_families_or_deadline_limit(client, store):
    a = send(client).json
    send(client, invitation("Beatriz"))
    own = client.get("/api/rsvps/" + a["id"], headers=bearer(a["edit_token"]))
    assert own.status_code == 200
    assert "Beatriz" not in str(own.json)
    assert not any(x in own.json for x in ("counts", "buffet_limit", "confirmed", "declined"))
    settings = client.get("/api/event").json
    assert not any(x in settings for x in ("counts", "buffet_limit", "confirmed", "declined"))


def test_readiness_fails_when_store_is_unavailable():
    class Disconnected:
        def settings(self):
            raise ConnectionError("internal credentials: do not expose")
    app = create_app({"TESTING": True, "RSVP_STORE": Disconnected(), "API_RATE_LIMIT": 0})
    response = app.test_client().get("/health/ready")
    assert response.status_code == 503
    assert "credentials" not in response.get_data(as_text=True)
