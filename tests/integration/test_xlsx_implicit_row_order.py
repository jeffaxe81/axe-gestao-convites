"""Excel: row-order/cell-address consistency, including omitted row identifiers."""
import re
from io import BytesIO
from zipfile import ZipFile

import pytest

from app.guest_list import preview_xlsx
from app.guest_xlsx_template import template_xlsx
from tests.integration.test_organizer_api import client, login
from tests.integration.test_public_api import store
from tests.integration.test_xlsx_tab_order import rewrite

MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def changed_sheet(transform):
    original = template_xlsx()
    with ZipFile(BytesIO(original)) as archive:
        sheet = archive.read("xl/worksheets/sheet1.xml")
    return rewrite(original, {"xl/worksheets/sheet1.xml": transform(sheet)})


def without_row_number(sheet):
    assert b'<row r="2">' in sheet
    return sheet.replace(b'<row r="2">', b'<row>', 1)


def mismatched_implicit_row(sheet):
    sheet = without_row_number(sheet)
    assert b'r="B2"' in sheet
    return sheet.replace(b'r="B2"', b'r="B3"', 1)


def reversed_rows(sheet):
    match = re.search(rb'(<row r="1">.*?</row>)(<row r="2">.*?</row>)', sheet)
    assert match
    return sheet.replace(match.group(0), match.group(2) + match.group(1), 1)


def test_optional_row_number_still_works_when_addresses_match():
    result, records = preview_xlsx(changed_sheet(without_row_number),
                                   include_records=True)
    assert result["valid"] is True
    assert records[0]["key"] == "familia-silva"


def test_optional_header_row_number_is_inferred():
    document = changed_sheet(
        lambda sheet: sheet.replace(b'<row r="1">', b'<row>', 1)
    )
    assert preview_xlsx(document)["valid"] is True


@pytest.mark.parametrize("transform", [mismatched_implicit_row, reversed_rows],
                         ids=["cell-from-different-row", "out-of-order-rows"])
def test_ambiguous_row_locations_are_rejected(transform):
    with pytest.raises(ValueError, match=r"[Ll]inha"):
        preview_xlsx(changed_sheet(transform))


@pytest.mark.parametrize("transform", [mismatched_implicit_row, reversed_rows],
                         ids=["mismatched-implicit", "reordered-physical"])
def test_ambiguous_row_locations_never_import_any_family(client, transform):
    csrf = login(client).json["csrf_token"]
    response = client.post(
        "/api/admin/guest-list-import",
        data=changed_sheet(transform), content_type=MIME,
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 422
    assert response.json["error"]["code"] == "INVALID_INPUT"
    assert client.get("/api/admin/guest-list-summary").json["families"] == 0
    assert client.get("/api/admin/dashboard").json["counts"]["total"] == 0
