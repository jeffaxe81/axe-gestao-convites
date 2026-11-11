"""XLSX: a primeira aba é definida pelo workbook, não pelo nome sheet1.xml."""
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED

import pytest

from app.guest_list import preview_xlsx
from app.guest_xlsx_template import template_xlsx
from tests.integration.test_public_api import store
from tests.integration.test_organizer_api import client, login

MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
REL_TYPE = (
    b"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
)


def rewrite(source, updated=None, removed=()):
    """Remonta um XLSX pequeno sem bibliotecas que executem fórmulas."""
    output = BytesIO()
    updated = updated or {}
    with ZipFile(BytesIO(source)) as original:
        with ZipFile(output, "w", ZIP_DEFLATED) as target:
            for member in original.infolist():
                if member.filename not in removed:
                    target.writestr(
                        member, updated.get(member.filename, original.read(member.filename))
                    )
            for name, payload in updated.items():
                if name not in original.namelist():
                    target.writestr(name, payload)
    return output.getvalue()


def first_sheet_is_sheet2():
    original = template_xlsx()
    with ZipFile(BytesIO(original)) as archive:
        workbook = archive.read("xl/workbook.xml")
        rels = archive.read("xl/_rels/workbook.xml.rels")
        sheet1 = archive.read("xl/worksheets/sheet1.xml")
        content_types = archive.read("[Content_Types].xml")

    workbook = workbook.replace(
        b'<sheet name="Familias" sheetId="1" r:id="rId1"/>',
        b'<sheet name="Primeira" sheetId="2" r:id="rId2"/>'
        b'<sheet name="Segunda" sheetId="1" r:id="rId1"/>',
    )
    rels = rels.replace(
        b"</Relationships>",
        b'<Relationship Id="rId2" Type="' + REL_TYPE +
        b'" Target="worksheets/sheet2.xml"/></Relationships>',
    )
    content_types = content_types.replace(
        b"</Types>",
        b'<Override PartName="/xl/worksheets/sheet2.xml" '
        b'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        b"</Types>",
    )
    sheet2 = sheet1.replace(b"familia-silva", b"familia-oliveira").replace(
        b"Maria Silva", b"Ana Oliveira"
    )
    assert workbook != archive_workbook_sentinel()
    return rewrite(original, {
        "xl/workbook.xml": workbook,
        "xl/_rels/workbook.xml.rels": rels,
        "xl/worksheets/sheet2.xml": sheet2,
        "[Content_Types].xml": content_types,
    })


def archive_workbook_sentinel():
    # Somente para garantir que a troca de metadados alterou o conteúdo.
    with ZipFile(BytesIO(template_xlsx())) as archive:
        return archive.read("xl/workbook.xml")


def test_preview_uses_first_tab_even_if_its_xml_is_sheet2():
    workbook = first_sheet_is_sheet2()
    result, records = preview_xlsx(workbook, include_records=True)
    assert result["valid"] is True
    assert result["families"] == 1
    assert records[0]["key"] == "familia-oliveira"
    assert records[0]["name"] == "Ana Oliveira"


def test_authenticated_import_uses_visible_first_tab(client):
    csrf = login(client).json["csrf_token"]
    response = client.post(
        "/api/admin/guest-list-import", data=first_sheet_is_sheet2(),
        content_type=MIME, headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 200
    roster = client.get("/api/admin/invitations").json["families"]
    assert len(roster) == 1
    assert roster[0]["key"] == "familia-oliveira"
    assert roster[0]["name"] == "Ana Oliveira"


def test_missing_workbook_metadata_fails_closed():
    document = rewrite(template_xlsx(), removed=("xl/workbook.xml",))
    with pytest.raises(ValueError, match="Estrutura XLSX incompleta"):
        preview_xlsx(document)


def test_first_hidden_tab_is_rejected():
    source = template_xlsx()
    with ZipFile(BytesIO(source)) as archive:
        workbook = archive.read("xl/workbook.xml")
    workbook = workbook.replace(b'r:id="rId1"/>', b'r:id="rId1" state="hidden"/>')
    with pytest.raises(ValueError, match="precisa estar visível"):
        preview_xlsx(rewrite(source, {"xl/workbook.xml": workbook}))


@pytest.mark.parametrize("substitution,expected", [
    (b'TargetMode="External" Target="worksheets/sheet1.xml"',
     "Relacionamento da primeira aba Excel inválido"),
    (b'Target="../../invalid.xml"', "Primeira aba Excel não encontrada"),
    (b'Target="worksheets/nothere.xml"', "Primeira aba Excel não encontrada"),
])
def test_external_or_invalid_sheet_relationship_is_rejected(substitution, expected):
    source = template_xlsx()
    with ZipFile(BytesIO(source)) as archive:
        rels = archive.read("xl/_rels/workbook.xml.rels")
    rels = rels.replace(b'Target="worksheets/sheet1.xml"', substitution)
    with pytest.raises(ValueError, match=expected):
        preview_xlsx(rewrite(source, {"xl/_rels/workbook.xml.rels": rels}))


def test_unsafe_workbook_never_imports_partial_data(client):
    csrf = login(client).json["csrf_token"]
    source = template_xlsx()
    with ZipFile(BytesIO(source)) as archive:
        rels = archive.read("xl/_rels/workbook.xml.rels")
    rels = rels.replace(b'Target="worksheets/sheet1.xml"',
                        b'TargetMode="External" Target="https://wrong.invalid/data"')
    response = client.post("/api/admin/guest-list-import",
        data=rewrite(source, {"xl/_rels/workbook.xml.rels": rels}),
        content_type=MIME, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 422
    assert client.get("/api/admin/guest-list-summary").json["families"] == 0
