"""Guest spreadsheet previews are private and never write registrations."""
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from xml.sax.saxutils import escape

from app.guest_list import template_csv, preview_csv, preview_xlsx
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
    assert client.post(path, data=template_csv().encode(), content_type="text/csv").status_code == 401
    credentials = login(client).json
    assert client.post(path, data=template_csv().encode(), content_type="text/csv").status_code == 403
    response = client.post(path, data=template_csv().encode(), content_type="text/csv",
                           headers={"X-CSRF-Token": credentials["csrf_token"]})
    assert response.status_code == 200
    assert response.json["valid"] is True
    assert client.get("/api/admin/guest-list-template.csv").status_code == 200
