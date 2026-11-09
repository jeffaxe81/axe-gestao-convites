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

    # Opening a private invitation is not an interest event.
    guest = page.context.new_page()
    try:
        guest.goto(link)
        expect(guest.locator("#interest-btn")).to_be_visible()
        expect(guest.locator("#interest-btn")).to_be_enabled()
        page.locator("#invite-refresh-btn").click()
        expect(page.get_by_test_id("invite-interested")).to_have_text("0")

        guest.locator("#interest-btn").click()
        expect(guest.locator("#interest-btn")).to_be_disabled()
        page.locator("#invite-refresh-btn").click()
        expect(page.get_by_test_id("invite-interested")).to_have_text("1")
        expect(page.get_by_test_id("invite-pending")).to_have_text("1")
        expect(page.get_by_test_id("invite-sent")).to_have_text("0")
        expect(page.get_by_test_id("invite-confirmed")).to_have_text("0")
    finally:
        guest.close()

    page.locator("#logout-btn").click()
    expect(page.locator("#dashboard-panel")).to_be_hidden()
    expect(page.get_by_test_id("invite-interested")).to_have_text("0")
    expect(page.locator("#invite-list")).to_have_text("")
