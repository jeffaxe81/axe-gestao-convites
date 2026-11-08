"""Organizer API security and private statistics contract."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from tests.integration.test_public_api import store, invitation, send


@pytest.fixture
def client(store):
    app = create_app({
        "TESTING": True,
        "RSVP_STORE": store,
        "SECRET_KEY": "organizer-session-only-in-unit-tests-1234",
        "ORGANIZER_USERNAME": "isadora-admin",
        "ORGANIZER_PASSWORD_HASH": generate_password_hash("minha-senha-de-teste"),
        "AUTH_RATE_LIMIT": 0,
        "API_RATE_LIMIT": 0,
    })
    return app.test_client()


def csrf(client):
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200
    assert set(response.json) == {"csrf_token"}
    return response.json["csrf_token"]


def login(client, password="minha-senha-de-teste"):
    token = csrf(client)
    return client.post("/api/auth/login", json={
        "username": "isadora-admin", "password": password,
    }, headers={"X-CSRF-Token": token})


def test_dashboard_and_settings_require_session(client):
    assert client.get("/api/admin/dashboard").status_code == 401
    assert client.get("/api/admin/settings").status_code == 401
    assert client.put("/api/admin/settings", json={"venue": "Salão", "edit_deadline_utc": None}).status_code == 401


def test_login_requires_matching_csrf(client):
    payload = {"username": "isadora-admin", "password": "minha-senha-de-teste"}
    assert client.post("/api/auth/login", json=payload).status_code == 403
    token = csrf(client)
    assert client.post("/api/auth/login", json=payload, headers={"X-CSRF-Token": token+"x"}).status_code == 403
    assert client.get("/api/admin/dashboard").status_code == 401


def test_invalid_password_does_not_authenticate(client):
    bad = login(client, password="senha-incorreta")
    assert bad.status_code == 401
    assert client.get("/api/admin/dashboard").status_code == 401


def test_private_dashboard_counts_confirmed_only(client, store):
    send(client, invitation("Ana"))
    send(client, invitation("Beatriz", attending=False))
    assert login(client).status_code == 200
    dashboard = client.get("/api/admin/dashboard")
    assert dashboard.status_code == 200
    data = dashboard.json
    assert data["counts"] == {
        "total": 3, "buffet": 2, "children_0_5": 1,
        "children_0_12": 2, "over_12": 1,
    }
    assert len(data["confirmed"]) == 1
    assert len(data["declined"]) == 1
    assert len(data["souvenir_children"]) == 2
    assert data["buffet_limit"] == 40
    assert len(client.get("/api/event").json) == 5


def test_login_rotates_csrf_for_admin_updates(client):
    old = csrf(client)
    result = client.post("/api/auth/login", json={
        "username": "isadora-admin", "password": "minha-senha-de-teste",
    }, headers={"X-CSRF-Token": old})
    assert result.status_code == 200
    new = result.json["csrf_token"]
    assert old != new
    path = "/api/admin/settings"
    body = {"venue": "Salão de festas", "edit_deadline_utc": None}
    assert client.put(path, json=body, headers={"X-CSRF-Token": old}).status_code == 403
    assert client.put(path, json=body, headers={"X-CSRF-Token": new}).status_code == 200
    assert client.get("/api/event").json["venue"] == "Salão de festas"


def test_deadline_is_validated_with_explicit_timezone(client):
    token = login(client).json["csrf_token"]
    path = "/api/admin/settings"
    headers = {"X-CSRF-Token": token}
    no_timezone = {"venue": "Local", "edit_deadline_utc": "2026-12-01T10:00:00"}
    assert client.put(path, json=no_timezone, headers=headers).status_code == 422
    accepted = {"venue": "Local", "edit_deadline_utc": "2026-11-30T23:59:00-03:00"}
    assert client.put(path, json=accepted, headers=headers).status_code == 200
    assert client.get(path).json["edit_deadline_utc"] == "2026-12-01T02:59:00+00:00"


def test_logout_invalidates_access(client):
    token = login(client).json["csrf_token"]
    assert client.get("/api/admin/dashboard").status_code == 200
    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": token}).status_code == 200
    assert client.get("/api/admin/dashboard").status_code == 401


def test_configuration_rejects_unknown_fields(client):
    token = login(client).json["csrf_token"]
    response = client.put("/api/admin/settings",
        json={"venue": "Salão", "edit_deadline_utc": None, "buffet_limit": 100},
        headers={"X-CSRF-Token": token})
    assert response.status_code == 422


def test_session_cookie_has_httponly_samesite(client):
    result = login(client)
    cookies = result.headers.getlist("Set-Cookie")
    assert any("HttpOnly" in c and "SameSite=Lax" in c for c in cookies)
