"""Relatório privado de acompanhamento, separado de RSVP e segredos de convite."""
import csv
import io

from tests.integration.test_organizer_api import client, login
from tests.integration.test_public_api import store


def _rows(payload):
    return list(csv.reader(io.StringIO(payload.decode("utf-8-sig")), delimiter=";"))


def _import_two_families(client, csrf):
    payload = (
        "familia;responsavel;telefone;adultos;criancas_0_5;criancas_6_12\r\n"
        "familia-a;=HYPERLINK(1);11999999999;2;0;0\r\n"
        "familia-b;Maria Silva;11988888888;1;1;0\r\n"
    )
    response = client.post(
        "/api/admin/guest-list-import", data=payload.encode("utf-8"),
        headers={"X-CSRF-Token": csrf}, content_type="text/csv"
    )
    assert response.status_code == 200


def test_followup_csv_requires_login_and_does_not_leak_tokens(client, store):
    endpoint = "/api/admin/invitation-followup.csv"
    assert client.get(endpoint).status_code == 401
    csrf = login(client).json["csrf_token"]
    _import_two_families(client, csrf)
    roster = client.get("/api/admin/invitations").json["families"]
    first = next(row for row in roster if row["key"] == "familia-a")
    second = next(row for row in roster if row["key"] == "familia-b")
    first_token = store.invitation_token(first["id"])
    assert client.post("/api/invitations/" + first["id"] + "/interest",
        headers={"Authorization": "Bearer " + first_token}).status_code == 200
    assert client.put("/api/admin/invitations/" + first["id"] + "/sent",
        headers={"X-CSRF-Token": csrf}, json={"sent": True}).status_code == 200
    assert client.post("/api/invitations/" + first["id"] + "/response",
        headers={"Authorization": "Bearer " + first_token},
        json={"contact_name": "Maria Teste", "attending": False, "participants": []}
    ).status_code == 200

    response = client.get(endpoint)
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert response.data.startswith(b"\xef\xbb\xbf")
    assert "no-store" in response.headers["Cache-Control"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "attachment" in response.headers["Content-Disposition"]
    assert first_token.encode() not in response.data
    assert "/convite#" not in response.get_data(as_text=True)
    assert "edit_token" not in response.get_data(as_text=True)
    rows = _rows(response.data)
    assert len(rows) == 3
    assert len(rows[0]) == 8
    a = next(row for row in rows[1:] if row[0] == "familia-a")
    b = next(row for row in rows[1:] if row[0] == "familia-b")
    assert a[1] == "'=HYPERLINK(1)"
    assert a[2] == "11999999999"
    assert a[3] == "RECUSADO"
    assert a[4] == "Sim" and a[5].endswith("+00:00")
    assert a[6] == "Sim" and a[7].endswith("+00:00")
    assert b[:4] == ["familia-b", "Maria Silva", "11988888888", "PENDENTE"]
    assert b[4:] == ["Nao", "", "Nao", ""]

    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 200
    assert client.get(endpoint).status_code == 401


def test_followup_csv_works_with_no_registered_families(client):
    login(client)
    response = client.get("/api/admin/invitation-followup.csv")
    assert response.status_code == 200
    rows = _rows(response.data)
    assert len(rows) == 1
    assert len(rows[0]) == 8
