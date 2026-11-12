"""Regressão visual: 403 e 409 não podem orientar o convidado de forma errada."""
from playwright.sync_api import expect

from tests.e2e.test_guest import page, server


def test_generic_rsvp_invitation_required_gives_correct_guidance(page, server):
    base, store = server
    page.goto(base)
    page.locator("#contact-name").fill("Ana")
    page.locator("#review-btn").click()
    page.route("**/api/rsvps", lambda route: route.fulfill(
        status=403, content_type="application/json",
        body='{"error":{"code":"INVITATION_REQUIRED","message":"Convite individual necessário."}}',
    ))
    page.locator("#submit-btn").click()
    expect(page.locator("#error")).to_contain_text("link individual")
    expect(page.locator("#error")).not_to_contain_text("prazo")
    expect(page.locator("#success")).to_be_hidden()
    assert store.summary()["counts"].total == 0


def test_conflicting_invitation_response_points_to_edit_link(page, server):
    base, store = server
    store.import_invited_families([{
        "key": "familia-silva", "name": "Maria Silva", "phone": "11999999999",
        "adults": 1, "young": 0, "older": 0,
    }])
    family = store.invitation_roster()[0]
    page.goto(base + "/convite#" + family["id"] + "." + family["token"])
    expect(page.locator("#contact-name")).to_have_value("Maria Silva")
    page.locator("#review-btn").click()
    page.route("**/api/invitations/*/response", lambda route: route.fulfill(
        status=409, content_type="application/json",
        body='{"error":{"code":"CONFLICT","message":"Resposta conflitante."}}',
    ))
    page.locator("#submit-btn").click()
    expect(page.locator("#error")).to_contain_text("link de edição")
    expect(page.locator("#error")).not_to_contain_text("outra aba")
    expect(page.locator("#success")).to_be_hidden()
    assert store.summary()["counts"].total == 0


def test_edit_deadline_403_keeps_specific_message(page, server):
    base, store = server
    page.goto(base)
    page.locator("#contact-name").fill("Ana")
    page.locator("#review-btn").click()
    page.locator("#submit-btn").click()
    expect(page.locator("#success")).to_be_visible()
    edit_link = page.locator("#edit-link").input_value()
    page.goto(edit_link)
    expect(page.locator("#contact-name")).to_have_value("Ana")
    page.locator("#review-btn").click()
    page.route("**/api/rsvps/*", lambda route: route.fulfill(
        status=403, content_type="application/json",
        body='{"error":{"code":"EDIT_CLOSED","message":"Prazo encerrado."}}',
    ))
    page.locator("#submit-btn").click()
    expect(page.locator("#error")).to_contain_text("prazo para editar")
    expect(page.locator("#success")).to_be_hidden()
    assert store.summary()["counts"].total == 1
