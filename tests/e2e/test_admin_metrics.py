"""Organizador: famílias confirmadas/recusadas e crianças 6–12 no painel."""
from datetime import datetime, timezone
from playwright.sync_api import expect

from app.domain import validate_rsvp
from tests.e2e.test_guest import page
from tests.e2e.test_organizer import organizer_server, login


def test_new_metrics_and_private_reset(page, organizer_server):
    base, store = organizer_server
    store.create(validate_rsvp({
        "contact_name": "Recusou", "attending": False, "participants": []
    }), "declined-family-improvements-00001", datetime.now(timezone.utc))
    login(page, base)
    expect(page.get_by_test_id("middle-count")).to_have_text("1")
    expect(page.get_by_test_id("confirmed-families")).to_have_text("1")
    expect(page.get_by_test_id("declined-families")).to_have_text("1")
    page.locator("#logout-btn").click()
    expect(page.locator("#dashboard-panel")).to_be_hidden()
    for key in ("middle-count", "confirmed-families", "declined-families"):
        expect(page.get_by_test_id(key)).to_have_text("0")


def test_search_does_not_mutate_group_metrics(page, organizer_server):
    base, _ = organizer_server
    login(page, base)
    expect(page.get_by_test_id("middle-count")).to_have_text("1")
    page.locator("#guest-search").fill("inexistente")
    expect(page.locator("#search-summary")).to_contain_text("0 de 1 respostas")
    expect(page.get_by_test_id("middle-count")).to_have_text("1")
    expect(page.get_by_test_id("confirmed-families")).to_have_text("1")
