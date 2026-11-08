"""A stalled POST never leaves the guest locked on 'Enviando...'."""
from playwright.sync_api import expect

from tests.e2e.test_guest import page, server


def test_stalled_post_timeout_releases_button_and_retains_idempotency(page, server):
    origin, store = server
    page.clock.install()
    page.goto(origin)
    page.locator("#contact-name").fill("Ana teste")
    page.locator("#review-btn").click()

    # Intercept and intentionally never forward request to the server.
    pattern = "**/api/rsvps"
    page.route(pattern, lambda route: None)
    page.locator("#submit-btn").click()
    expect(page.locator("#submit-btn")).to_be_disabled()
    page.clock.fast_forward(15100)
    expect(page.locator("#error")).to_contain_text("A conexão demorou a responder")
    expect(page.locator("#submit-btn")).to_be_enabled()
    expect(page.locator("#success")).to_be_hidden()
    assert store.summary()["counts"].total == 0
    key = page.evaluate("sessionStorage.getItem('isadora_submission_key')")
    assert isinstance(key, str) and len(key) >= 16

    page.unroute(pattern)
    page.locator("#submit-btn").click()
    expect(page.locator("#success")).to_be_visible()
    assert store.summary()["counts"].total == 1
    assert page.evaluate("sessionStorage.getItem('isadora_submission_key')") is None
