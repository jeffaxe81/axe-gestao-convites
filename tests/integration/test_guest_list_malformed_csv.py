"""Malformed CSV headers receive validation errors before any family is saved."""
import pytest

from tests.integration.test_public_api import store
from tests.integration.test_organizer_api import client, login


@pytest.mark.parametrize("endpoint", [
    "/api/admin/guest-list-preview",
    "/api/admin/guest-list-import",
])
@pytest.mark.parametrize("payload", [
    b'"familia;responsavel;telefone;adultos;criancas_0_5;criancas_6_12\n',
    b'"familia"invalid;responsavel;telefone;adultos;criancas_0_5;criancas_6_12\n',
])
def test_malformed_csv_header_returns_422_without_saving(client, endpoint, payload):
    token = login(client).json["csrf_token"]
    response = client.post(
        endpoint, data=payload, content_type="text/csv",
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 422
    assert "CSV malformado" in response.json["error"]["message"]
    assert client.get("/api/admin/guest-list-summary").json["families"] == 0
    assert client.get("/api/admin/dashboard").json["counts"]["total"] == 0
