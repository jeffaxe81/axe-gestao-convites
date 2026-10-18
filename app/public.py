"""Guest-only HTTP endpoints; separate private organizer API is a later task."""
from dataclasses import asdict
from datetime import datetime, timezone
from uuid import UUID

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import BadRequest

from app.config import EVENT_NAME, EVENT_STARTS_AT, EVENT_TIMEZONE
from app.domain import InputError, validate_rsvp
from app.rsvp import AccessDenied, EditClosed, IdempotencyConflict, RevisionConflict
from app.security import bearer_token

public = Blueprint("public", __name__)


def _store():
    return current_app.extensions["isadora_store"]


def error_response(status, code, message):
    return jsonify({"error": {"code": code, "message": message}}), status


def _json_object():
    if not request.is_json:
        raise BadRequest("Envie JSON.")
    value = request.get_json()
    if not isinstance(value, dict):
        raise InputError("Envie um objeto JSON.")
    return value


def _public_receipt(receipt):
    # Explicitly avoid serializing internal Counts, buffet limits or family lists.
    return {key: getattr(receipt, key) for key in (
        "id", "revision", "edit_token", "attending"
    )}


def _require_token():
    token = bearer_token()
    if not token:
        raise AccessDenied("Acesso não autorizado.")
    return token


@public.before_request
def restrict_guest_requests():
    if request.path.startswith("/api/rsvps/") or request.path == "/api/rsvps":
        limiter = current_app.extensions["isadora_rate_limiter"]
        if not limiter.allow(request.remote_addr or "unknown"):
            return error_response(429, "TOO_MANY_REQUESTS", "Tente novamente mais tarde.")


@public.errorhandler(InputError)
def handle_invalid(_error):
    return error_response(422, "INVALID_INPUT", str(_error))


@public.errorhandler(BadRequest)
def handle_bad_json(_error):
    return error_response(400, "INVALID_JSON", "JSON inválido.")


@public.errorhandler(AccessDenied)
def handle_access_denied(_error):
    return error_response(401, "UNAUTHORIZED", "Acesso não autorizado.")


@public.errorhandler(EditClosed)
def handle_expired(_error):
    return error_response(403, "EDIT_CLOSED", "O prazo de edição foi encerrado.")


@public.errorhandler(IdempotencyConflict)
@public.errorhandler(RevisionConflict)
def handle_conflict(_error):
    return error_response(409, "CONFLICT", "Esta operação entra em conflito com uma resposta existente.")


@public.errorhandler(SQLAlchemyError)
@public.errorhandler(ConnectionError)
@public.errorhandler(OSError)
def handle_unavailable(_error):
    # Never expose SQL/credentials, connection strings, names or secrets.
    return error_response(503, "SERVICE_UNAVAILABLE", "Serviço temporariamente indisponível.")


@public.get("/health/live")
def live():
    return jsonify({"status": "ok"})


@public.get("/health/ready")
def ready():
    try:
        _store().settings()
    except Exception:
        return error_response(503, "SERVICE_UNAVAILABLE", "Serviço temporariamente indisponível.")
    return jsonify({"status": "ready"})


@public.get("/api/event")
def event():
    settings = _store().settings()
    return jsonify({
        "name": EVENT_NAME,
        "age": 2,
        "starts_at": EVENT_STARTS_AT.isoformat(),
        "timezone": EVENT_TIMEZONE,
        "venue": settings["venue"] or "Local a confirmar",
    })


@public.post("/api/rsvps")
def create_rsvp():
    key = request.headers.get("Idempotency-Key", "")
    if not 16 <= len(key) <= 160:
        raise InputError("Identificador de envio inválido ou ausente.")
    payload = validate_rsvp(_json_object())
    # Check for retry before commit without leaking private family data.
    store = _store()
    key_hash = store._key_hash(key)
    digest = __import__("hashlib").sha256(
        __import__("app.rsvp", fromlist=["_input_bytes"])._input_bytes(payload)
    ).hexdigest()
    with store.session_factory() as session:
        existing = store._existing(session, key_hash, digest, store._edit_token(key))
    receipt = store.create(payload, key, datetime.now(timezone.utc))
    return jsonify(_public_receipt(receipt)), (200 if existing else 201)


@public.get("/api/rsvps/<family_id>")
def own_rsvp(family_id):
    return jsonify(_own_json(_store().get_own(family_id, _require_token())))


def _own_json(data):
    return {
        "id": data["id"],
        "contact_name": data["contact_name"],
        "attending": data["attending"],
        "revision": data["revision"],
        "participants": data["participants"],
        "venue": data["venue"],
        "can_edit": data["can_edit"],
        "edit_deadline_utc": (
            data["edit_deadline_utc"].isoformat()
            if data["edit_deadline_utc"] is not None else None
        ),
    }


@public.put("/api/rsvps/<family_id>")
def update_rsvp(family_id):
    token = _require_token()
    body = _json_object()
    if set(body) != {"revision", "contact_name", "attending", "participants"}:
        raise InputError("Informe revisão e dados completos da confirmação.")
    revision = body["revision"]
    payload = validate_rsvp({key: body[key] for key in ("contact_name", "attending", "participants")})
    receipt = _store().update(family_id, token, revision, payload, datetime.now(timezone.utc))
    return jsonify(_public_receipt(receipt))
