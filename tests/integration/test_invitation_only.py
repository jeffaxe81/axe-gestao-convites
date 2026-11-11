"""Novas confirmações exigem link individual em produção; edição legada preservada."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.domain import validate_rsvp
from app.guest_list import template_csv
from tests.integration.test_public_api import store, invitation
from tests.integration.test_organizer_api import login


@pytest.fixture
def private_client(store):
    app = create_app({
        "TESTING": True, "RSVP_STORE": store,
        "API_RATE_LIMIT": 0, "INVITATION_ONLY": True,
    })
    return app.test_client()


def test_anonymous_rsvp_is_blocked_without_creating_records(private_client, store):
    response = private_client.post(
        "/api/rsvps", json=invitation("Falso"),
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 403
    assert response.json["error"]["code"] == "INVITATION_REQUIRED"
    assert "link individual" in response.json["error"]["message"]
    assert store.summary()["counts"].total == 0
    assert store.invited_family_summary()["families"] == 0


def test_anonymous_rsvp_rejects_before_payload_parsing(private_client, store):
    response = private_client.post(
        "/api/rsvps", data=b"{invalid",
        headers={"Idempotency-Key": "not-needed"},
        content_type="application/json",
    )
    assert response.status_code == 403
    assert store.summary()["counts"].total == 0


def test_landing_page_informs_user_without_exposing_rsvp_form(private_client):
    landing = private_client.get("/")
    assert landing.status_code == 200
    body = landing.get_data(as_text=True)
    assert "Confirmação somente pelo convite individual" in body
    assert '<form id="rsvp-form" novalidate hidden>' in body
    assert '<p id="stage-indicator"' in body
    assert "no-store" in landing.headers["Cache-Control"]
    invite = private_client.get("/convite").get_data(as_text=True)
    assert '<form id="rsvp-form" novalidate>' in invite
    assert "Confirmação somente pelo convite individual" not in invite


def test_authorized_family_can_confirm_and_update_in_strict_mode(private_client, store):
    csrf = login(private_client).json["csrf_token"]
    imported = private_client.post(
        "/api/admin/guest-list-import",
        data=template_csv().encode("utf-8"),
        content_type="text/csv", headers={"X-CSRF-Token": csrf},
    )
    assert imported.status_code == 200
    family_id = private_client.get("/api/admin/invitations").json["families"][0]["id"]
    bearer = {"Authorization": "Bearer " + store.invitation_token(family_id)}
    payload = invitation("Maria Silva")
    confirmed = private_client.post(
        "/api/invitations/" + family_id + "/response",
        headers=bearer, json=payload,
    )
    assert confirmed.status_code == 200
    assert store.summary()["counts"].total == 3
    again = private_client.post(
        "/api/invitations/" + family_id + "/response",
        headers=bearer, json=payload,
    )
    assert again.status_code == 200
    assert again.json == confirmed.json
    edit = private_client.put(
        "/api/rsvps/" + confirmed.json["id"],
        headers={"Authorization": "Bearer " + confirmed.json["edit_token"]},
        json={"revision": 1, **invitation("Maria Silva", attending=False)},
    )
    assert edit.status_code == 200
    assert store.summary()["counts"].total == 0


def test_existing_legacy_receipt_remains_editable_in_strict_mode(private_client, store):
    original = store.create(
        validate_rsvp(invitation("Pessoa de teste")),
        "legacy-unique-submission-key-0001",
        datetime.now(timezone.utc),
    )
    edit = private_client.put(
        "/api/rsvps/" + original.id,
        headers={"Authorization": "Bearer " + original.edit_token},
        json={"revision": original.revision,
              **invitation("Pessoa de teste", attending=False)},
    )
    assert edit.status_code == 200
    assert edit.json["revision"] == original.revision + 1


def test_production_is_strict_by_default_and_cannot_disable_it(store, monkeypatch):
    monkeypatch.setenv("APP_PUBLIC_URL", "https://isadora2anos.org")
    config = {
        "TESTING": False, "RSVP_STORE": store,
        "SECRET_KEY": "a" * 40,
        "ORGANIZER_USERNAME": "organizador",
        "ORGANIZER_PASSWORD_HASH": generate_password_hash("only-test-password"),
    }
    app = create_app(config)
    assert app.config["INVITATION_ONLY"] is True
    response = app.test_client().post(
        "/api/rsvps", base_url="https://isadora2anos.org",
        json=invitation(), headers={"Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 403
    with pytest.raises(ValueError, match="não pode ser sobrescrito"):
        create_app({**config, "INVITATION_ONLY": False})
