"""End-to-end HTTP contracts for individually scoped invitations."""
import csv
import io
from urllib.parse import urlsplit

from tests.integration.test_public_api import store
from tests.integration.test_organizer_api import client, login
from app.guest_list import template_csv


def _import_and_link(client, monkeypatch):
    monkeypatch.setenv("APP_PUBLIC_URL", "https://isadora2anos.org")
    csrf = login(client).json["csrf_token"]
    result = client.post(
        "/api/admin/guest-list-import", data=template_csv().encode("utf-8"),
        content_type="text/csv", headers={"X-CSRF-Token": csrf})
    assert result.status_code == 200
    response = client.get("/api/admin/invitation-links.csv")
    assert response.status_code == 200
    assert response.data.startswith(b"\xef\xbb\xbf")
    assert "no-store" in response.headers["Cache-Control"]
    rows = list(csv.reader(io.StringIO(response.data.decode("utf-8-sig")), delimiter=";"))
    assert rows[0] == ["Familia", "Responsavel", "Telefone", "Status", "Link individual"]
    assert len(rows) == 2
    link = rows[1][4]
    parts = urlsplit(link)
    assert parts.scheme == "https" and parts.netloc == "isadora2anos.org"
    assert parts.path == "/convite" and not parts.query
    ident, token = parts.fragment.split(".")
    assert len(token) == 64
    return ident, token


def test_invitation_can_be_read_only_by_its_family(client, monkeypatch):
    ident, token = _import_and_link(client, monkeypatch)
    path = "/api/invitations/" + ident
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer " + "0" * 64}).status_code == 401
    result = client.get(path, headers={"Authorization": "Bearer " + token})
    assert result.status_code == 200
    assert result.json == {
        "contact_name": "Maria Silva", "adults": 2, "children_0_5": 1,
        "children_6_12": 0, "responded": False
    }
    assert client.get("/convite").status_code == 200
    assert "Maria Silva" not in client.get("/convite").get_data(as_text=True)
    assert client.get("/api/admin/invitation-links.csv").status_code == 200


def test_invitation_answer_is_atomic_idempotent_and_editable(client, store, monkeypatch):
    ident, token = _import_and_link(client, monkeypatch)
    url = "/api/invitations/" + ident
    bearer = {"Authorization": "Bearer " + token}
    payload = {
        "contact_name": "Maria Silva", "attending": True,
        "participants": [
            {"name": "Maria Silva", "kind": "OVER_12", "age_years": None},
            {"name": "Rafa", "kind": "CHILD", "age_years": 4}
        ]
    }
    assert client.post(url + "/response", json=payload).status_code == 401
    first = client.post(url + "/response", json=payload, headers=bearer)
    assert first.status_code == 200
    assert first.json["attending"] is True
    again = client.post(url + "/response", json=payload, headers=bearer)
    assert again.status_code == 200 and again.json == first.json
    assert len(store.summary()["confirmed"]) == 1
    own = client.get(url, headers=bearer).json
    assert own["responded"] is True and own["receipt"] == first.json
    assert store.invited_family_summary()["pending"] == 0
    assert "CONFIRMADO" in client.get("/api/admin/invitation-links.csv").get_data(as_text=True)
    conflict = client.post(url + "/response", json={
        "contact_name": "Outra", "attending": False, "participants": []
    }, headers=bearer)
    assert conflict.status_code == 409
    update = client.put("/api/rsvps/" + first.json["id"],
        headers={"Authorization": "Bearer " + first.json["edit_token"]},
        json={"revision": 1, "contact_name": "Maria Silva",
              "attending": False, "participants": []})
    assert update.status_code == 200
    assert store.invited_family_summary()["pending"] == 0
    assert "RECUSADO" in client.get("/api/admin/invitation-links.csv").get_data(as_text=True)
    assert store.summary()["counts"].total == 0


def test_link_export_never_public(client, monkeypatch):
    assert client.get("/api/admin/invitation-links.csv").status_code == 401
    assert client.get("/api/invitations/not-a-valid-id").status_code == 401
    monkeypatch.delenv("APP_PUBLIC_URL", raising=False)
    login(client)
    response = client.get("/api/admin/invitation-links.csv")
    assert response.status_code == 422
