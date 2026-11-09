"""Browser journey: link -> prefilled family -> one response -> saved edit link."""
from playwright.sync_api import expect
from tests.e2e.test_guest import page, server


def test_family_specific_link_prefills_and_recovers_confirmation(page, server):
    base, store = server
    store.import_invited_families([{
        "key": "familia-teste", "name": "Maria Silva", "phone": "11999999999",
        "adults": 2, "young": 1, "older": 0
    }])
    invited = store.invitation_roster()[0]
    link = base + "/convite#" + invited["id"] + "." + invited["token"]
    page.goto(link)
    expect(page.locator("#contact-name")).to_have_value("Maria Silva")
    expect(page.locator("#invitation-plan")).to_contain_text("2 acima de 12 anos")
    expect(page.locator("#invitation-plan")).to_contain_text("1 crianças até 5 anos")
    page.locator("#add-companion").click()
    companion = page.locator("#participants .person-row").nth(1)
    companion.locator(".person-name").fill("Bia")
    companion.locator(".person-kind").select_option("CHILD")
    companion.locator(".person-age").fill("5")
    page.locator("#review-btn").click()
    expect(page.locator("#review-data")).to_contain_text("Bia")
    page.locator("#submit-btn").click()
    expect(page.locator("#success")).to_be_visible()
    private_edit_link = page.locator("#edit-link").input_value()
    assert "/editar#" in private_edit_link
    assert store.invited_family_summary()["pending"] == 0
    assert len(store.summary()["confirmed"]) == 1
    assert store.summary()["counts"].total == 2
    page.goto(link)
    expect(page.locator("#success")).to_be_visible()
    expect(page.locator("#edit-link")).to_have_value(private_edit_link)
    assert len(store.summary()["confirmed"]) == 1
