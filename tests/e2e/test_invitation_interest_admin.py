"""Browser proof: organizer interest metric stays separate from RSVP and manual sending."""
from playwright.sync_api import expect

from tests.e2e.test_guest import page
from tests.e2e.test_organizer import organizer_server, login


def test_organizer_sees_voluntary_interest_without_confirming_attendance(page, organizer_server):
    base, store = organizer_server
    store.import_invited_families([{
        "key": "familia-teste-interesse", "name": "Maria Silva",
        "phone": "11999999999", "adults": 2, "young": 0, "older": 0,
    }])
    family = store.invitation_roster()[0]
    link = base + "/convite#" + family["id"] + "." + family["token"]

    login(page, base)
    expect(page.get_by_test_id("invite-total")).to_have_text("1")
    expect(page.get_by_test_id("invite-interested")).to_have_text("0")
    expect(page.get_by_test_id("invite-pending")).to_have_text("1")
    expect(page.get_by_test_id("invite-sent")).to_have_text("0")

    # Use the same browser tab: this project's fixture owns a browser.new_page()
    # context that intentionally does not allow context.new_page().
    page.goto(link)
    expect(page.locator("#interest-btn")).to_be_visible()
    expect(page.locator("#interest-btn")).to_be_enabled()
    assert store.invitation_overview()["counts"]["interested"] == 0
    page.locator("#interest-btn").click()
    expect(page.locator("#interest-btn")).to_be_disabled()
    assert store.invitation_overview()["counts"]["interested"] == 1

    # The organizer session survives navigation to the guest invitation.
    page.goto(base + "/organizar")
    expect(page.get_by_test_id("invite-interested")).to_have_text("1")
    expect(page.get_by_test_id("invite-pending")).to_have_text("1")
    expect(page.get_by_test_id("invite-sent")).to_have_text("0")
    expect(page.get_by_test_id("invite-confirmed")).to_have_text("0")

    page.locator("#logout-btn").click()
    expect(page.locator("#dashboard-panel")).to_be_hidden()
    expect(page.get_by_test_id("invite-interested")).to_have_text("0")
    expect(page.locator("#invite-list")).to_have_text("")
