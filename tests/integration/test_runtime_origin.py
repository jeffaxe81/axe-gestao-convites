"""Controle em runtime impede configurações inseguras mesmo sem preflight."""
import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.origin import configured_origin
from tests.integration.test_public_api import store


@pytest.mark.parametrize("value", [
    "", "http://convites.festa.com.br",
    "http://localhost", "http://localhost:8888", "http://0.0.0.0:8080",
    "http://[::1]:8080", "https://convites.example",
    "https://convites.festa.com.br:8443", "https://convites.festa.com.br/path",
    "https://convites.festa.com.br?token=abc", "https://convites.festa.com.br#private",
    "https://u:p@convites.festa.com.br", "https://192.168.0.10",
    "javascript:alert(1)", "https://-x.festa.com.br",
])
def test_reject_invalid_public_origin(value):
    with pytest.raises(ValueError, match="APP_PUBLIC_URL inválida"):
        configured_origin(value)


@pytest.mark.parametrize("value,expected", [
    ("http://127.0.0.1:8080", ("http", "127.0.0.1")),
    ("http://localhost:8080", ("http", "localhost")),
    ("https://convites.festa.com.br", ("https", "convites.festa.com.br")),
])
def test_allow_canonical_http_loopback_and_dns_https(value, expected):
    assert configured_origin(value) == expected


def _configured_app(store):
    return create_app({
        "RSVP_STORE": store,
        "SECRET_KEY": "a-realistic-session-secret-for-tests-only-123456789",
        "ORGANIZER_USERNAME": "admin",
        "ORGANIZER_PASSWORD_HASH": generate_password_hash("long-admin-password-for-tests"),
    })


@pytest.mark.parametrize("value", [
    "http://0.0.0.0:8080", "https://convites.festa.com.br:1234",
    "https://u:p@convites.festa.com.br", "http://convites.festa.com.br",
])
def test_production_fails_closed_with_unsafe_origin(monkeypatch, store, value):
    monkeypatch.setenv("APP_PUBLIC_URL", value)
    with pytest.raises(RuntimeError, match="APP_PUBLIC_URL inválida"):
        _configured_app(store)


def test_production_restricts_host_and_sets_hsts_for_https(monkeypatch, store):
    monkeypatch.setenv("APP_PUBLIC_URL", "https://convites.festa.com.br")
    app = _configured_app(store)
    assert app.config["TRUSTED_HOSTS"] == [
        "convites.festa.com.br", "localhost", "127.0.0.1"
    ]
    assert app.config["SESSION_COOKIE_SECURE"] is True
    client = app.test_client()
    assert client.get("/", headers={"Host": "evil.attacker.com"}).status_code == 400
    valid = client.get("/", headers={"Host": "convites.festa.com.br"})
    assert valid.status_code == 200
    assert valid.headers["Strict-Transport-Security"] == "max-age=31536000"


def test_local_mode_omits_hsts(monkeypatch, store):
    monkeypatch.setenv("APP_PUBLIC_URL", "http://127.0.0.1:8080")
    app = _configured_app(store)
    assert app.config["SESSION_COOKIE_SECURE"] is False
    assert app.test_client().get("/").headers.get("Strict-Transport-Security") is None
