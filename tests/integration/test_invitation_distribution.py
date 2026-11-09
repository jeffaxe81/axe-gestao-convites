"""Organizer-only invitation roster and one-family sharing capabilities."""
from tests.integration.test_public_api import store
from tests.integration.test_organizer_api import client, login
from app.guest_list import template_csv


def _import(client):
    token = login(client).json["csrf_token"]
    response = client.post(
        "/api/admin/guest-list-import", data=template_csv().encode("utf-8"),
        content_type="text/csv", headers={"X-CSRF-Token": token})
    assert response.status_code == 200


def test_roster_requires_authentication_and_never_contains_links(client, monkeypatch):
    assert client.get("/api/admin/invitations").status_code == 401
    _import(client)
    monkeypatch.setenv("APP_PUBLIC_URL", "https://isadora2anos.org")
    result = client.get("/api/admin/invitations")
    assert result.status_code == 200
    assert "no-store" in result.headers["Cache-Control"]
    assert result.json["counts"] == {
        "total": 1, "pending": 1, "confirmed": 0, "declined": 0
    }
    family = result.json["families"][0]
    assert set(family) == {"id", "key", "name", "phone", "status"}
    assert family["name"] == "Maria Silva"
    assert family["status"] == "PENDENTE"
    assert "token" not in result.get_data(as_text=True)
    assert "/convite#" not in result.get_data(as_text=True)
    path = "/api/admin/invitations/" + family["id"] + "/link"
    link_result = client.get(path)
    assert link_result.status_code == 200
    assert "no-store" in link_result.headers["Cache-Control"]
    assert link_result.json["url"].startswith("https://isadora2anos.org/convite#")
    assert len(link_result.json["url"].split(".")[-1]) == 64
    assert client.get("/api/admin/invitations/not-a-uuid/link").status_code == 422
    assert client.get("/api/admin/invitations/00000000-0000-0000-0000-000000000000/link").status_code == 422


def test_roster_reflects_confirmation_and_refusal(client, store):
    _import(client)
    roster = client.get("/api/admin/invitations").json
    family = roster["families"][0]
    invitation_token = store.invitation_token(family["id"])
    response = client.post(
        "/api/invitations/" + family["id"] + "/response",
        headers={"Authorization": "Bearer " + invitation_token},
        json={"contact_name": "Maria Silva", "attending": False, "participants": []})
    assert response.status_code == 200
    updated = client.get("/api/admin/invitations").json
    assert updated["counts"] == {
        "total": 1, "pending": 0, "confirmed": 0, "declined": 1}
    assert updated["families"][0]["status"] == "RECUSADO"


def test_share_link_is_private_even_if_family_id_is_known(client, monkeypatch):
    _import(client)
    family_id = client.get("/api/admin/invitations").json["families"][0]["id"]
    link_path = "/api/admin/invitations/" + family_id + "/link"
    token = client.get("/api/auth/csrf").json["csrf_token"]
    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": token}).status_code == 200
    assert client.get(link_path).status_code == 401
    monkeypatch.setenv("APP_PUBLIC_URL", "http://127.0.0.1:8080")
    login(client)
    local = client.get(link_path)
    assert local.status_code == 200
    assert local.json["url"].startswith("http://127.0.0.1:8080/convite#")
