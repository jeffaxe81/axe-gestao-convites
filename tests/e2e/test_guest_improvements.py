"""Navegador: orientação e melhorias de usabilidade do convite."""
from playwright.sync_api import expect

from tests.e2e.test_guest import page, server


def test_event_date_countdown_and_calendar_action(page, server):
    base, _ = server
    page.goto(base)
    expect(page.locator("#event-date")).to_contain_text("13 de dezembro de 2026")
    expect(page.locator("#event-date")).to_contain_text("15:00")
    expect(page.locator("#event-countdown")).to_be_visible()
    expect(page.locator("#event-countdown")).to_contain_text("festa")
    expect(page.get_by_role("link", name="Adicionar a festa ao calendário")).to_have_attribute(
        "href", "/evento.ics"
    )
    assert page.request.get(base + "/evento.ics").status == 200


def test_step_guidance_and_escape_to_fix_response(page, server):
    base, _ = server
    page.goto(base)
    expect(page.locator("#stage-indicator")).to_contain_text("Etapa 1 de 3")
    page.locator("#contact-name").fill("Ana")
    page.locator("#review-btn").click()
    expect(page.locator("#stage-indicator")).to_contain_text("Etapa 2 de 3")
    page.keyboard.press("Escape")
    expect(page.locator("#rsvp-form")).to_be_visible()
    expect(page.locator("#review-btn")).to_be_focused()
    page.locator("#review-btn").click()
    page.locator("#submit-btn").click()
    expect(page.locator("#success")).to_be_visible()
    expect(page.locator("#stage-indicator")).to_contain_text("Etapa 3 de 3")


def test_missing_contact_and_companion_focus_invalid_fields(page, server):
    base, _ = server
    page.goto(base)
    page.locator("#review-btn").click()
    expect(page.locator("#contact-name")).to_be_focused()
    page.locator("#contact-name").fill("Ana")
    page.locator("#add-companion").click()
    page.locator("#review-btn").click()
    expect(page.locator("#participants .person-row").nth(1).locator(".person-name")).to_be_focused()
    row = page.locator("#participants .person-row").nth(1)
    row.locator(".person-name").fill("Bia")
    row.locator(".person-kind").select_option("CHILD")
    page.locator("#review-btn").click()
    expect(row.locator(".person-age")).to_be_focused()
    row.locator(".person-age").fill("6")
    page.locator("#review-btn").click()
    expect(page.locator("#review")).to_be_visible()


def test_counter_and_companion_limit_are_reversible(page, server):
    base, _ = server
    page.goto(base)
    expect(page.locator("#participant-count")).to_contain_text("1 participante")
    page.locator("#add-companion").click()
    expect(page.locator("#participant-count")).to_contain_text("2 participantes")
    page.locator("#participants .person-row").nth(1).locator("button.remove").click()
    expect(page.locator("#participant-count")).to_contain_text("1 participante")
    page.evaluate("""() => { for (let i=0; i<99; i++) {
      document.getElementById('add-companion').click();
    }}""")
    expect(page.locator("#participant-count")).to_contain_text("100 participantes")
    expect(page.locator("#add-companion")).to_be_disabled()
    page.locator("#participants .person-row").last.locator("button.remove").click()
    expect(page.locator("#add-companion")).to_be_enabled()


def test_offline_state_never_claims_success_until_reconnected(page, server):
    base, store = server
    page.goto(base)
    page.locator("#contact-name").fill("Ana")
    page.locator("#review-btn").click()
    page.context.set_offline(True)
    expect(page.locator("#connection-status")).to_be_visible()
    expect(page.locator("#connection-status")).to_contain_text("sem conexão")
    page.locator("#submit-btn").click()
    expect(page.locator("#error")).to_contain_text("Sem conexão")
    expect(page.locator("#success")).to_be_hidden()
    assert store.summary()["counts"].total == 0
    page.context.set_offline(False)
    expect(page.locator("#connection-status")).to_be_hidden()
    page.locator("#submit-btn").click()
    expect(page.locator("#success")).to_be_visible()
    assert store.summary()["counts"].total == 1


def test_copy_link_accessible_feedback(page, server):
    base, _ = server
    page.goto(base)
    page.locator("#contact-name").fill("Ana")
    page.locator("#review-btn").click()
    page.locator("#submit-btn").click()
    expect(page.locator("#success")).to_be_visible()
    page.locator("#copy-link").click()
    expect(page.locator("#copy-status")).not_to_be_empty()
    assert "aria-live" in page.locator("#copy-status").evaluate(
        "(element) => element.outerHTML"
    )
