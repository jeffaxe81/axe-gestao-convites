"""Mobile browser engines: Chromium/Android-like and WebKit/iPhone-like.

Emulação de navegador NÃO substitui testes em aparelhos físicos via WhatsApp.
"""
import pytest
from playwright.sync_api import expect, sync_playwright

from tests.e2e.test_guest import server


@pytest.mark.parametrize("engine,device", [
    ("chromium", "Pixel 5"),
    ("webkit", "iPhone 13"),
])
def test_mobile_visitor_responds_and_edits_in_both_engines(server, engine, device):
    origin, store = server
    with sync_playwright() as playwright:
        browser = getattr(playwright, engine).launch(headless=True)
        context = browser.new_context(**playwright.devices[device])
        page = context.new_page()
        try:
            page.goto(origin)
            expect(page.get_by_role("heading", name="Os 2 aninhos da Isadora")).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
            page.locator("#contact-name").fill("Convidado teste")
            page.locator("#add-companion").click()
            row = page.locator("#participants .person-row").nth(1)
            row.locator(".person-name").fill("Criança teste")
            row.locator(".person-kind").select_option("CHILD")
            row.locator(".person-age").fill("5")
            page.locator("#review-btn").click()
            expect(page.locator("#review-data")).to_contain_text("Criança teste")
            page.locator("#submit-btn").click()
            expect(page.locator("#success")).to_be_visible()
            link = page.locator("#edit-link").input_value()
            assert "/editar#" in link
            assert store.summary()["counts"].buffet == 1

            page.goto(link)
            expect(page.locator("#contact-name")).to_have_value("Convidado teste")
            page.locator("#participants .person-row").nth(1).locator(".person-age").fill("6")
            page.locator("#review-btn").click()
            page.locator("#submit-btn").click()
            expect(page.locator("#success")).to_be_visible()
            assert store.summary()["counts"].buffet == 2
            assert len(store.summary()["confirmed"]) == 1
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        finally:
            context.close()
            browser.close()


@pytest.mark.parametrize("engine,device", [
    ("chromium", "Pixel 5"),
    ("webkit", "iPhone 13"),
])
def test_mobile_offline_preserves_response_and_allows_retry(server, engine, device):
    origin, store = server
    with sync_playwright() as playwright:
        browser = getattr(playwright, engine).launch(headless=True)
        context = browser.new_context(**playwright.devices[device])
        page = context.new_page()
        try:
            page.goto(origin)
            page.locator("#contact-name").fill("Teste sem rede")
            page.locator("#review-btn").click()
            context.set_offline(True)
            expect(page.locator("#connection-status")).to_be_visible()
            page.locator("#submit-btn").click()
            expect(page.locator("#success")).to_be_hidden()
            expect(page.locator("#submit-btn")).to_be_enabled()
            assert store.summary()["counts"].total == 0
            context.set_offline(False)
            page.locator("#submit-btn").click()
            expect(page.locator("#success")).to_be_visible()
            assert store.summary()["counts"].total == 1
        finally:
            context.close()
            browser.close()
