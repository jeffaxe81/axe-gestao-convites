#!/usr/bin/env python3
"""Change only APP_PUBLIC_URL in a private .env, without a domain during development.

Use --local now, or --domain later. Does not contact DNS or expose secrets.
Recreate the app container after updating this file.
"""
import argparse
import os
from pathlib import Path
import re
import stat
import tempfile

if __package__:
    from scripts.check_production import validate_origin
else:
    from check_production import validate_origin

LOCAL_ORIGIN = "http://127.0.0.1:8080"


def normalize_origin(domain=None, *, local=False):
    if local:
        if domain is not None:
            raise ValueError("Escolha --domain ou --local, nunca ambos.")
        return LOCAL_ORIGIN
    if not isinstance(domain, str) or not domain.strip():
        raise ValueError("Informe um domínio ou escolha --local.")
    candidate = domain.strip()
    if not candidate.startswith("https://"):
        if "://" in candidate:
            raise ValueError("Domínio público deve utilizar HTTPS.")
        candidate = "https://" + candidate
    return validate_origin(candidate)[0]


def update_env(path, origin):
    """Update one variable without disclosing/changing private values."""
    path = Path(path).expanduser()
    if path.is_symlink() or not path.is_file():
        raise ValueError("Use um arquivo .env existente e regular, sem link simbólico.")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError("Proteja o arquivo .env com chmod 600 antes de configurar o domínio.")
    contents = path.read_bytes().decode("utf-8")
    lines = contents.splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if re.match(r"^APP_PUBLIC_URL=", line)]
    if len(matches) != 1:
        raise ValueError("O arquivo .env deve conter exatamente uma variável APP_PUBLIC_URL.")
    line = lines[matches[0]]
    ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
    lines[matches[0]] = "APP_PUBLIC_URL=" + origin + ending
    fd, temp = tempfile.mkstemp(prefix=".public-url-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as output:
            output.write("".join(lines))
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return origin


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--local", action="store_true", help="Manter execução local sem domínio")
    target.add_argument("--domain", help="Domínio futuro, ex.: convites.seudominio.com.br")
    parser.add_argument("--env-file", default=".env", help="Arquivo privado (padrão .env)")
    args = parser.parse_args()
    try:
        origin = normalize_origin(args.domain, local=args.local)
        update_env(args.env_file, origin)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    print("APP_PUBLIC_URL configurada: " + origin)
    print("Recrie apenas o serviço app: docker compose up -d --no-deps --force-recreate app")
    if args.local:
        print("MODO LOCAL: não publicar nem enviar convites.")
    else:
        print("DOMÍNIO CONFIGURADO: DNS/TLS e verificação externa ainda são obrigatórios.")


if __name__ == "__main__":
    main()
