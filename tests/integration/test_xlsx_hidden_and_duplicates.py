"""Excel: não cadastrar famílias invisíveis nem aceitar células ambíguas."""
from io import BytesIO
from zipfile import ZipFile

import pytest

from app.guest_list import preview_xlsx
from app.guest_xlsx_template import template_xlsx
from tests.integration.test_xlsx_tab_order import rewrite
from tests.integration.test_public_api import store
from tests.integration.test_organizer_api import client, login

MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def modified_sheet(old, new):
    source = template_xlsx()
    with ZipFile(BytesIO(source)) as archive:
        sheet = archive.read("xl/worksheets/sheet1.xml")
    assert old in sheet
    return rewrite(source, {
        "xl/worksheets/sheet1.xml": sheet.replace(old, new, 1),
    })


def test_hidden_family_row_never_enters_preview():
    document = modified_sheet(
        b'<row r="2">', b'<row r="2" hidden="1">'
    )
    with pytest.raises(ValueError, match="linhas ocultas"):
        preview_xlsx(document)


@pytest.mark.parametrize("attribute", [b'1', b'true', b'TRUE'])
def test_hidden_required_column_is_rejected(attribute):
    document = modified_sheet(
        b"<sheetData>",
        b'<cols><col min="2" max="2" hidden="' + attribute +
        b'"/></cols><sheetData>',
    )
    with pytest.raises(ValueError, match="Colunas A até F"):
        preview_xlsx(document)


def test_hide_unrelated_column_is_allowed():
    document = modified_sheet(
        b"<sheetData>",
        b'<cols><col min="7" max="7" hidden="1"/></cols><sheetData>',
    )
    result = preview_xlsx(document)
    assert result["valid"] is True
    assert result["families"] == 1


def test_explicitly_visible_row_and_column_are_allowed():
    document = modified_sheet(
        b'<row r="2">',
        b'<row r="2" hidden="0">',
    )
    assert preview_xlsx(document)["valid"] is True
    document = modified_sheet(
        b"<sheetData>",
        b'<cols><col min="2" max="2" hidden="false"/></cols><sheetData>',
    )
    assert preview_xlsx(document)["valid"] is True


def test_duplicate_cell_is_rejected_instead_of_overwriting_contact():
    document = modified_sheet(
        b'<c r="B2" t="inlineStr"><is><t>Maria Silva</t></is></c>',
        b'<c r="B2" t="inlineStr"><is><t>Maria Silva</t></is></c>'
        b'<c r="B2" t="inlineStr"><is><t>Outra Pessoa</t></is></c>',
    )
    with pytest.raises(ValueError, match="Célula duplicada"):
        preview_xlsx(document)


def test_duplicate_row_identifier_is_rejected():
    document = modified_sheet(
        b'<row r="2">',
        b'<row r="1">',
    )
    with pytest.raises(ValueError, match="Linha repetida"):
        preview_xlsx(document)


def test_cell_with_wrong_row_identifier_is_rejected():
    document = modified_sheet(
        b'r="B2" t="inlineStr"',
        b'r="B3" t="inlineStr"',
    )
    with pytest.raises(ValueError, match="fora da linha"):
        preview_xlsx(document)


@pytest.mark.parametrize("old,new", [
    (b'<row r="2">', b'<row r="2" hidden="true">'),
    (b'<sheetData>', b'<cols><col min="1" max="1" hidden="1"/></cols><sheetData>'),
    (b'<c r="B2" t="inlineStr"><is><t>Maria Silva</t></is></c>',
     b'<c r="B2" t="inlineStr"><is><t>Maria Silva</t></is></c>'
     b'<c r="B2" t="inlineStr"><is><t>Outra Pessoa</t></is></c>'),
])
def test_unsafe_excel_import_fails_without_writing_any_family(client, old, new):
    csrf = login(client).json["csrf_token"]
    response = client.post(
        "/api/admin/guest-list-import",
        data=modified_sheet(old, new), content_type=MIME,
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 422
    assert client.get("/api/admin/guest-list-summary").json["families"] == 0
    assert client.get("/api/admin/dashboard").json["counts"]["total"] == 0
