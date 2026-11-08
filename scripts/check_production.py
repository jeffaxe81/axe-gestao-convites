#!/usr/bin/env python3
"""Verificações de leitura para homologação do Isadora publicado com TLS válido.

Não envia RSVPs nem acessa dados de convidados. Exige uma URL HTTPS real.
"""
import argparse
from http.cookies import CookieError, SimpleCookie
import json
import ipaddress
import re
import ssl
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPSHandler, HTTPRedirectHandler, Request, build_opener


def validate_origin(value):
    parsed = urlsplit(value)
    host = parsed.hostname
    if (
        parsed.scheme != "https" or not host
        or parsed.username or parsed.password or parsed.query or parsed.fragment
        or parsed.path not in ("", "/") or parsed.port is not None
        or not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", host)
        or host.endswith((".local", ".internal", ".test", ".example", ".invalid", ".localhost"))
    ):
        raise ValueError("Informe somente a origem HTTPS pública (sem caminhos ou credenciais).")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("Informe um domínio DNS, nunca IP privado ou público.")
    return "https://" + host, host


class _StrictOriginRedirect(HTTPRedirectHandler):
    """Reject off-origin redirects BEFORE contacting the redirected address."""
    def __init__(self, host):
        self.host = host

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlsplit(newurl)
        if target.scheme != "https" or target.netloc != self.host:
            raise RuntimeError("Redirecionamento externo ou HTTP bloqueado.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(origin, expected_host, path):
    request = Request(origin + path, headers={"Accept": "application/json"})
    opener = build_opener(HTTPSHandler(context=ssl.create_default_context()),
                          _StrictOriginRedirect(expected_host))
    try:
        response = opener.open(request, timeout=15)
    except HTTPError as exc:
        response = exc
    with response:
        final = urlsplit(response.geturl())
        if final.scheme != "https" or final.netloc != expected_host:
            raise RuntimeError("Redirecionamento fora da origem HTTPS esperada.")
        data = response.read(256 * 1024 + 1)
        if len(data) > 256 * 1024:
            raise RuntimeError("Resposta maior que o limite do teste.")
        return response.status, response.headers, data


def json_body(data):
    value = json.loads(data.decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("API retornou JSON inesperado.")
    return value


def has_safe_admin_cookie(headers):
    """Exige atributos reais do cookie Flask 'session', não substrings no nome/valor."""
    for header in headers.get_all("Set-Cookie", []):
        cookies = SimpleCookie()
        try:
            cookies.load(header)
        except CookieError:
            continue
        session_cookie = cookies.get("session")
        if session_cookie is None:
            continue
        if (bool(session_cookie["secure"]) and bool(session_cookie["httponly"])
                and session_cookie["samesite"].lower() == "lax"
                and session_cookie["path"] == "/"):
            return True
    return False


def verify(url):
    origin, hostname = validate_origin(url)
    status, headers, data = fetch(origin, hostname, "/health/ready")
    if status != 200 or json_body(data).get("status") != "ready":
        raise RuntimeError("Health check não está pronto.")

    status, headers, data = fetch(origin, hostname, "/api/event")
    event = json_body(data)
    if status != 200 or not {"name", "age", "starts_at", "venue"} <= set(event):
        raise RuntimeError("API pública de evento inválida.")
    forbidden = {"counts", "confirmed", "declined", "souvenir_children", "buffet_limit"}
    if forbidden.intersection(event):
        raise RuntimeError("Dados privados detectados na API pública.")

    status, headers, data = fetch(origin, hostname, "/api/admin/dashboard")
    if status != 401:
        raise RuntimeError("Painel administrativo acessível sem autenticação.")
    if forbidden.intersection(json_body(data)):
        raise RuntimeError("Dados privados retornados no erro administrativo.")

    status, headers, data = fetch(origin, hostname, "/")
    if status != 200 or not data:
        raise RuntimeError("Página dos convidados não disponível.")
    if "no-store" not in headers.get("Cache-Control", "").lower():
        raise RuntimeError("Cache-Control inadequado.")
    if "default-src" not in headers.get("Content-Security-Policy", ""):
        raise RuntimeError("CSP não encontrada.")
    if headers.get("X-Frame-Options", "").upper() != "DENY":
        raise RuntimeError("Anti-clickjacking não configurado.")
    if "max-age=" not in headers.get("Strict-Transport-Security", "").lower():
        raise RuntimeError("Proxy HTTPS não está emitindo HSTS.")

    status, headers, data = fetch(origin, hostname, "/api/auth/csrf")
    if status != 200 or "csrf_token" not in json_body(data):
        raise RuntimeError("Rota CSRF indisponível.")
    if not has_safe_admin_cookie(headers):
        raise RuntimeError("Cookie de sessão administrativa exige Secure, HttpOnly, SameSite=Lax e Path=/.")
    print("PASS: TLS, disponibilidade, acesso privado, CSP, HSTS e cookie seguro.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Origem HTTPS real")
    args = parser.parse_args()
    try:
        verify(args.url)
    except (ValueError, RuntimeError, URLError, json.JSONDecodeError, OSError) as exc:
        print("ERRO: {}".format(exc), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
