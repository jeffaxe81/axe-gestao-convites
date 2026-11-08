"""E2E do histórico privado, impressão e resumo para fornecedores."""
from playwright.sync_api import expect

from tests.e2e.test_guest import page
from tests.e2e.test_organizer import organizer_server, login


def test_activity_load_and_logout_clears_private_view(page, organizer_server):
    base, _store = organizer_server
    login(page, base)
    expect(page.get_by_test_id("total-count")).to_have_text("3")
    page.locator("#load-activity-btn").click()
    expect(page.locator("#activity-list")).to_contain_text("Confirmação recebida")
    assert "João" not in page.locator("#activity-list").inner_text()
    page.locator("#logout-btn").click()
    expect(page.locator("#dashboard-panel")).to_be_hidden()
    assert page.locator("#activity-list").inner_text() == ""


def test_quantities_report_does_not_contain_invitee_names(page, organizer_server, tmp_path):
    base, _store = organizer_server
    login(page, base)
    expect(page.get_by_test_id("total-count")).to_have_text("3")
    with page.expect_download() as received:
        page.locator("#export-planning-btn").click()
    download = received.value
    assert download.suggested_filename == "isadora-resumo-buffet.csv"
    output = tmp_path / "resumo.csv"
    download.save_as(output)
    contents = output.read_text("utf-8-sig")
    assert "Pessoas para buffet" in contents
    assert "Lembrancinhas" not in contents  # Descrição genérica, sem dados de convidados
    assert "João" not in contents and "Nina" not in contents
    expect(page.locator("#planning-status")).to_contain_text("sem nomes")


def test_print_button_uses_browser_only(page, organizer_server):
    base, _store = organizer_server
    login(page, base)
    expect(page.get_by_test_id("total-count")).to_have_text("3")
    page.evaluate("window.__printInvoked = false; window.print = () => { window.__printInvoked = true; }")
    page.locator("#print-list-btn").click()
    assert page.evaluate("window.__printInvoked") is True
