"""Guest spreadsheet previews are private and never write registrations."""
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from xml.sax.saxutils import escape

from app.guest_list import template_csv, preview_csv, preview_xlsx
from app.guest_xlsx_template import template_xlsx
from tests.integration.test_public_api import store
from tests.integration.test_organizer_api import client, csrf, login


def excel(rows, with_formula=False):
    cells = []
    for rownum, values in enumerate(rows, 1):
        content = []
        for colnum, value in enumerate(values):
            letter = chr(65 + colnum)
            if with_formula and rownum == 2 and colnum == 3:
                content.append(f'<c r="{letter}{rownum}"><f>1+1</f><v>2</v></c>')
            else:
                content.append(f'<c r="{letter}{rownum}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        cells.append(f'<row r="{rownum}">{"".join(content)}</row>')
    sheet = ('<?xml version="1.0" encoding="UTF-8"?>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             '<sheetData>' + "".join(cells) + '</sheetData></worksheet>')
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return stream.getvalue()


def test_csv_example_preview_is_read_only():
    report = preview_csv(template_csv().encode("utf-8"))
    assert report["valid"]
    assert report["families"] == 1
    assert report["adults"] == 2
    assert report["children_0_5"] == 1
    assert report["saved"] is False
    assert report["links_created"] == 0


def test_downloadable_excel_template_round_trip():
    content = template_xlsx()
    assert content.startswith(b"PK")
    report = preview_xlsx(content)
    assert report["valid"] is True
    assert report["families"] == 1
    assert report["adults"] == 2
    assert report["children_0_5"] == 1
    assert report["saved"] is False


def test_xlsx_example_preview():
    content = excel([
        ["familia", "responsavel", "telefone", "adultos", "criancas_0_5", "criancas_6_12"],
        ["familia-silva", "Maria Silva", "11999999999", "2", "1", "0"]
    ])
    assert preview_xlsx(content)["valid"]


def test_xlsx_formula_not_evaluated():
    content = excel([
        ["familia", "responsavel", "telefone", "adultos", "criancas_0_5", "criancas_6_12"],
        ["familia-silva", "Maria Silva", "11999999999", "2", "1", "0"]
    ], with_formula=True)
    import pytest
    with pytest.raises(ValueError, match="fórmulas"):
        preview_xlsx(content)


def test_duplicate_families_rejected():
    payload = (template_csv() + "FAMILIA-SILVA;Outra Pessoa;11988888888;1;0;0\n").encode("utf-8")
    report = preview_csv(payload)
    assert not report["valid"]
    assert any("duplicada" in error for error in report["errors"])


def test_organizer_only_and_csrf(client):
    path = "/api/admin/guest-list-preview"
    assert client.get("/api/admin/guest-list-template.csv").status_code == 401
    assert client.get("/api/admin/guest-list-template.xlsx").status_code == 401
    assert client.post(path, data=template_csv().encode(), content_type="text/csv").status_code == 401
    credentials = login(client).json
    assert client.post(path, data=template_csv().encode(), content_type="text/csv").status_code == 403
    response = client.post(path, data=template_csv().encode(), content_type="text/csv",
                           headers={"X-CSRF-Token": credentials["csrf_token"]})
    assert response.status_code == 200
    assert response.json["valid"] is True
    assert client.get("/api/admin/guest-list-template.csv").status_code == 200
    excel_response = client.get("/api/admin/guest-list-template.xlsx")
    assert excel_response.status_code == 200
    assert excel_response.headers["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert excel_response.headers["Cache-Control"] == "no-store, private"
    assert "attachment" in excel_response.headers["Content-Disposition"]
    assert preview_xlsx(excel_response.data)["valid"] is True
    excel_preview = client.post(path, data=excel_response.data,
                                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                headers={"X-CSRF-Token": credentials["csrf_token"]})
    assert excel_preview.status_code == 200
    assert excel_preview.json["families"] == 1


def test_import_atomic_idempotent_and_pending(client):
    token = login(client).json["csrf_token"]
    headers = {"X-CSRF-Token": token}
    endpoint = "/api/admin/guest-list-import"
    csv_data = template_csv().encode("utf-8")
    result = client.post(endpoint, data=csv_data, content_type="text/csv", headers=headers)
    assert result.status_code == 200
    assert result.json == {"imported": 1, "existing_unchanged": 0, "total_in_file": 1}
    repeated = client.post(endpoint, data=csv_data, content_type="text/csv", headers=headers)
    assert repeated.status_code == 200
    assert repeated.json["imported"] == 0
    summary = client.get("/api/admin/guest-list-summary")
    assert summary.json["families"] == 1
    assert summary.json["pending"] == 1
    assert client.get("/api/admin/dashboard").json["counts"]["total"] == 0
    changed = csv_data.decode("utf-8-sig").replace("Maria Silva", "Outra Pessoa").encode()
    conflict = client.post(endpoint, data=changed, content_type="text/csv", headers=headers)
    assert conflict.status_code == 422
    assert client.get("/api/admin/guest-list-summary").json["families"] == 1


def test_import_requires_authenticated_csrf(client):
    payload = template_csv().encode()
    path = "/api/admin/guest-list-import"
    assert client.post(path, data=payload, content_type="text/csv").status_code == 401
    login(client)
    assert client.post(path, data=payload, content_type="text/csv").status_code == 403
