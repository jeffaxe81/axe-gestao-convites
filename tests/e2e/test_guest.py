"""Chromium browser checks for mobile invitation and private editing."""
from threading import Thread

import pytest
from playwright.sync_api import sync_playwright, expect
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from werkzeug.serving import make_server

from app import create_app
from app.models import Base, EventSettings
from app.rsvp import RsvpStore


@pytest.fixture
def server():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(EventSettings(id=1, buffet_limit=40))
    store = RsvpStore(factory, "browser-tests-only-secret-1234567")
    app = create_app({"TESTING": True, "RSVP_STORE": store, "API_RATE_LIMIT": 0})
    httpd = make_server("127.0.0.1", 0, app, threaded=True)
    worker = Thread(target=httpd.serve_forever, daemon=True)
    worker.start()
    yield ("http://127.0.0.1:" + str(httpd.server_port), store)
    httpd.shutdown()
    worker.join(timeout=5)
    httpd.server_close()
    engine.dispose()


@pytest.fixture
def page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        tab = browser.new_page(viewport={"width": 390, "height": 844})
        yield tab
        browser.close()


def test_mobile_guest_confirms_and_edits_same_family(page, server):
    url, store = server
    page.goto(url)
    expect(page.get_by_role("heading", name="Os 2 aninhos da Isadora")).to_be_visible()
    page.locator("#contact-name").fill("Ana")
    page.locator("#add-companion").click()
    row = page.locator("#participants .person-row").nth(1)
    row.locator(".person-name").fill("Luiza")
    row.locator(".person-kind").select_option("CHILD")
    row.locator(".person-age").fill("6")
    page.locator("#review-btn").click()
    expect(page.locator("#review-data")).to_contain_text("Luiza")
    page.locator("#submit-btn").click()
    expect(page.locator("#success")).to_be_visible()
    link = page.locator("#edit-link").input_value()
    assert "/editar#" in link and "buffet" not in page.content().lower()
    assert store.summary()["counts"].total == 2
    assert store.summary()["counts"].buffet == 2

    page.goto(link)
    expect(page.locator("#contact-name")).to_have_value("Ana")
    page.locator("#participants .person-row").nth(1).locator(".person-age").fill("5")
    page.locator("#review-btn").click()
    page.locator("#submit-btn").click()
    expect(page.locator("#success")).to_be_visible()
    assert len(store.summary()["confirmed"]) == 1
    assert store.summary()["counts"].total == 2
    assert store.summary()["counts"].buffet == 1


def test_negative_confirmation_never_counts_as_attending(page, server):
    url, store = server
    page.goto(url)
    page.locator("#contact-name").fill("Beatriz")
    page.locator('input[name="attendance"][value="no"]').check()
    page.locator("#review-btn").click()
    page.locator("#submit-btn").click()
    expect(page.locator("#success")).to_be_visible()
    assert len(store.summary()["confirmed"]) == 0
    assert len(store.summary()["declined"]) == 1


def test_html_like_names_are_rendered_as_text_not_elements(page, server):
    url, _ = server
    page.goto(url)
    suspicious = '<img src=x onerror=alert(1)>'
    page.locator("#contact-name").fill(suspicious)
    page.locator("#review-btn").click()
    expect(page.locator("#review-data")).to_contain_text(suspicious)
    assert page.locator("img[src=x]").count() == 0


def test_mobile_page_does_not_scroll_horizontally(page, server):
    url, _ = server
    page.goto(url)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
