"""Fluxo de download privado no navegador Chromium."""
from playwright.sync_api import expect

from tests.e2e.test_guest import page
from tests.e2e.test_organizer import organizer_server, login


def test_organizer_downloads_csv_from_dashboard(page, organizer_server, tmp_path):
    base, _store = organizer_server
    login(page, base)
    expect(page.locator("#export-csv-btn")).to_be_visible()
    with page.expect_download() as info:
        page.locator("#export-csv-btn").click()
    download = info.value
    assert download.suggested_filename == "isadora-confirmacoes.csv"
    target = tmp_path / "relatorio.csv"
    download.save_as(target)
    content = target.read_text("utf-8-sig")
    assert "João" in content
    assert "Nina" in content
    assert "Confirmado" in content
    expect(page.locator("#export-status")).to_contain_text("download")


def test_organizer_does_not_export_when_logged_out(page, organizer_server):
    base, _store = organizer_server
    login(page, base)
    expect(page.locator("#export-csv-btn")).to_be_visible()
    page.locator("#logout-btn").click()
    expect(page.locator("#dashboard-panel")).to_be_hidden()
    assert page.request.get(base + "/api/admin/export.csv").status == 401
