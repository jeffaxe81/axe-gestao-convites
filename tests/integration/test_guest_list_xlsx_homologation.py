"""Excel family-list acceptance checks: authenticated download through atomic import."""
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED

from app.guest_xlsx_template import template_xlsx
from app.guest_list import preview_xlsx
from tests.integration.test_public_api import store
from tests.integration.test_organizer_api import client, login


XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
IMPORT_URL = "/api/admin/guest-list-import"
TEMPLATE_URL = "/api/admin/guest-list-template.xlsx"


def altered_sheet(original, old, new):
    """Make a test-only workbook change without depending on Excel or openpyxl."""
    output = BytesIO()
    with ZipFile(BytesIO(original)) as source:
        with ZipFile(output, "w", ZIP_DEFLATED) as target:
            for member in source.infolist():
                data = source.read(member.filename)
                if member.filename == "xl/worksheets/sheet1.xml":
                    assert old in data
                    data = data.replace(old, new, 1)
                target.writestr(member.filename, data)
    return output.getvalue()


def test_excel_download_requires_login_and_import_requires_csrf(client):
    assert client.get(TEMPLATE_URL).status_code == 401
    assert client.post(IMPORT_URL, data=template_xlsx(), content_type=XLSX_MIME).status_code == 401

    auth = login(client).json
    response = client.get(TEMPLATE_URL)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store, private"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Content-Disposition"].startswith("attachment;")
    assert response.data.startswith(b"PK")
    assert preview_xlsx(response.data)["valid"] is True

    forbidden = client.post(IMPORT_URL, data=response.data, content_type=XLSX_MIME)
    assert forbidden.status_code == 403
    assert client.get("/api/admin/guest-list-summary").json["families"] == 0


def test_downloaded_excel_import_is_atomic_idempotent_and_does_not_confirm(client):
    token = login(client).json["csrf_token"]
    headers = {"X-CSRF-Token": token}
    downloaded = client.get(TEMPLATE_URL).data

    first = client.post(IMPORT_URL, data=downloaded, content_type=XLSX_MIME, headers=headers)
    assert first.status_code == 200
    assert first.json == {"imported": 1, "existing_unchanged": 0, "total_in_file": 1}

    repeated = client.post(IMPORT_URL, data=downloaded, content_type=XLSX_MIME, headers=headers)
    assert repeated.status_code == 200
    assert repeated.json == {"imported": 0, "existing_unchanged": 1, "total_in_file": 1}

    overview = client.get("/api/admin/guest-list-summary").json
    assert overview["families"] == 1
    assert overview["pending"] == 1
    assert client.get("/api/admin/dashboard").json["counts"]["total"] == 0

    changed = altered_sheet(downloaded, b"Maria Silva", b"Pessoa Diferente")
    conflict = client.post(IMPORT_URL, data=changed, content_type=XLSX_MIME, headers=headers)
    assert conflict.status_code == 422
    assert client.get("/api/admin/guest-list-summary").json["families"] == 1


def test_formula_in_excel_cannot_import_or_create_family(client):
    token = login(client).json["csrf_token"]
    headers = {"X-CSRF-Token": token}
    template = template_xlsx()
    malicious = altered_sheet(
        template,
        b'<c r="D2" t="inlineStr"><is><t>2</t></is></c>',
        b'<c r="D2"><f>1+1</f><v>2</v></c>',
    )
    response = client.post(IMPORT_URL, data=malicious, content_type=XLSX_MIME, headers=headers)
    assert response.status_code == 422
    assert "fórmula" in response.json["error"]["message"].lower()
    assert client.get("/api/admin/guest-list-summary").json["families"] == 0
