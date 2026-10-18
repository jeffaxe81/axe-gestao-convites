"""Application factory for the Isadora invitation manager.

Public responses have explicit whitelists; internal buffet data stays private.
"""
import os
from urllib.parse import urlsplit
from datetime import timedelta

from flask import Flask
from sqlalchemy.exc import SQLAlchemyError

from app.db import new_engine, session_factory
from app.rsvp import RsvpStore
from app.security import RequestRateLimiter


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        MAX_CONTENT_LENGTH=64 * 1024,
        JSON_AS_ASCII=False,
        API_RATE_LIMIT=30,  # requests / minute / IP, per worker (not a global DDoS solution)
        AUTH_RATE_LIMIT=5,
        SECRET_KEY=os.environ.get("SESSION_SECRET"),
        ORGANIZER_USERNAME=os.environ.get("ORGANIZER_USERNAME"),
        ORGANIZER_PASSWORD_HASH=os.environ.get("ORGANIZER_PASSWORD_HASH"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("APP_PUBLIC_URL", "").startswith("https://"),
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    )
    if test_config:
        app.config.update(test_config)

    if not app.config.get("TESTING"):
        if len(app.config.get("SECRET_KEY") or "") < 32:
            raise RuntimeError("Configure SESSION_SECRET aleatória com ao menos 32 caracteres.")
        if not app.config.get("ORGANIZER_USERNAME"):
            raise RuntimeError("Configure ORGANIZER_USERNAME.")
        saved_hash = app.config.get("ORGANIZER_PASSWORD_HASH") or ""
        if not (saved_hash.startswith("scrypt:") or saved_hash.startswith("pbkdf2:")):
            raise RuntimeError("Configure ORGANIZER_PASSWORD_HASH com hash seguro Werkzeug.")

    if not app.config.get("TESTING"):
        public_url = os.environ.get("APP_PUBLIC_URL", "")
        parsed = urlsplit(public_url)
        is_local_http = parsed.scheme == "http" and parsed.hostname in (
            "localhost", "127.0.0.1", "::1"
        )
        if not (parsed.scheme == "https" or is_local_http) or not parsed.hostname:
            raise RuntimeError("Uma URL pública exige HTTPS; HTTP só é permitido em localhost.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
            raise RuntimeError("APP_PUBLIC_URL deve conter apenas a origem do site.")
        app.config["SESSION_COOKIE_SECURE"] = parsed.scheme == "https"

    store = app.config.get("RSVP_STORE")
    if store is None:
        secret = os.environ.get("TOKEN_SECRET", "")
        if len(secret) < 32 or secret.startswith("SUBSTITUIR"):
            raise RuntimeError("Configure TOKEN_SECRET aleatória com ao menos 32 caracteres.")
        engine = new_engine()
        app.extensions["isadora_engine"] = engine
        store = RsvpStore(session_factory(engine), secret)
    app.extensions["isadora_store"] = store
    app.extensions["isadora_rate_limiter"] = RequestRateLimiter(
        int(app.config["API_RATE_LIMIT"])
    )

    from app.public import public
    from app.organizer import organizer
    app.register_blueprint(public)
    app.register_blueprint(organizer)

    app.extensions["isadora_auth_limiter"] = RequestRateLimiter(
        int(app.config["AUTH_RATE_LIMIT"])
    )

    @app.after_request
    def harden(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self' data:; font-src 'self'; "
            "form-action 'self'; base-uri 'none'; object-src 'none'; "
            "frame-ancestors 'none'"
        )
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if response.mimetype in ("application/json", "text/html"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(413)
    def request_too_large(_error):
        return {"error": {"code": "PAYLOAD_TOO_LARGE", "message": "Envio muito grande."}}, 413

    return app
