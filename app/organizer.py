"""Organizer-only sessions, CSRF, attendance dashboard and event settings."""
from dataclasses import asdict
import os
from datetime import datetime, timezone
import hmac
import secrets

from flask import Blueprint, current_app, jsonify, request, session, render_template, make_response
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import BadRequest
from werkzeug.security import check_password_hash

from app.domain import InputError
from app.reports import export_attendance_csv, export_planning_csv
from app.invitations import InvitationImportError, InvitationStore, parse_guest_csv

organizer = Blueprint("organizer", __name__)


def error_response(status, code, message):
    return jsonify({"error": {"code": code, "message": message}}), status


def store():
    return current_app.extensions["isadora_store"]


def json_object():
    if not request.is_json:
        raise BadRequest()
    data = request.get_json()
    if not isinstance(data, dict):
        raise InputError("Informe um objeto JSON.")
    return data


def csrf_valid():
    sent = request.headers.get("X-CSRF-Token", "")
    expected = session.get("csrf", "")
    return bool(sent and expected and hmac.compare_digest(sent, expected))


def settings_safe(raw):
    deadline = raw["edit_deadline_utc"]
    return {"venue": raw["venue"],
            "edit_deadline_utc": deadline.isoformat() if deadline else None}


@organizer.before_request
def require_organizer_auth():
    if request.path.startswith("/api/admin/") and session.get("organizer_authenticated") is not True:
        return error_response(401, "UNAUTHORIZED", "Acesso não autorizado.")
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        if request.endpoint == "organizer.login":
            limiter = current_app.extensions["isadora_auth_limiter"]
            if not limiter.allow(request.remote_addr or "unknown"):
                return error_response(429, "TOO_MANY_REQUESTS", "Tente novamente mais tarde.")
        if not csrf_valid():
            return error_response(403, "INVALID_CSRF", "Solicitação não autorizada.")


@organizer.errorhandler(InputError)
def invalid_input(exc):
    return error_response(422, "INVALID_INPUT", str(exc))


@organizer.errorhandler(BadRequest)
def invalid_json(exc):
    return error_response(400, "INVALID_JSON", "JSON inválido.")


@organizer.errorhandler(SQLAlchemyError)
@organizer.errorhandler(ConnectionError)
@organizer.errorhandler(OSError)
def db_unavailable(exc):
    return error_response(503, "SERVICE_UNAVAILABLE", "Serviço temporariamente indisponível.")


@organizer.get("/api/auth/csrf")
def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return jsonify({"csrf_token": session["csrf"]})


@organizer.post("/api/auth/login")
def login():
    body = json_object()
    if set(body) != {"username", "password"} or not all(
        isinstance(body[key], str) for key in ("username", "password")
    ):
        raise InputError("Credenciais inválidas.")
    username = current_app.config.get("ORGANIZER_USERNAME")
    saved_hash = current_app.config.get("ORGANIZER_PASSWORD_HASH")
    if not username or not saved_hash:
        return error_response(503, "SERVICE_UNAVAILABLE", "Acesso ainda não configurado.")
    matched = check_password_hash(saved_hash, body["password"])
    if not (matched and hmac.compare_digest(body["username"], username)):
        return error_response(401, "INVALID_CREDENTIALS", "Usuário ou senha inválidos.")
    session.clear()
    session.permanent = True
    session["organizer_authenticated"] = True
    session["csrf"] = secrets.token_urlsafe(32)
    return jsonify({"ok": True, "csrf_token": session["csrf"]})


@organizer.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@organizer.get("/api/admin/dashboard")
def dashboard():
    report = store().summary()
    return jsonify({
        "counts": asdict(report["counts"]),
        "confirmed": report["confirmed"],
        "declined": report["declined"],
        "souvenir_children": report["souvenir_children"],
        "buffet_limit": report["buffet_limit"],
        "buffet_limit_reached": report["buffet_limit_reached"],
    })


@organizer.get("/api/admin/activity")
def activity():
    # Eventos operacionais não possuem nomes, telefones, tokens nem IDs familiares.
    return jsonify({"events": store().recent_activity(limit=50)})


@organizer.get("/api/admin/export.csv")
def export_csv():
    # Protegido pelo mesmo login da API administrativa; nunca servir publicamente.
    content = export_attendance_csv(store().summary())
    response = make_response(content, 200)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = 'attachment; filename="isadora-confirmacoes.csv"'
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@organizer.get("/api/admin/planning.csv")
def export_planning():
    # Planejamento quantitativo, sem nomes nem identificadores familiares.
    response = make_response(export_planning_csv(store().summary()), 200)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = 'attachment; filename="isadora-resumo-buffet.csv"'
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@organizer.get("/api/admin/settings")
def read_settings():
    return jsonify(settings_safe(store().settings()))


@organizer.put("/api/admin/settings")
def update_settings():
    data = json_object()
    if set(data) != {"venue", "edit_deadline_utc"}:
        raise InputError("Informe somente local e prazo de edição.")
    venue, raw_deadline = data["venue"], data["edit_deadline_utc"]
    if venue is not None and (not isinstance(venue, str) or len(venue) > 240):
        raise InputError("Local inválido.")
    deadline = None
    if raw_deadline is not None:
        if not isinstance(raw_deadline, str):
            raise InputError("Informe uma data com fuso horário.")
        try:
            deadline = datetime.fromisoformat(raw_deadline)
        except ValueError as exc:
            raise InputError("Prazo inválido.") from exc
        if deadline.utcoffset() is None:
            raise InputError("O prazo precisa informar o fuso horário.")
    store().configure(venue, deadline, datetime.now(timezone.utc))
    return jsonify(settings_safe(store().settings()))


@organizer.get("/organizar")
def organizer_page():
    # No private data in this template. Browser fetches it only after session login.
    return render_template("admin.html")


def invitation_store():
    existing = current_app.extensions.get("isadora_invitation_store")
    if existing is not None:
        return existing
    base_store = current_app.extensions["isadora_store"]
    secret = os.environ.get("TOKEN_SECRET", "")
    instance = InvitationStore(base_store.session_factory, secret)
    current_app.extensions["isadora_invitation_store"] = instance
    return instance


@organizer.errorhandler(InvitationImportError)
def invitation_input_error(exc):
    return error_response(422, "INVITATION_INVALID", str(exc))


@organizer.post("/api/admin/invitations/preview")
def invitations_preview():
    upload = request.files.get("file")
    if upload is None:
        raise InputError("Selecione um arquivo CSV.")
    rows = parse_guest_csv(upload.read(1_000_001))
    return jsonify({
        "count": len(rows),
        "preview": [{
            "family_name": row.family_name, "contact_name": row.contact_name,
            "whatsapp": row.whatsapp, "expected_guests": row.expected_guests
        } for row in rows[:10]]
    })


@organizer.post("/api/admin/invitations/import")
def invitations_import():
    upload = request.files.get("file")
    if upload is None:
        raise InputError("Selecione um arquivo CSV.")
    rows = parse_guest_csv(upload.read(1_000_001))
    issued = invitation_store().import_rows(rows)
    origin = os.environ.get("APP_PUBLIC_URL", "").rstrip("/")
    if not origin:
        raise RuntimeError("APP_PUBLIC_URL não configurada.")
    return jsonify({
        "created": len(issued),
        "invitations": [{
            **{key: value for key, value in item.items() if key != "token"},
            "url": origin + "/convite/" + item["token"],
            "whatsapp_url": "https://wa.me/" + item["whatsapp"] + "?text=" +
                __import__("urllib.parse", fromlist=["quote"]).quote(
                    "Olá, " + item["contact_name"] + "! Você está convidado(a) para comemorar os 2 aninhos da Isadora: " +
                    origin + "/convite/" + item["token"]
                )
        } for item in issued]
    }), 201


@organizer.get("/api/admin/invitations")
def invitations_list():
    return jsonify({"invitations": invitation_store().list_invitations()})


@organizer.post("/api/admin/invitations/<invitation_id>/sent")
def invitation_mark_sent(invitation_id):
    invitation_store().mark_sent(invitation_id)
    return jsonify({"ok": True})


@organizer.delete("/api/admin/invitations/<invitation_id>")
def invitation_revoke(invitation_id):
    invitation_store().revoke(invitation_id)
    return jsonify({"ok": True})
