"""Security regression tests for public pages, HTTPS and default network exposure."""
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from tests.integration.test_public_api import store


@pytest.fixture
def client(store):
    app = create_app({"TESTING": True, "RSVP_STORE": store, "API_RATE_LIMIT": 0, "SECRET_KEY": "hardening-test-only-secret"})
    return app.test_client()


@pytest.mark.parametrize("path", ["/", "/editar", "/organizar", "/api/event", "/api/auth/csrf"])
def test_security_headers_on_guest_admin_and_api(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["X-Frame-Options"] == "DENY"
    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_compose_does_not_publish_unencrypted_http_to_all_interfaces():
    text = Path("compose.yaml").read_text(encoding="utf-8")
    assert '127.0.0.1:8080:8080' in text
    assert '      - "8080:8080"' not in text


def test_production_rejects_public_http_even_with_correct_secrets(monkeypatch, store):
    monkeypatch.setenv("APP_PUBLIC_URL", "http://convites.example.com")
    with pytest.raises(RuntimeError, match="HTTPS"):
        create_app({
            "RSVP_STORE": store,
            "SECRET_KEY": "test-session-secret-long-enough-for-startup",
            "ORGANIZER_USERNAME": "admin",
            "ORGANIZER_PASSWORD_HASH": generate_password_hash("a-test-password"),
        })


@pytest.mark.parametrize("url", ["http://localhost:8080", "http://127.0.0.1:8080"])
def test_local_http_is_allowed_in_production_with_loopback(monkeypatch, store, url):
    monkeypatch.setenv("APP_PUBLIC_URL", url)
    app = create_app({
        "RSVP_STORE": store,
        "SECRET_KEY": "test-session-secret-long-enough-for-startup",
        "ORGANIZER_USERNAME": "admin",
        "ORGANIZER_PASSWORD_HASH": generate_password_hash("a-test-password"),
    })
    assert app.config["SESSION_COOKIE_SECURE"] is False


def test_production_https_requires_secure_session_cookie(monkeypatch, store):
    monkeypatch.setenv("APP_PUBLIC_URL", "https://convites.example.com")
    app = create_app({
        "RSVP_STORE": store,
        "SECRET_KEY": "test-session-secret-long-enough-for-startup",
        "ORGANIZER_USERNAME": "admin",
        "ORGANIZER_PASSWORD_HASH": generate_password_hash("a-test-password"),
    })
    assert app.config["SESSION_COOKIE_SECURE"] is True
