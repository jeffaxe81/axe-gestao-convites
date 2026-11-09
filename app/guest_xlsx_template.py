"""Create an Excel template with the same six columns accepted by guest-list import.

Uses the Python standard library and contains only fictitious sample data.
"""
from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

from app.guest_list import HEADERS, EXAMPLE

XML = '<?xml version="1.0" encoding="UTF-8"?>'
SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def template_xlsx():
    """Return a small, formula-free .xlsx compatible with the existing preview reader."""
    def row_xml(number, values):
        cells = "".join(
            '<c r="' + chr(65 + index) + str(number)
            + '" t="inlineStr"><is><t>' + escape(value)
            + '</t></is></c>'
            for index, value in enumerate(values)
        )
        return '<row r="' + str(number) + '">' + cells + '</row>'

    sheet = (
        XML + '<worksheet xmlns="' + SHEET_NS + '"><sheetData>'
        + row_xml(1, HEADERS) + row_xml(2, EXAMPLE)
        + '</sheetData></worksheet>'
    )
    workbook = (
        XML + '<workbook xmlns="' + SHEET_NS + '" xmlns:r="' + REL_NS
        + '"><sheets><sheet name="Familias" sheetId="1" r:id="rId1"/>'
        + '</sheets></workbook>'
    )
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", (
            XML + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            + '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            + '<Default Extension="xml" ContentType="application/xml"/>'
            + '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            + '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            + '</Types>'
        ))
        archive.writestr("_rels/.rels", (
            XML + '<Relationships xmlns="' + PACKAGE_REL_NS + '">'
            + '<Relationship Id="rId1" Type="' + REL_NS
            + '/officeDocument" Target="xl/workbook.xml"/></Relationships>'
        ))
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", (
            XML + '<Relationships xmlns="' + PACKAGE_REL_NS + '">'
            + '<Relationship Id="rId1" Type="' + REL_NS
            + '/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'
        ))
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return buffer.getvalue()
