"""Regressão de números de linha Excel: sem HTTP 500 ou persistência indevida."""
from io import BytesIO
from zipfile import ZipFile

import pytest

from app.guest_list import preview_xlsx
from app.guest_xlsx_template import template_xlsx
from tests.integration.test_organizer_api import client, login
from tests.integration.test_public_api import store
from tests.integration.test_xlsx_hidden_and_duplicates import modified_sheet
from tests.integration.test_xlsx_tab_order import rewrite

MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.mark.parametrize("value", [
    b"0", b"0002", b"1048577", b"9999999", b"9" * 5000,
    "٢".encode("utf-8"), b"segredo-pessoal",
], ids=["zero", "leading-zero", "beyond-excel", "seven-digit", "overlong", "unicode", "sensitive"])
def test_rejects_invalid_row_number_without_echoing_content(value):
    document = modified_sheet(b'<row r="2">', b'<row r="' + value + b'">')
    with pytest.raises(ValueError, match="Número de linha Excel inválido") as error:
        preview_xlsx(document)
    assert "segredo-pessoal" not in str(error.value)


@pytest.mark.parametrize("value", [
    b"B0", b"B1048577", b"B9999999", b"B" + b"9" * 5000,
], ids=["zero", "beyond-excel", "seven-digit", "overlong"])
def test_rejects_out_of_bounds_cell_reference(value):
    document = modified_sheet(
        b'r="B2" t="inlineStr"', b'r="' + value + b'" t="inlineStr"'
    )
    with pytest.raises(ValueError) as error:
        preview_xlsx(document)
    assert "inválid" in str(error.value)


def test_last_valid_excel_row_is_accepted():
    source = template_xlsx()
    with ZipFile(BytesIO(source)) as archive:
        sheet = archive.read("xl/worksheets/sheet1.xml")
    sheet = sheet.replace(b'<row r="2">', b'<row r="1048576">')
    for column in b"ABCDEF":
        sheet = sheet.replace(
            b'r="' + bytes([column]) + b'2"',
            b'r="' + bytes([column]) + b'1048576"',
        )
    document = rewrite(source, {"xl/worksheets/sheet1.xml": sheet})
    report = preview_xlsx(document)
    assert report["valid"] is True
    assert report["families"] == 1


@pytest.mark.parametrize("old,new", [
    (b'<row r="2">', b'<row r="' + b"9" * 5000 + b'">'),
    (b'<row r="2">', b'<row r="1048577">'),
    (b'r="B2" t="inlineStr"', b'r="B1048577" t="inlineStr"'),
    (b'r="B2" t="inlineStr"', b'r="B' + b"9" * 5000 + b'" t="inlineStr"'),
], ids=["huge-row", "beyond-excel-row", "beyond-excel-cell", "huge-cell"])
def test_malformed_row_returns_422_without_saving_families(client, old, new):
    csrf = login(client).json["csrf_token"]
    response = client.post(
        "/api/admin/guest-list-import",
        data=modified_sheet(old, new),
        content_type=MIME,
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 422
    assert response.json["error"]["code"] == "INVALID_INPUT"
    assert client.get("/api/admin/guest-list-summary").json["families"] == 0
    assert client.get("/api/admin/dashboard").json["counts"]["total"] == 0
