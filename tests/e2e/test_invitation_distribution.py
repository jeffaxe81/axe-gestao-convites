"""Browser verification of safe manual WhatsApp sharing and pending-family filters."""
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import expect

from tests.e2e.test_guest import page
from tests.e2e.test_organizer import organizer_server, login


def test_manual_whatsapp_preparation_and_filters(page, organizer_server, monkeypatch):
    base, store = organizer_server
    store.import_invited_families([
        {"key": "familia-maria", "name": "Maria Silva",
         "phone": "11999999999", "adults": 2, "young": 1, "older": 0},
        {"key": "familia-joao", "name": "João Souza",
         "phone": "", "adults": 1, "young": 0, "older": 0}
    ])
    monkeypatch.setenv("APP_PUBLIC_URL", "https://isadora2anos.org")
    login(page, base)
    expect(page.get_by_test_id("invite-total")).to_have_text("2")
    expect(page.get_by_test_id("invite-pending")).to_have_text("2")
    expect(page.locator("#invite-list")).to_contain_text("Maria Silva")
    page.locator("#invite-search").fill("maria")
    expect(page.locator("#invite-list li")).to_have_count(1)
    row = page.locator("#invite-list li").first
    row.get_by_role("button", name="Preparar WhatsApp").click()
    link = row.get_by_role("link", name="Abrir conversa no WhatsApp")
    expect(link).to_be_visible()
    url = urlparse(link.get_attribute("href"))
    assert url.netloc == "wa.me"
    assert url.path == "/5511999999999"
    message = parse_qs(url.query)["text"][0]
    assert "https://isadora2anos.org/convite#" in message
    assert "Maria Silva" in message
    expect(row).to_contain_text("Nenhuma mensagem foi enviada")
    page.locator("#invite-search").fill("joao")
    expect(page.locator("#invite-list li")).to_have_count(1)
    row = page.locator("#invite-list li").first
    row.get_by_role("button", name="Preparar WhatsApp").click()
    expect(row).to_contain_text("Telefone ausente")
    expect(row.get_by_role("link", name="Abrir conversa no WhatsApp")).to_have_count(0)
    page.locator("#invite-status-filter").select_option("CONFIRMADO")
    expect(page.locator("#invite-list")).to_contain_text("Nenhum registro")
    page.locator("#logout-btn").click()
    expect(page.locator("#dashboard-panel")).to_be_hidden()
    expect(page.locator("#invite-list")).to_have_text("")
    expect(page.get_by_test_id("invite-total")).to_have_text("0")
