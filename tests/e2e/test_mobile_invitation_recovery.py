"""Real individual-invitation mobile flows under intermittent connectivity.

Chromium/Android-like and WebKit/iPhone-like emulation are automated checks,
not evidence from real devices. Uses only fictional names and temporary storage.
"""
import pytest
from playwright.sync_api import expect, sync_playwright

from tests.e2e.test_guest import server


MOBILE_DEVICES = [("chromium", "Pixel 5"), ("webkit", "iPhone 13")]


def _invite(store, origin):
    store.import_invited_families([{
        "key": "familia-rede-teste", "name": "Pessoa Rede Teste",
        "phone": "11999990001", "adults": 1, "young": 0, "older": 0,
    }])
    family = store.invitation_roster()[0]
    return origin + "/convite#" + family["id"] + "." + family["token"]


def _mobile(playwright, engine, device):
    browser = getattr(playwright, engine).launch(headless=True)
    context = browser.new_context(**playwright.devices[device])
    return browser, context, context.new_page()


@pytest.mark.parametrize("engine,device", MOBILE_DEVICES)
def test_individual_mobile_invitation_offline_then_online_is_single_rsvp(
    server, engine, device
):
    origin, store = server
    link = _invite(store, origin)
    with sync_playwright() as playwright:
        browser, context, page = _mobile(playwright, engine, device)
        try:
            page.goto(link)
            expect(page.locator("#contact-name")).to_have_value("Pessoa Rede Teste")
            expect(page.locator("#invitation-plan")).to_be_visible()
            page.locator("#review-btn").click()
            expect(page.locator("#review")).to_be_visible()
            context.set_offline(True)
            expect(page.locator("#connection-status")).to_be_visible()
            page.locator("#submit-btn").click()
            expect(page.locator("#error")).to_contain_text("Sem conexão")
            expect(page.locator("#submit-btn")).to_be_enabled()
            expect(page.locator("#success")).to_be_hidden()
            assert store.summary()["counts"].total == 0

            context.set_offline(False)
            page.locator("#submit-btn").click()
            expect(page.locator("#success")).to_be_visible()
            edit_link = page.locator("#edit-link").input_value()
            assert "/editar#" in edit_link
            assert len(store.summary()["confirmed"]) == 1
            assert store.summary()["counts"].total == 1

            # Same individual invitation is idempotent when reopened.
            page.goto(link)
            expect(page.locator("#success")).to_be_visible()
            expect(page.locator("#edit-link")).to_have_value(edit_link)
            assert len(store.summary()["confirmed"]) == 1
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        finally:
            context.close()
            browser.close()


@pytest.mark.parametrize("engine,device", MOBILE_DEVICES)
def test_individual_mobile_invitation_lost_reply_retry_does_not_duplicate(
    server, engine, device
):
    origin, store = server
    link = _invite(store, origin)
    with sync_playwright() as playwright:
        browser, context, page = _mobile(playwright, engine, device)
        try:
            page.goto(link)
            expect(page.locator("#contact-name")).to_have_value("Pessoa Rede Teste")
            page.locator("#review-btn").click()
            delivered_to_server = []

            def drop_only_response(route):
                # Server commits the response, but the mobile browser loses the
                # HTTP reply. A subsequent retry must return the same receipt.
                response = route.fetch()
                delivered_to_server.append(response.status)
                route.abort("failed")

            pattern = "**/api/invitations/*/response"
            page.route(pattern, drop_only_response)
            page.locator("#submit-btn").click()
            expect(page.locator("#error")).to_be_visible()
            expect(page.locator("#submit-btn")).to_be_enabled()
            expect(page.locator("#success")).to_be_hidden()
            assert delivered_to_server == [200]
            assert store.summary()["counts"].total == 1

            page.unroute(pattern)
            page.locator("#submit-btn").click()
            expect(page.locator("#success")).to_be_visible()
            assert len(store.summary()["confirmed"]) == 1
            assert store.summary()["counts"].total == 1
            receipt_link = page.locator("#edit-link").input_value()
            assert "/editar#" in receipt_link

            page.goto(link)
            expect(page.locator("#edit-link")).to_have_value(receipt_link)
            assert store.invited_family_summary()["pending"] == 0
        finally:
            context.close()
            browser.close()


@pytest.mark.parametrize("engine,device", MOBILE_DEVICES)
def test_reopened_mobile_invitation_rejects_incomplete_saved_receipt(
    server, engine, device
):
    """A damaged saved receipt must not claim success or expose a broken edit link."""
    origin, store = server
    link = _invite(store, origin)
    with sync_playwright() as playwright:
        browser, context, page = _mobile(playwright, engine, device)
        try:
            page.goto(link)
            expect(page.locator("#contact-name")).to_have_value("Pessoa Rede Teste")
            page.locator("#review-btn").click()
            page.locator("#submit-btn").click()
            expect(page.locator("#success")).to_be_visible()
            edit_link = page.locator("#edit-link").input_value()

            def damage_saved_receipt(route):
                response = route.fetch()
                data = response.json()
                # Preserve the real invitation and saved response, but simulate
                # an intermediary dropping the secret needed to edit it.
                del data["receipt"]["edit_token"]
                route.fulfill(response=response, json=data)

            pattern = "**/api/invitations/*"
            page.route(pattern, damage_saved_receipt)
            page.reload()
            expect(page.locator("#error")).to_contain_text("Não foi possível verificar")
            expect(page.locator("#success")).to_be_hidden()
            expect(page.locator("#rsvp-form")).to_be_hidden()
            assert store.summary()["counts"].total == 1

            page.unroute(pattern)
            page.reload()
            expect(page.locator("#success")).to_be_visible()
            expect(page.locator("#edit-link")).to_have_value(edit_link)
            assert len(store.summary()["confirmed"]) == 1
        finally:
            context.close()
            browser.close()
