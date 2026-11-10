#!/usr/bin/env python3
"""Diagnóstico seguro dos gates automatizados da publicação Isadora.

Apenas consultas HTTP de leitura e inspeção de configuração local.
Não acessa dados de famílias, não envia RSVP e não autoriza divulgação.
"""
import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys

if __package__:
    from . import check_deployed_assets, check_local, check_production, preflight
else:
    import check_deployed_assets
    import check_local
    import check_production
    import preflight


ROOT = Path(__file__).resolve().parents[1]
HUMAN_GATES = (
    "dns_https_externo",
    "backup_externo_restaurado",
    "android_fisico",
    "iphone_fisico",
    "revisao_seguranca",
    "aceite_organizador",
)


def clean_revision(root):
    """Confere revisão Git e checkout limpo; nunca faz git pull/reset/fetch."""
    root = Path(root).resolve()

    def git(*args):
        outcome = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if outcome.returncode:
            raise RuntimeError("Falha ao verificar o checkout.")
        return outcome.stdout.strip()

    if Path(git("rev-parse", "--show-toplevel")).resolve() != root:
        raise RuntimeError("O diretório não é a raiz do repositório.")
    commit = git("rev-parse", "HEAD")
    if len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit):
        raise RuntimeError("SHA Git inválido.")
    if git("status", "--porcelain", "--untracked-files=normal"):
        raise RuntimeError("O checkout contém arquivos modificados ou não versionados.")
    return commit


def diagnose(url, *, root=ROOT, env_file=None, local_url=None,
             allow_proxy_hop=False):
    """Retorna relatório sanitizado; falhas nunca incluem credenciais/PII."""
    report = {
        "status": "BLOCKED",
        "read_only": True,
        "release_approved": False,
        "human_gates_pending": list(HUMAN_GATES),
        "checks": {},
    }

    def gate(name, fn):
        try:
            value = fn()
        except Exception:
            report["checks"][name] = "FAIL"
            report["failed_check"] = name
            raise RuntimeError("gate failed") from None
        report["checks"][name] = "PASS"
        return value

    try:
        # Rejeita origens inseguras antes de efetuar qualquer HTTP.
        origin = gate("public_url", lambda: check_production.validate_origin(url)[0])
        if local_url is not None:
            gate("local_url", lambda: check_local.local_origin(local_url))
        root = Path(root).resolve()
        report["checkout_sha"] = gate("checkout_clean", lambda: clean_revision(root))

        if env_file is not None:
            def local_config():
                values = preflight.load_env(env_file)
                errors = preflight.validate(
                    values, allow_proxy=allow_proxy_hop, allow_local=False,
                )
                if errors:
                    raise RuntimeError("Configuração incompleta.")
                config_origin = check_production.validate_origin(values["APP_PUBLIC_URL"])[0]
                if config_origin != origin:
                    raise RuntimeError("APP_PUBLIC_URL divergente.")
            gate("local_configuration", local_config)
        else:
            report["checks"]["local_configuration"] = "NOT_TESTED"

        if local_url is not None:
            gate("local_http", lambda: check_local.inspect(local_url))
        else:
            report["checks"]["local_http"] = "NOT_TESTED"

        def public_check():
            with redirect_stdout(io.StringIO()):
                check_production.verify(origin)
        gate("public_https", public_check)
        gate("published_assets", lambda: check_deployed_assets.inspect(origin, root))
        report["status"] = "AUTOMATED_PASS"
    except RuntimeError:
        pass
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Origem HTTPS pública sem caminho")
    parser.add_argument("--env-file", help="Arquivo .env privado, opcional")
    parser.add_argument("--local-url", help="Loopback HTTP: ex. http://127.0.0.1:8080")
    parser.add_argument("--allow-proxy-hop", action="store_true",
                        help="Somente após validar proxy que sobrescreve X-Forwarded-For")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = diagnose(
        args.url, env_file=args.env_file, local_url=args.local_url,
        allow_proxy_hop=args.allow_proxy_hop,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("Diagnóstico automatizado: " + report["status"])
        for name, status in report["checks"].items():
            print(f"  {name}: {status}")
        print("Liberação de convites reais: BLOQUEADA até seis evidências humanas.")
        print("Não comprova versão do backend nem o aceite operacional.")
    return 0 if report["status"] == "AUTOMATED_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
