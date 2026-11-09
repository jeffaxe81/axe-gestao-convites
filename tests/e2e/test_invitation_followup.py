"""Chromium: invitation-interest filter and private follow-up CSV download."""
from datetime import datetime, timezone

from playwright.sync_api import expect

from tests.e2e.test_guest import page
from tests.e2e.test_organizer import organizer_server, login


def test_interest_filter_and_export_work_without_modifying_global_metrics(page, organizer_server, tmp_path):
    base, store = organizer_server
    store.import_invited_families([
        {"key": "familia-maria", "name": "Maria Silva", "phone": "",
         "adults": 2, "young": 0, "older": 0},
        {"key": "familia-joao", "name": "João Souza", "phone": "",
         "adults": 2, "young": 0, "older": 0},
    ])
    family = next(row for row in store.invitation_roster() if row["key"] == "familia-maria")
    store.express_invitation_interest(family["id"], family["token"], datetime.now(timezone.utc))
    login(page, base)
    expect(page.get_by_test_id("invite-total")).to_have_text("2")
    expect(page.get_by_test_id("invite-interested")).to_have_text("1")
    page.locator("#invite-interest-filter").select_option("INTERESSADO")
    expect(page.locator("#invite-list li")).to_have_count(1)
    expect(page.locator("#invite-list")).to_contain_text("Maria Silva")
    page.locator("#invite-interest-filter").select_option("NAO_INTERESSADO")
    expect(page.locator("#invite-list li")).to_have_count(1)
    expect(page.locator("#invite-list")).to_contain_text("João Souza")
    expect(page.get_by_test_id("invite-total")).to_have_text("2")
    expect(page.get_by_test_id("invite-interested")).to_have_text("1")
    with page.expect_download() as info:
        page.locator("#invite-followup-export-btn").click()
    download = info.value
    assert download.suggested_filename == "acompanhamento-convites.csv"
    target = tmp_path / "acompanhamento.csv"
    download.save_as(target)
    data = target.read_text("utf-8-sig")
    assert "Maria Silva" in data and "João Souza" in data
    assert "Interesse voluntario" in data
    assert "/convite#" not in data
    expect(page.locator("#invite-followup-export-status")).to_contain_text("Relatório exportado")
    page.locator("#logout-btn").click()
    expect(page.locator("#invite-interest-filter")).to_have_value("TODOS")
    expect(page.locator("#invite-followup-export-status")).to_have_text("")
    expect(page.locator("#dashboard-panel")).to_be_hidden()
