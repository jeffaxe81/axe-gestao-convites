"""Application factory for the Isadora invitation manager.

Public responses have explicit whitelists; internal buffet data stays private.
"""
import os

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
    )
    if test_config:
        app.config.update(test_config)

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
    app.register_blueprint(public)

    @app.after_request
    def harden(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if response.mimetype == "application/json":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(413)
    def request_too_large(_error):
        return {"error": {"code": "PAYLOAD_TOO_LARGE", "message": "Envio muito grande."}}, 413

    return app
