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
    expect(page.locator("#admin-password")).to_have_value("")


def test_unavailable_login_clears_password_field(page, organizer_server):
    base, _ = organizer_server
    page.route("**/api/auth/login", lambda route: route.fulfill(
        status=503, content_type="application/json",
        body='{"error":{"message":"Serviço indisponível"}}'
    ))
    login(page, base)
    expect(page.locator("#login-error")).to_contain_text("Serviço indisponível")
    expect(page.locator("#admin-password")).to_have_value("")
    expect(page.locator("#dashboard-panel")).to_be_hidden()


def test_guest_search_by_contact_companion_and_decline(page, organizer_server):
    base, store = organizer_server
    store.create(validate_rsvp({
        "contact_name": "Ana", "attending": True,
        "participants": [
            {"name": "Ana", "kind": "OVER_12", "age_years": None},
            {"name": "Cecília", "kind": "CHILD", "age_years": 6},
        ],
    }), "organizer-search-family-ana-001", datetime.now(timezone.utc))
    store.create(validate_rsvp({
        "contact_name": "Beatriz", "attending": False, "participants": [],
    }), "organizer-search-family-bia-002", datetime.now(timezone.utc))
    login(page, base)
    expect(page.get_by_test_id("total-count")).to_have_text("5")
    expect(page.locator("#search-summary")).to_contain_text("3 de 3 respostas")
    page.locator("#guest-search").fill("cecilia")
    expect(page.locator("#confirmed-list")).to_contain_text("Ana")
    expect(page.locator("#confirmed-list")).not_to_contain_text("João")
    expect(page.locator("#souvenir-list")).to_contain_text("Cecília")
    expect(page.locator("#souvenir-list")).not_to_contain_text("Lia")
    expect(page.locator("#search-summary")).to_contain_text("1 de 3 respostas")
    # Global counters must never be changed by a visual-only filter.
    expect(page.get_by_test_id("total-count")).to_have_text("5")
    page.locator("#guest-search").fill("BEATRIZ")
    expect(page.locator("#declined-list")).to_contain_text("Beatriz")
    expect(page.locator("#confirmed-list")).to_contain_text("Nenhum registro")
    page.locator("#guest-search").fill("nome-inexistente")
    expect(page.locator("#search-summary")).to_contain_text("0 de 3 respostas")
    page.locator("#clear-search").click()
    expect(page.locator("#confirmed-list")).to_contain_text("João")
    expect(page.locator("#declined-list")).to_contain_text("Beatriz")
    expect(page.locator("#guest-search")).to_have_value("")


def test_logout_resets_private_search_without_local_persistence(page, organizer_server):
    base, _ = organizer_server
    login(page, base)
    expect(page.locator("#confirmed-list")).to_contain_text("João")
    page.locator("#guest-search").fill("Joao")
    expect(page.locator("#confirmed-list")).to_contain_text("João")
    page.locator("#logout-btn").click()
    expect(page.locator("#dashboard-panel")).to_be_hidden()
    expect(page.locator("#guest-search")).to_have_value("")
    expect(page.locator("#search-summary")).to_have_text("")
    login(page, base)
    expect(page.locator("#search-summary")).to_contain_text("1 de 1 respostas")


def test_manual_refresh_preserves_search_and_unsaved_settings(page, organizer_server):
    base, store = organizer_server
    login(page, base)
    expect(page.get_by_test_id("total-count")).to_have_text("3")
    page.locator("#guest-search").fill("Ana")
    page.locator("#venue-input").fill("Novo local ainda não salvo")

    store.create(validate_rsvp({
        "contact_name": "Ana", "attending": True,
        "participants": [
            {"name": "Ana", "kind": "OVER_12", "age_years": None},
            {"name": "Mila", "kind": "CHILD", "age_years": 5},
        ],
    }), "organizer-refresh-ana-001", datetime.now(timezone.utc))

    page.locator("#refresh-dashboard-btn").click()
    expect(page.get_by_test_id("total-count")).to_have_text("5")
    expect(page.locator("#confirmed-list")).to_contain_text("Ana")
    expect(page.locator("#confirmed-list")).not_to_contain_text("João")
    expect(page.locator("#guest-search")).to_have_value("Ana")
    expect(page.locator("#venue-input")).to_have_value("Novo local ainda não salvo")
    expect(page.locator("#refresh-status")).to_contain_text("Dados atualizados")
    assert store.settings()["venue"] is None


def test_refresh_failure_keeps_previous_private_counts(page, organizer_server):
    base, _ = organizer_server
    login(page, base)
    expect(page.get_by_test_id("total-count")).to_have_text("3")
    page.route("**/api/admin/dashboard", lambda route: route.fulfill(
        status=503, content_type="application/json",
        body='{"error":{"message":"Temporariamente indisponível"}}'
    ))
    page.locator("#refresh-dashboard-btn").click()
    expect(page.locator("#refresh-status")).to_contain_text("Falha ao atualizar")
    expect(page.get_by_test_id("total-count")).to_have_text("3")
    expect(page.locator("#refresh-dashboard-btn")).to_be_enabled()


def test_expired_refresh_session_hides_private_data(page, organizer_server):
    base, _ = organizer_server
    login(page, base)
    expect(page.locator("#confirmed-list")).to_contain_text("João")
    page.locator("#refresh-interval").select_option("15")
    page.route("**/api/admin/dashboard", lambda route: route.fulfill(
        status=401, content_type="application/json",
        body='{"error":{"message":"Acesso não autorizado."}}'
    ))
    page.locator("#refresh-dashboard-btn").click()
    expect(page.locator("#dashboard-panel")).to_be_hidden()
    expect(page.locator("#login-panel")).to_be_visible()
    expect(page.locator("#login-error")).to_contain_text("sessão expirou")
    expect(page.locator("#confirmed-list")).to_have_text("")
    expect(page.locator("#refresh-interval")).to_have_value("0")


def test_refresh_after_cookie_expiration_allows_new_login(page, organizer_server):
    base, _ = organizer_server
    login(page, base)
    expect(page.locator("#confirmed-list")).to_contain_text("João")
    # Model a truly expired Flask session (not just a mocked HTTP error).
    page.context.clear_cookies()
    page.locator("#refresh-dashboard-btn").click()
    expect(page.locator("#dashboard-panel")).to_be_hidden()
    expect(page.locator("#login-error")).to_contain_text("sessão expirou")
    # The next login must retrieve a fresh session-specific CSRF token.
    page.locator("#admin-username").fill("organizador")
    page.locator("#admin-password").fill("senha-de-teste")
    page.locator("#login-btn").click()
    expect(page.locator("#confirmed-list")).to_contain_text("João")
    expect(page.get_by_test_id("total-count")).to_have_text("3")


def test_automatic_refresh_at_selected_interval(page, organizer_server):
    base, store = organizer_server
    page.clock.install()
    login(page, base)
    expect(page.get_by_test_id("total-count")).to_have_text("3")
    page.locator("#refresh-interval").select_option("15")
    store.create(validate_rsvp({
        "contact_name": "Pedro", "attending": True,
        "participants": [{"name": "Pedro", "kind": "OVER_12", "age_years": None}],
    }), "organizer-auto-refresh-pedro-001", datetime.now(timezone.utc))
    # Playwright's virtual clock avoids a 15-second sleep in CI.
    page.clock.fast_forward(15_000)
    expect(page.get_by_test_id("total-count")).to_have_text("4")
    expect(page.locator("#confirmed-list")).to_contain_text("Pedro")
    expect(page.locator("#refresh-status")).to_contain_text("Dados atualizados")


def test_invalid_success_snapshot_does_not_corrupt_dashboard(page, organizer_server):
    base, store = organizer_server
    login(page, base)
    expect(page.get_by_test_id("total-count")).to_have_text("3")
    store.create(validate_rsvp({
        "contact_name": "Rosa", "attending": True,
        "participants": [{"name": "Rosa", "kind": "OVER_12", "age_years": None}],
    }), "organizer-broken-response-rosa-1", datetime.now(timezone.utc))
    page.route("**/api/admin/dashboard", lambda route: route.fulfill(
        status=200, content_type="application/json", body="{}"
    ))
    page.locator("#refresh-dashboard-btn").click()
    expect(page.locator("#refresh-status")).to_contain_text("Falha ao atualizar")
    expect(page.get_by_test_id("total-count")).to_have_text("3")
    page.locator("#guest-search").fill("Joao")
    expect(page.locator("#confirmed-list")).to_contain_text("João")
    page.unroute("**/api/admin/dashboard")
    page.locator("#refresh-dashboard-btn").click()
    expect(page.get_by_test_id("total-count")).to_have_text("4")
    expect(page.locator("#refresh-status")).to_contain_text("Dados atualizados")
    expect(page.locator("#guest-search")).to_have_value("Joao")


def test_inconsistent_success_snapshot_rejected_without_wrong_buffet(page, organizer_server):
    base, _ = organizer_server
    login(page, base)
    expect(page.get_by_test_id("buffet-count")).to_have_text("2")

    def corrupt_buffet(route):
        import json
        response = route.fetch()
        data = response.json()
        data["counts"]["buffet"] = 1000
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(data))

    page.route("**/api/admin/dashboard", corrupt_buffet)
    page.locator("#refresh-dashboard-btn").click()
    expect(page.locator("#refresh-status")).to_contain_text("Falha ao atualizar")
    expect(page.get_by_test_id("buffet-count")).to_have_text("2")
    expect(page.locator("#refresh-dashboard-btn")).to_be_enabled()


def test_session_expires_while_saving_settings(page, organizer_server):
    base, store = organizer_server
    login(page, base)
    expect(page.get_by_test_id("total-count")).to_have_text("3")
    page.context.clear_cookies()
    page.locator("#venue-input").fill("Alteração não autorizada")
    page.locator("#save-settings").click()
    expect(page.locator("#dashboard-panel")).to_be_hidden()
    expect(page.locator("#login-error")).to_contain_text("sessão expirou")
    expect(page.locator("#confirmed-list")).to_have_text("")
    expect(page.get_by_test_id("total-count")).to_have_text("0")
    expect(page.locator("#venue-input")).to_have_value("")
    assert store.settings()["venue"] is None


def test_session_expires_while_exporting_csv(page, organizer_server):
    base, _ = organizer_server
    login(page, base)
    expect(page.locator("#confirmed-list")).to_contain_text("João")
    page.context.clear_cookies()
    page.locator("#export-csv-btn").click()
    expect(page.locator("#dashboard-panel")).to_be_hidden()
    expect(page.locator("#login-error")).to_contain_text("sessão expirou")
    expect(page.locator("#confirmed-list")).to_have_text("")
    expect(page.get_by_test_id("buffet-count")).to_have_text("0")


def test_failed_logout_still_hides_names_and_reports_uncertain_server_state(page, organizer_server):
    base, _ = organizer_server
    login(page, base)
    expect(page.locator("#confirmed-list")).to_contain_text("João")
    page.route("**/api/auth/logout", lambda route: route.fulfill(
        status=503, content_type="application/json",
        body='{"error":{"message":"Indisponível"}}'
    ))
    page.locator("#logout-btn").click()
    expect(page.locator("#dashboard-panel")).to_be_hidden()
    expect(page.locator("#confirmed-list")).to_have_text("")
    expect(page.get_by_test_id("souvenir-count")).to_have_text("0")
    expect(page.locator("#login-error")).to_contain_text("Não foi possível confirmar a saída")


def test_successful_logout_clears_private_counters_and_fields(page, organizer_server):
    base, _ = organizer_server
    login(page, base)
    expect(page.get_by_test_id("total-count")).to_have_text("3")
    page.locator("#venue-input").fill("Rascunho privado")
    page.locator("#logout-btn").click()
    expect(page.locator("#dashboard-panel")).to_be_hidden()
    expect(page.locator("#venue-input")).to_have_value("")
    expect(page.get_by_test_id("total-count")).to_have_text("0")
    expect(page.get_by_test_id("buffet-count")).to_have_text("0")
    expect(page.locator("#confirmed-list")).to_have_text("")
    expect(page.locator("#souvenir-list")).to_have_text("")
