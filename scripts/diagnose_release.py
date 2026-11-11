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
             allow_proxy_hop=False, require_local_gates=False,
             require_deployed_revision=False):
    """Retorna relatório sanitizado; falhas nunca incluem credenciais/PII."""
    local_inputs = (env_file is not None, local_url is not None)
    # Cobertura informa entradas fornecidas, não sucesso ou homologação.
    input_coverage = ("COMPLETE" if all(local_inputs) else
                      "PARTIAL" if any(local_inputs) else "NOT_TESTED")
    report = {
        "status": "BLOCKED",
        "read_only": True,
        "release_approved": False,
        "human_gates_pending": list(HUMAN_GATES),
        "local_input_coverage": input_coverage,
        "host_checks_ready": False,
        "image_revision_verified": False,
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
        if require_local_gates and (env_file is None or local_url is None):
            report["checks"]["required_local_inputs"] = "FAIL"
            report["failed_check"] = "required_local_inputs"
            return report
        # A revisão Docker só faz sentido no host, com diagnóstico local completo.
        if require_deployed_revision and not require_local_gates:
            report["checks"]["required_host_mode_for_revision"] = "FAIL"
            report["failed_check"] = "required_host_mode_for_revision"
            return report
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

        if require_deployed_revision:
            def deployed_image_revision():
                # Import local evita circularidade: check_deployed_revision
                # reutiliza clean_revision deste módulo.
                if __package__:
                    from . import check_deployed_revision
                else:
                    import check_deployed_revision
                current = check_deployed_revision.inspect(
                    root=root, checkout=lambda _root: report["checkout_sha"],
                )
                if (current.get("status") != "PASS" or
                        current.get("running_image_revision") != report["checkout_sha"] or
                        current.get("revision_label_matches_checkout") is not True or
                        current.get("running_container_healthy") is not True):
                    raise RuntimeError("Revisão da imagem não confirmada.")
            gate("deployed_revision", deployed_image_revision)
            report["image_revision_verified"] = True
        else:
            report["checks"]["deployed_revision"] = "NOT_TESTED"

        def public_check():
            with redirect_stdout(io.StringIO()):
                check_production.verify(origin)
        gate("public_https", public_check)
        gate("published_assets", lambda: check_deployed_assets.inspect(origin, root))
        report["host_checks_ready"] = all(local_inputs)
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
    parser.add_argument("--require-local-gates", action="store_true",
                        help="Bloqueia sem --env-file e --local-url (uso no policorp)")
    parser.add_argument("--require-deployed-revision", action="store_true",
                        help="Exige também contêiner Docker app saudável, com SHA igual ao checkout; requer --require-local-gates")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = diagnose(
        args.url, env_file=args.env_file, local_url=args.local_url,
        allow_proxy_hop=args.allow_proxy_hop,
        require_local_gates=args.require_local_gates,
        require_deployed_revision=args.require_deployed_revision,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("Diagnóstico automatizado: " + report["status"])
        for name, status in report["checks"].items():
            print(f"  {name}: {status}")
        print("Cobertura das entradas locais: " + report["local_input_coverage"])
        print("Revisão declarada da imagem verificada: " +
              ("SIM" if report.get("image_revision_verified", False) else "NÃO"))
        print("Liberação de convites reais: BLOQUEADA até seis evidências humanas.")
        print("Não comprova versão do backend nem o aceite operacional.")
    return 0 if report["status"] == "AUTOMATED_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
