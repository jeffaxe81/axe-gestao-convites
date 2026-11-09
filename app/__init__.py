"""Application factory for the Isadora invitation manager.

Public responses have explicit whitelists; internal buffet data stays private.
"""
import os
from datetime import timedelta

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy.exc import SQLAlchemyError

from app.db import new_engine, session_factory
from app.origin import configured_origin
from app.rsvp import RsvpStore
from app.security import RequestRateLimiter


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        MAX_CONTENT_LENGTH=1_100_000,
        JSON_AS_ASCII=False,
        API_RATE_LIMIT=30,  # requests / minute / IP, per worker (not a global DDoS solution)
        AUTH_RATE_LIMIT=5,
        TRUSTED_PROXY_HOPS=int(os.environ.get("TRUSTED_PROXY_HOPS", "0")),
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

    proxy_hops = int(app.config["TRUSTED_PROXY_HOPS"])
    if proxy_hops not in (0, 1):
        raise ValueError("TRUSTED_PROXY_HOPS deve ser 0 ou 1.")
    # Only use with a local reverse proxy that OVERWRITES X-Forwarded-For.
    # Default is 0: client-supplied forwarding headers are ignored.
    if proxy_hops:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

    if not app.config.get("TESTING"):
        if len(app.config.get("SECRET_KEY") or "") < 32:
            raise RuntimeError("Configure SESSION_SECRET aleatória com ao menos 32 caracteres.")
        if not app.config.get("ORGANIZER_USERNAME"):
            raise RuntimeError("Configure ORGANIZER_USERNAME.")
        saved_hash = app.config.get("ORGANIZER_PASSWORD_HASH") or ""
        if not (saved_hash.startswith("scrypt:") or saved_hash.startswith("pbkdf2:")):
            raise RuntimeError("Configure ORGANIZER_PASSWORD_HASH com hash seguro Werkzeug.")

    if not app.config.get("TESTING"):
        try:
            scheme, hostname = configured_origin(os.environ.get("APP_PUBLIC_URL", ""))
        except ValueError as exc:
            raise RuntimeError(str(exc)) from None
        app.config["SESSION_COOKIE_SECURE"] = scheme == "https"
        # Flask 3.1 rejects arbitrary Host headers, even if upstream proxy
        # forgets to enforce them. Loopback remains available to health checks.
        app.config["TRUSTED_HOSTS"] = [hostname, "localhost", "127.0.0.1"]

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
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self' data:; font-src 'self'; "
            "form-action 'self'; base-uri 'none'; object-src 'none'; "
            "frame-ancestors 'none'"
        )
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        if response.mimetype in ("application/json", "text/html"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(413)
    def request_too_large(_error):
        return {"error": {"code": "PAYLOAD_TOO_LARGE", "message": "Envio muito grande."}}, 413

    return app
