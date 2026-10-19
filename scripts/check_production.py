#!/usr/bin/env python3
"""Verificações de leitura para homologação do Isadora publicado com TLS válido.

Não envia RSVPs nem acessa dados de convidados. Exige uma URL HTTPS real.
"""
import argparse
import json
import ssl
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def validate_origin(value):
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https" or not parsed.hostname
        or parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        or parsed.username or parsed.password or parsed.query or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise ValueError("Informe somente a origem HTTPS pública (sem caminhos ou credenciais).")
    return value.rstrip("/"), parsed.netloc


def fetch(origin, expected_host, path):
    request = Request(origin + path, headers={"Accept": "application/json"})
    try:
        response = urlopen(request, timeout=15, context=ssl.create_default_context())
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
    cookies = headers.get_all("Set-Cookie", [])
    if not cookies or not any(
        "secure" in c.lower() and "httponly" in c.lower() for c in cookies
    ):
        raise RuntimeError("Cookie administrativo não tem Secure e HttpOnly.")
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
