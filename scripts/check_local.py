#!/usr/bin/env python3
"""Read-only local acceptance check: no RSVP, admin login or database writes.

Requires the app to be running on loopback. All outgoing HTTP is restricted
to 127.0.0.1/localhost; redirects are blocked before they are followed.
"""
import argparse
from datetime import datetime
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_RESPONSE_BYTES = 256 * 1024


def local_origin(value):
    """Accept loopback HTTP with an explicit port, never a remote host or path."""
    if not isinstance(value, str):
        raise ValueError("Informe uma origem HTTP local válida.")
    try:
        url = urlsplit(value)
        port = url.port
    except ValueError as exc:
        raise ValueError("Porta local inválida.") from exc
    if (url.scheme != "http" or url.hostname not in ("127.0.0.1", "localhost")
            or not port or url.username or url.password
            or url.query or url.fragment or url.path not in ("", "/")
            or url.netloc not in (f"{url.hostname}:{port}",)):
        raise ValueError("Somente HTTP em 127.0.0.1/localhost com porta é permitido.")
    return f"http://{url.hostname}:{port}"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("Redirecionamento bloqueado na homologação local.")


def fetch_local(opener, origin, path):
    request = Request(origin + path, headers={"Accept": "application/json"})
    try:
        response = opener.open(request, timeout=8)
    except HTTPError as exc:
        response = exc
    with response:
        if urlsplit(response.geturl()).netloc != urlsplit(origin).netloc:
            raise RuntimeError("O destino da resposta mudou.")
        body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise RuntimeError("Resposta ultrapassou o limite de segurança.")
        return response.status, response.headers, body


def require_json(body):
    try:
        result = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise RuntimeError("A aplicação não retornou JSON válido.") from exc
    if not isinstance(result, dict):
        raise RuntimeError("A aplicação retornou um objeto JSON inválido.")
    return result


def inspect(url="http://127.0.0.1:8080"):
    """Read-only checks using a fresh unauthenticated client, with no PII output."""
    origin = local_origin(url)
    opener = build_opener(NoRedirect())
    results = {}

    def get(name, path, status):
        actual, headers, body = fetch_local(opener, origin, path)
        if actual != status:
            raise RuntimeError(f"{name}: HTTP {actual} (esperado {status}).")
        results[name] = "PASS"
        return headers, body

    _, health = get("health", "/health/ready", 200)
    if require_json(health).get("status") != "ready":
        raise RuntimeError("Banco de dados não está pronto.")

    _, event = get("event", "/api/event", 200)
    data = require_json(event)
    if not {"name", "age", "starts_at", "timezone", "venue"} <= set(data):
        raise RuntimeError("Dados públicos do evento incompletos.")
    if set(data) & {"counts", "confirmed", "declined", "souvenir_children", "buffet_limit"}:
        raise RuntimeError("Dados administrativos expostos publicamente.")
    try:
        if datetime.fromisoformat(data["starts_at"]).tzinfo is None:
            raise ValueError("Missing timezone")
    except (ValueError, TypeError, KeyError) as exc:
        raise RuntimeError("Data do evento sem horário/fuso válido.") from exc

    headers, page = get("guest_page", "/", 200)
    if b"<!doctype html" not in page[:100].lower():
        raise RuntimeError("A página pública não retornou HTML válido.")
    if "no-store" not in headers.get("Cache-Control", "").lower():
        raise RuntimeError("A página pública permite cache.")
    if "noindex" not in headers.get("X-Robots-Tag", "").lower():
        raise RuntimeError("Falta proteção contra indexação.")
    if "default-src" not in headers.get("Content-Security-Policy", ""):
        raise RuntimeError("A política CSP não está presente.")

    headers, calendar = get("calendar", "/evento.ics", 200)
    if ("text/calendar" not in headers.get("Content-Type", "").lower()
            or not calendar.startswith(b"BEGIN:VCALENDAR\r\n")
            or not calendar.endswith(b"END:VCALENDAR\r\n")):
        raise RuntimeError("Arquivo de calendário inválido.")

    for name, path in (
        ("admin_private", "/api/admin/dashboard"),
        ("planning_private", "/api/admin/planning.csv"),
        ("activity_private", "/api/admin/activity"),
    ):
        headers, body = get(name, path, 401)
        if "João" in body.decode("utf-8", "replace") or "confirmed" in require_json(body):
            raise RuntimeError("Dados privados detectados em resposta não autorizada.")

    _, csrf = get("csrf", "/api/auth/csrf", 200)
    token = require_json(csrf).get("csrf_token")
    if not isinstance(token, str) or len(token) < 20:
        raise RuntimeError("Proteção CSRF indisponível.")

    return {"origin": origin, "status": "PASS",
            "checks": results, "read_only": True, "rsvp_writes": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080",
                        help="Origem HTTP estritamente local (padrão: 127.0.0.1:8080)")
    parser.add_argument("--json", action="store_true",
                        help="Relatório resumido para registro da homologação")
    args = parser.parse_args()
    try:
        report = inspect(args.url)
    except (ValueError, RuntimeError, URLError, OSError) as exc:
        print("FALHA: " + str(exc), file=sys.stderr)
        raise SystemExit(1) from None
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("PASS: %d verificações locais, sem criar ou alterar RSVPs." %
              len(report["checks"]))
        print("PENDENTE: homologação HTTPS, celulares reais e backup externo.")


if __name__ == "__main__":
    main()
