"""Exportação de presença: privacidade, compatibilidade e CSV injection."""
import csv
import io

from app.reports import export_attendance_csv, safe_cell
from tests.integration.test_organizer_api import client, login
from tests.integration.test_public_api import invitation, send


def rows(raw):
    return list(csv.reader(io.StringIO(raw.decode("utf-8-sig")),
                           delimiter=";"))


def test_export_requires_organizer_session(client):
    send(client, invitation("Segredo"))
    response = client.get("/api/admin/export.csv")
    assert response.status_code == 401
    assert b"Segredo" not in response.data


def test_export_confirmations_declines_age_and_no_tokens(client):
    send(client, invitation("Ana"))
    send(client, invitation("Beatriz", attending=False))
    assert login(client).status_code == 200
    result = client.get("/api/admin/export.csv")
    assert result.status_code == 200
    assert result.data.startswith(b"\xef\xbb\xbf")
    assert result.mimetype == "text/csv"
    assert "no-store" in result.headers["Cache-Control"]
    assert result.headers["X-Content-Type-Options"] == "nosniff"
    assert "attachment" in result.headers["Content-Disposition"]
    parsed = rows(result.data)
    assert len(parsed) == 5
    assert parsed[1] == ["Confirmado", "Ana", "Ana", "Acima de 12", "", "Sim", "Não"]
    assert parsed[2][3:] == ["Criança", "5", "Não", "Sim"]
    assert parsed[3][3:] == ["Criança", "6", "Sim", "Sim"]
    assert parsed[4] == ["Recusou", "Beatriz", "", "", "", "Não", "Não"]
    assert not any("edit_token" in str(r) or "submission_key_hash" in str(r)
                   for r in parsed)


def test_csv_injection_is_neutralized(client):
    send(client, invitation("=HYPERLINK(1)"))
    send(client, invitation("+SUM(5)", attending=False))
    assert login(client).status_code == 200
    entries = rows(client.get("/api/admin/export.csv").data)
    assert entries[1][1] == "'=HYPERLINK(1)"
    assert entries[1][2] == "'=HYPERLINK(1)"
    assert entries[2][1] == "'+SUM(5)"


def test_csv_formula_edge_cases():
    assert safe_cell("@evil") == "'@evil"
    assert safe_cell(" -10") == "' -10"
    assert safe_cell("\t=cmd") == "'\t=cmd"
    assert safe_cell("Ana") == "Ana"
    assert safe_cell(None) == ""
    raw = export_attendance_csv({"confirmed": [], "declined": []})
    assert len(rows(raw)) == 1


def test_export_disappears_after_logout(client):
    login_result = login(client)
    token = login_result.json["csrf_token"]
    assert client.get("/api/admin/export.csv").status_code == 200
    assert client.post("/api/auth/logout",
                       headers={"X-CSRF-Token": token}).status_code == 200
    assert client.get("/api/admin/export.csv").status_code == 401
