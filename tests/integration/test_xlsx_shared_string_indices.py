"""Regressão: índices de sharedStrings inválidos não expõem dados nem gravam famílias."""
from io import BytesIO
from zipfile import ZipFile

import pytest

from app.guest_list import preview_xlsx
from app.guest_xlsx_template import template_xlsx
from tests.integration.test_organizer_api import client, login
from tests.integration.test_public_api import store
from tests.integration.test_xlsx_tab_order import rewrite

MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def shared_index_sheet(index: bytes, *, with_strings: bool = False) -> bytes:
    source = template_xlsx()
    with ZipFile(BytesIO(source)) as archive:
        sheet = archive.read("xl/worksheets/sheet1.xml")
    original = b'<c r="B2" t="inlineStr"><is><t>Maria Silva</t></is></c>'
    assert original in sheet
    replacement = b'<c r="B2" t="s"><v>' + index + b'</v></c>'
    updated = {"xl/worksheets/sheet1.xml": sheet.replace(original, replacement, 1)}
    if with_strings:
        updated["xl/sharedStrings.xml"] = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            b'count="1" uniqueCount="1"><si><t>Maria Silva</t></si></sst>'
        )
    return rewrite(source, updated)


def test_valid_shared_string_remains_supported():
    report, families = preview_xlsx(
        shared_index_sheet(b"0", with_strings=True), include_records=True
    )
    assert report["valid"] is True
    assert families[0]["name"] == "Maria Silva"


@pytest.mark.parametrize("index", [
    b"segredo-pessoal", b"-1", b" 0", b"99999999999", b"0", b""
])
def test_invalid_index_never_leaks_excel_content(index):
    with pytest.raises(ValueError, match="Índice de texto compartilhado inválido") as error:
        preview_xlsx(shared_index_sheet(index))
    assert "segredo-pessoal" not in str(error.value)


def test_invalid_excel_import_is_422_without_database_writes(client):
    csrf = login(client).json["csrf_token"]
    response = client.post(
        "/api/admin/guest-list-import",
        data=shared_index_sheet(b"segredo-pessoal"),
        content_type=MIME,
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 422
    assert response.json["error"]["code"] == "INVALID_INPUT"
    assert "segredo-pessoal" not in response.json["error"]["message"]
    assert client.get("/api/admin/guest-list-summary").json["families"] == 0
    assert client.get("/api/admin/dashboard").json["counts"]["total"] == 0
