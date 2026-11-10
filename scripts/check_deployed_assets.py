#!/usr/bin/env python3
"""Compara arquivos estáticos da implantação HTTPS com esta cópia do projeto.

Somente GETs públicos; não envia RSVP, usa login ou consulta dados pessoais.
Este teste NÃO valida a versão do backend nem homologa o ambiente por completo.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from urllib.error import URLError

if __package__:
    from .check_production import fetch, validate_origin
else:  # Suporta python scripts/check_deployed_assets.py sem instalar o pacote
    from check_production import fetch, validate_origin

ASSETS = ("site.css", "guest.js", "admin.css", "admin.js")
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def inspect(url, source_root=PROJECT_ROOT):
    origin, hostname = validate_origin(url)
    root = Path(source_root)
    checked = []
    for filename in ASSETS:
        local = root / "app" / "static" / filename
        if not local.is_file() or local.is_symlink():
            raise RuntimeError(f"Arquivo local ausente ou inseguro: {filename}.")
        expected = sha256(local.read_bytes()).digest()
        status, _headers, deployed = fetch(origin, hostname, f"/static/{filename}")
        if status != 200:
            raise RuntimeError(f"Arquivo publicado indisponível: {filename} (HTTP {status}).")
        if sha256(deployed).digest() != expected:
            raise RuntimeError(
                f"Versão diferente de {filename}: verifique checkout, publicação e cache."
            )
        checked.append(filename)
    return {
        "status": "PASS", "read_only": True, "checked_assets": len(checked),
        "files": checked, "backend_version_verified": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Origem pública HTTPS, sem caminho")
    parser.add_argument("--json", action="store_true", help="Relatório sem dados pessoais")
    args = parser.parse_args(argv)
    try:
        report = inspect(args.url)
    except (OSError, ValueError, RuntimeError, URLError) as exc:
        if args.json:
            print(json.dumps({"status": "FAIL", "read_only": True,
                              "reason": str(exc)}, ensure_ascii=False))
        else:
            print(f"FALHA: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(f"PASS: {report['checked_assets']} arquivos públicos coincidem com o checkout.")
        print("ATENÇÃO: o backend, o banco e a homologação operacional não são verificados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
