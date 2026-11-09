"""Mobile WebKit smoke check for Safari-like rendering (not a physical iPhone)."""
from playwright.sync_api import expect, sync_playwright
from tests.e2e.test_organizer import organizer_server, login


def test_mobile_webkit_manual_dispatch_has_safe_layout(organizer_server):
    base, store = organizer_server
    store.import_invited_families([{
        "key": "familia-webkit", "name": "Família WebKit",
        "phone": "11999999999", "adults": 1, "young": 0, "older": 0
    }])
    before = store.summary()["counts"].total
    with sync_playwright() as playwright:
        browser = playwright.webkit.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844},
                                    is_mobile=True, has_touch=True)
            login(page, base)
            expect(page.get_by_test_id("invite-total")).to_have_text("1")
            expect(page.get_by_test_id("invite-sent")).to_have_text("0")
            expect(page.locator("#invite-list")).to_contain_text("Família WebKit")
            assert page.evaluate(
                "() => document.documentElement.scrollWidth <= window.innerWidth + 2")
            page.locator("#invite-list").get_by_role(
                "button", name="Marcar como enviado manualmente").click()
            expect(page.get_by_test_id("invite-sent")).to_have_text("1")
            expect(page.get_by_test_id("invite-pending")).to_have_text("1")
            assert store.summary()["counts"].total == before
            page.locator("#logout-btn").click()
            expect(page.locator("#dashboard-panel")).to_be_hidden()
            expect(page.get_by_test_id("invite-sent")).to_have_text("0")
        finally:
            browser.close()
