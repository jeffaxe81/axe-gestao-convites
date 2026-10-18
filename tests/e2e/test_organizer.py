"""Chromium tests for private organizer login, lists and event settings."""
from datetime import datetime, timezone
from threading import Thread

import pytest
from playwright.sync_api import expect
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server

from app import create_app
from app.domain import validate_rsvp
from app.models import Base, EventSettings
from app.rsvp import RsvpStore
from tests.e2e.test_guest import page


@pytest.fixture
def organizer_server():
    engine = create_engine("sqlite+pysqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(EventSettings(id=1, buffet_limit=40))
    store = RsvpStore(factory, "organizer-e2e-token-secret-123456")
    people = validate_rsvp({
        "contact_name": "João",
        "attending": True,
        "participants": [
            {"name": "João", "kind": "OVER_12", "age_years": None},
            {"name": "Lia", "kind": "CHILD", "age_years": 5},
            {"name": "Nina", "kind": "CHILD", "age_years": 6},
        ],
    })
    store.create(people, "organizer-e2e-first-family", datetime.now(timezone.utc))
    app = create_app({
        "TESTING": True, "RSVP_STORE": store,
        "SECRET_KEY": "only-browser-admin-session-secret-12345",
        "ORGANIZER_USERNAME": "organizador",
        "ORGANIZER_PASSWORD_HASH": generate_password_hash("senha-de-teste"),
        "AUTH_RATE_LIMIT": 0, "API_RATE_LIMIT": 0,
    })
    server = make_server("127.0.0.1", 0, app, threaded=True)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    yield "http://127.0.0.1:" + str(server.server_port), store
    server.shutdown()
    worker.join(timeout=5)
    server.server_close()
    engine.dispose()


def login(page, base, password="senha-de-teste"):
    page.goto(base + "/organizar")
    page.locator("#admin-username").fill("organizador")
    page.locator("#admin-password").fill(password)
    page.locator("#login-btn").click()


def test_private_dashboard_lists_and_age_counts(page, organizer_server):
    base, store = organizer_server
    login(page, base)
    expect(page.get_by_test_id("buffet-count")).to_have_text("2")
    expect(page.get_by_test_id("souvenir-count")).to_have_text("2")
    expect(page.get_by_test_id("total-count")).to_have_text("3")
    expect(page.locator("#confirmed-list")).to_contain_text("João")
    expect(page.locator("#confirmed-list")).to_contain_text("Lia")
    expect(page.locator("#souvenir-list")).to_contain_text("Nina")


def test_admin_updates_venue_and_deadline(page, organizer_server):
    base, store = organizer_server
    login(page, base)
    expect(page.locator("#venue-input")).to_be_visible()
    page.locator("#venue-input").fill("Salão das Flores")
    page.locator("#deadline-input").fill("2026-11-30T22:30")
    page.locator("#save-settings").click()
    expect(page.locator("#settings-status")).to_contain_text("salva")
    assert store.settings()["venue"] == "Salão das Flores"
    assert store.settings()["edit_deadline_utc"] is not None


def test_logout_hides_private_information(page, organizer_server):
    base, _ = organizer_server
    login(page, base)
    expect(page.get_by_test_id("buffet-count")).to_have_text("2")
    page.locator("#logout-btn").click()
    expect(page.locator("#login-panel")).to_be_visible()
    expect(page.locator("#dashboard-panel")).to_be_hidden()


def test_failed_login_never_shows_private_lists(page, organizer_server):
    base, _ = organizer_server
    login(page, base, password="senha-incorreta")
    expect(page.locator("#login-error")).to_be_visible()
    expect(page.locator("#dashboard-panel")).to_be_hidden()
