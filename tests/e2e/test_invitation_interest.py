"""Browser checks: explicit opt-in interest must never be confused with page views or RSVP."""
from playwright.sync_api import expect

from tests.e2e.test_guest import page, server


def test_invitation_interest_requires_click_and_survives_reload(page, server):
    base, store = server
    store.import_invited_families([{
        "key": "familia-interesse", "name": "Maria Silva",
        "phone": "11999999999", "adults": 2, "young": 0, "older": 0
    }])
    invited = store.invitation_roster()[0]
    link = base + "/convite#" + invited["id"] + "." + invited["token"]

    page.goto(link)
    expect(page.locator("#invitation-interest")).to_be_visible()
    button = page.locator("#interest-btn")
    expect(button).to_be_enabled()
    assert store.invitation_overview()["counts"]["interested"] == 0

    # Page reload is not consent and cannot increment the counter.
    page.reload()
    expect(page.locator("#invitation-interest")).to_be_visible()
    expect(page.locator("#interest-btn")).to_be_enabled()
    assert store.invitation_overview()["counts"]["interested"] == 0

    page.locator("#interest-btn").click()
    expect(page.locator("#interest-btn")).to_be_disabled()
    expect(page.locator("#interest-status")).to_contain_text(
        "sem confirmar presença")
    counts = store.invitation_overview()["counts"]
    assert counts["interested"] == 1
    assert counts["pending"] == 1
    assert counts["confirmed"] == 0

    page.reload()
    expect(page.locator("#interest-btn")).to_be_disabled()
    expect(page.locator("#interest-btn")).to_contain_text("Interesse registrado")
    assert store.invitation_overview()["counts"]["interested"] == 1
    assert store.summary()["counts"].total == 0
