"""Mobile-sized browser checks for operator-marked invitation sending."""
from playwright.sync_api import expect

from tests.e2e.test_guest import page
from tests.e2e.test_organizer import organizer_server, login


def test_operator_manual_send_is_distinct_from_reply_and_reversible(page, organizer_server):
    base, store = organizer_server
    store.import_invited_families([
        {"key": "familia-silva", "name": "Maria Silva", "phone": "11999999999",
         "adults": 2, "young": 1, "older": 0}
    ])
    login(page, base)
    expect(page.get_by_test_id("invite-total")).to_have_text("1")
    expect(page.get_by_test_id("invite-pending")).to_have_text("1")
    expect(page.get_by_test_id("invite-sent")).to_have_text("0")
    expect(page.get_by_test_id("invite-not-sent")).to_have_text("1")
    expect(page.locator("#invite-list")).to_contain_text("Envio não registrado")
    page.locator("#invite-list").get_by_role(
        "button", name="Marcar como enviado manualmente").click()
    expect(page.get_by_test_id("invite-sent")).to_have_text("1")
    expect(page.get_by_test_id("invite-not-sent")).to_have_text("0")
    expect(page.get_by_test_id("invite-pending")).to_have_text("1")
    expect(page.locator("#invite-list")).to_contain_text("Envio registrado manualmente")
    assert store.summary()["counts"].total == 0
    page.locator("#invite-sent-filter").select_option("NAO_ENVIADO")
    expect(page.locator("#invite-list")).to_contain_text("Nenhum registro")
    page.locator("#invite-sent-filter").select_option("ENVIADO")
    expect(page.locator("#invite-list")).to_contain_text("Maria Silva")
    page.locator("#invite-list").get_by_role(
        "button", name="Desfazer envio registrado").click()
    expect(page.get_by_test_id("invite-sent")).to_have_text("0")
    expect(page.get_by_test_id("invite-not-sent")).to_have_text("1")
    expect(page.locator("#invite-list")).to_contain_text("Nenhum registro")
    page.locator("#invite-sent-filter").select_option("TODOS")
    page.locator("#load-activity-btn").click()
    expect(page.locator("#activity-list")).to_contain_text("Envio de convite registrado manualmente")
    expect(page.locator("#activity-list")).to_contain_text("Registro manual de envio desfeito")
    page.locator("#logout-btn").click()
    expect(page.locator("#dashboard-panel")).to_be_hidden()
    expect(page.get_by_test_id("invite-total")).to_have_text("0")
    expect(page.get_by_test_id("invite-sent")).to_have_text("0")
    expect(page.locator("#invite-list")).to_have_text("")
