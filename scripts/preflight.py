#!/usr/bin/env python3
"""Pré-checagem local e segura antes de publicar o Isadora na internet.

Não conecta ao banco nem verifica HTTPS real. Não imprime segredos.
"""
import argparse
import ipaddress
import os
from pathlib import Path
import re
import stat
import sys
from urllib.parse import urlsplit

REQUIRED = (
    "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD",
    "MYSQL_ROOT_PASSWORD", "TOKEN_SECRET", "SESSION_SECRET",
    "ORGANIZER_USERNAME", "ORGANIZER_PASSWORD_HASH", "APP_PUBLIC_URL",
)
SECRET_FIELDS = (
    "MYSQL_PASSWORD", "MYSQL_ROOT_PASSWORD", "TOKEN_SECRET", "SESSION_SECRET"
)


def load_env(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("Arquivo de configuração regular não encontrado.")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise ValueError("Proteja o .env com chmod 600 (sem permissões de grupo/outros).")
    values = {}
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError("Linha {} do .env inválida.".format(n))
        key, value = line.split("=", 1)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            raise ValueError("Nome de variável inválido na linha {}.".format(n))
        if key in values:
            raise ValueError("Variável repetida na linha {}.".format(n))
        values[key] = value.strip().strip("'").strip('"')
    return values


def validate(values, *, allow_proxy=False):
    errors = []
    for name in REQUIRED:
        if not values.get(name):
            errors.append("Configuração obrigatória ausente: " + name)
    for name in SECRET_FIELDS:
        value = values.get(name, "")
        if len(value) < 32 or any(x in value.upper() for x in ("SUBSTITUIR", "CHANGEME", "EXAMPLE", "TESTSECRET")):
            errors.append(name + " deve ter pelo menos 32 caracteres aleatórios.")
    if values.get("SESSION_SECRET") == values.get("TOKEN_SECRET"):
        errors.append("SESSION_SECRET e TOKEN_SECRET devem ser diferentes.")
    if values.get("MYSQL_ROOT_PASSWORD") == values.get("MYSQL_PASSWORD"):
        errors.append("Use senhas diferentes para MySQL root e usuário da aplicação.")
    if values.get("MYSQL_USER", "").lower() == "root":
        errors.append("Não use root como MYSQL_USER.")
    saved_hash = values.get("ORGANIZER_PASSWORD_HASH", "")
    if not saved_hash.startswith(("scrypt:", "pbkdf2:")) or "$" not in saved_hash:
        errors.append("ORGANIZER_PASSWORD_HASH precisa conter hash Werkzeug real.")
    try:
        url = urlsplit(values.get("APP_PUBLIC_URL", ""))
        hostname = url.hostname
        if (url.scheme != "https" or not hostname
            or url.username or url.password or url.query or url.fragment
            or url.path not in ("", "/") or url.port is not None
            or not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", hostname)):
            errors.append("APP_PUBLIC_URL deve ser apenas a origem HTTPS do domínio público.")
        if hostname:
            try:
                ipaddress.ip_address(hostname)
                errors.append("APP_PUBLIC_URL deve usar um domínio DNS, não endereço IP.")
            except ValueError:
                pass
            if hostname.endswith((".local", ".internal", ".example", ".test", ".invalid", ".localhost")):
                errors.append("APP_PUBLIC_URL deve usar domínio de produção.")
    except ValueError:
        errors.append("APP_PUBLIC_URL inválida.")
    proxy = values.get("TRUSTED_PROXY_HOPS", "0")
    if proxy not in {"0", "1"}:
        errors.append("TRUSTED_PROXY_HOPS só pode ser 0 ou 1.")
    if proxy == "1" and not allow_proxy:
        errors.append("Uso de proxy confiável exige verificação manual e --allow-proxy-hop.")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--allow-proxy-hop", action="store_true")
    args = parser.parse_args()
    try:
        values = load_env(args.env_file)
        errors = validate(values, allow_proxy=args.allow_proxy_hop)
    except (OSError, UnicodeError, ValueError) as exc:
        print("FALHA: {}".format(exc), file=sys.stderr)
        raise SystemExit(1) from None
    if errors:
        for error in errors:
            print("FALHA: {}".format(error), file=sys.stderr)
        raise SystemExit(1)
    print("PASS: configuração básica, segredos, permissões e origem HTTPS.")
    print("PENDENTE: DNS/TLS reais, controles do proxy/WAF, backup externo e celulares físicos.")


if __name__ == "__main__":
    main()
