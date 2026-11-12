"""Hidden Excel column metadata: strict bounds and safe import failure."""
import pytest

from app.guest_list import preview_xlsx
from tests.integration.test_public_api import store
from tests.integration.test_organizer_api import client, login
from tests.integration.test_xlsx_hidden_and_duplicates import modified_sheet

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def with_columns(minimum: bytes, maximum: bytes) -> bytes:
    fragment = (b'<cols><col min="' + minimum + b'" max="' +
                maximum + b'" hidden="1"/></cols><sheetData>')
    return modified_sheet(b"<sheetData>", fragment)


@pytest.mark.parametrize(("minimum", "maximum"), [
    (b"0", b"6"), (b"-1", b"6"), (b"7", b"6"),
    (b"1", b"16385"), (b"1", b"99999999"),
    (b"segredo-pessoal", b"9"), (b"7", b"9" * 5000),
    (b"00001", b"3"), ("١".encode("utf-8"), b"3"),
], ids=[
    "zero", "negative", "inverted", "outside-excel",
    "overlong-number", "invalid-text", "huge-number",
    "noncanonical", "unicode-number",
])
def test_invalid_hidden_column_limits_are_rejected_without_echo(minimum, maximum):
    with pytest.raises(ValueError, match="Definição de coluna oculta inválida") as error:
        preview_xlsx(with_columns(minimum, maximum))
    assert "segredo-pessoal" not in str(error.value)


def test_last_excel_column_hidden_does_not_affect_required_columns():
    assert preview_xlsx(with_columns(b"16384", b"16384"))["valid"] is True


@pytest.mark.parametrize(("minimum", "maximum"), [
    (b"7", b"9" * 5000),
    (b"1", b"16385"),
    (b"segredo-pessoal", b"9"),
], ids=["huge", "out-of-range", "text"])
def test_invalid_column_metadata_returns_422_without_saving(client, minimum, maximum):
    csrf = login(client).json["csrf_token"]
    response = client.post(
        "/api/admin/guest-list-import", data=with_columns(minimum, maximum),
        content_type=XLSX, headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 422
    assert response.json["error"]["code"] == "INVALID_INPUT"
    assert "segredo-pessoal" not in response.get_data(as_text=True)
    assert client.get("/api/admin/guest-list-summary").json["families"] == 0
    assert client.get("/api/admin/dashboard").json["counts"]["total"] == 0
