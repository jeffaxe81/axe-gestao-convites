"""Cross-format family identity: imports must be additive, atomic and never RSVP writes.

All inputs are fictional. No messaging, production credentials or host access.
"""
import pytest

from app.guest_list import HEADERS, preview_csv, preview_xlsx
from tests.integration.test_guest_list_preview import excel
from tests.integration.test_organizer_api import client, login
from tests.integration.test_public_api import store

CSV_MIME = "text/csv"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
IMPORT = "/api/admin/guest-list-import"
HEADERS_LIST = list(HEADERS)
ALFA = ["familia-alfa", "Pessoa Alfa", "11999990001", "1", "1", "0"]
BETA = ["familia-beta", "Pessoa Beta", "11999990002", "2", "0", "0"]


def csv_bytes(*families):
    return ("\r\n".join(";".join(row) for row in (HEADERS_LIST, *families))
            + "\r\n").encode("utf-8")


def xlsx_bytes(*families):
    return excel([HEADERS_LIST, *families])


def import_file(client, token, content, mime):
    return client.post(IMPORT, data=content, content_type=mime,
                       headers={"X-CSRF-Token": token})


def roster(client):
    response = client.get("/api/admin/invitations")
    assert response.status_code == 200
    return {row["key"]: row for row in response.json["families"]}


def secret_link(client, family_id):
    response = client.get(f"/api/admin/invitations/{family_id}/link")
    assert response.status_code == 200
    assert "no-store" in response.headers["Cache-Control"]
    return response.json["url"]


def test_csv_to_xlsx_reimport_keeps_family_links_rsvp_and_dispatch(client, store, monkeypatch):
    monkeypatch.setenv("APP_PUBLIC_URL", "https://isadora2anos.org")
    csrf = login(client).json["csrf_token"]
    first = import_file(client, csrf, csv_bytes(ALFA, BETA), CSV_MIME)
    assert first.status_code == 200
    assert first.json == {"imported": 2, "existing_unchanged": 0, "total_in_file": 2}

    before = roster(client)
    alfa, beta = before["familia-alfa"], before["familia-beta"]
    original_links = {key: secret_link(client, row["id"]) for key, row in before.items()}
    assert original_links["familia-alfa"] != original_links["familia-beta"]

    marked = client.put(f"/api/admin/invitations/{alfa['id']}/sent",
                        headers={"X-CSRF-Token": csrf}, json={"sent": True})
    assert marked.status_code == 200
    interested = client.post(f"/api/invitations/{beta['id']}/interest",
                             headers={"Authorization": "Bearer " +
                                      store.invitation_token(beta["id"])})
    assert interested.status_code == 200

    payload = {"contact_name": "Pessoa Alfa", "attending": True,
               "participants": [
                   {"name": "Pessoa Alfa", "kind": "OVER_12", "age_years": None},
                   {"name": "Crianca Ficticia", "kind": "CHILD", "age_years": 5},
               ]}
    confirmed = client.post(f"/api/invitations/{alfa['id']}/response",
                            headers={"Authorization": "Bearer " +
                                     store.invitation_token(alfa["id"])},
                            json=payload)
    assert confirmed.status_code == 200
    original_receipt = confirmed.json

    # Importing the same people in another file format must be a no-op.
    second = import_file(client, csrf, xlsx_bytes(ALFA, BETA), XLSX_MIME)
    assert second.status_code == 200
    assert second.json == {"imported": 0, "existing_unchanged": 2, "total_in_file": 2}
    after = roster(client)
    assert set(after) == set(before)
    for key, prior in before.items():
        assert after[key]["id"] == prior["id"]
        assert secret_link(client, after[key]["id"]) == original_links[key]

    assert after["familia-alfa"]["status"] == "CONFIRMADO"
    assert after["familia-alfa"]["sent"] is True
    assert after["familia-alfa"]["sent_at_utc"] == marked.json["sent_at_utc"]
    assert after["familia-beta"]["status"] == "PENDENTE"
    assert after["familia-beta"]["interested"] is True
    assert store.summary()["counts"].total == 2
    read_again = client.get(f"/api/invitations/{alfa['id']}",
                            headers={"Authorization": "Bearer " +
                                     store.invitation_token(alfa["id"])})
    assert read_again.status_code == 200
    assert read_again.json["receipt"] == original_receipt
    assert original_receipt["edit_token"] not in str(client.get("/api/admin/invitations").json)


@pytest.mark.parametrize("mime,encode", [
    (CSV_MIME, csv_bytes),
    (XLSX_MIME, xlsx_bytes),
])
def test_mixed_new_and_conflicting_existing_family_rolls_back_entire_import(
    client, store, monkeypatch, mime, encode
):
    monkeypatch.setenv("APP_PUBLIC_URL", "https://isadora2anos.org")
    csrf = login(client).json["csrf_token"]
    assert import_file(client, csrf, csv_bytes(ALFA), CSV_MIME).status_code == 200
    before = roster(client)
    link_before = secret_link(client, before["familia-alfa"]["id"])

    # First row is brand-new; second row conflicts with the existing key.
    # Neither partial creation nor mutation may survive a failed transaction.
    conflicting = [ALFA[0], "Pessoa Alterada", *ALFA[2:]]
    result = import_file(client, csrf, encode(BETA, conflicting), mime)
    assert result.status_code == 422
    assert roster(client) == before
    assert secret_link(client, before["familia-alfa"]["id"]) == link_before
    assert client.get("/api/admin/guest-list-summary").json["families"] == 1
    assert store.summary()["counts"].total == 0


@pytest.mark.parametrize("mime,encode,preview", [
    (CSV_MIME, csv_bytes, preview_csv),
    (XLSX_MIME, xlsx_bytes, preview_xlsx),
])
def test_casefold_duplicate_keys_rejected_before_any_family_write(
    client, mime, encode, preview
):
    family_upper = ["FAMILIA-ALFA", "Pessoa A", "11999990001", "1", "0", "0"]
    family_lower = ["familia-alfa", "Pessoa B", "11999990002", "1", "0", "0"]
    document = encode(family_upper, family_lower)
    report = preview(document)
    assert report["valid"] is False
    assert any("duplicada" in item for item in report["errors"])
    csrf = login(client).json["csrf_token"]
    result = import_file(client, csrf, document, mime)
    # Invalid row set is reported rather than saved.
    assert result.status_code == 422
    assert client.get("/api/admin/guest-list-summary").json["families"] == 0
    assert client.get("/api/admin/invitations").json["counts"]["total"] == 0
