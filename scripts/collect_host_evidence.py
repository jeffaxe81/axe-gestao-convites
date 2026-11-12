#!/usr/bin/env python3
"""Salva evidência AUTOMÁTICA e sanitizada de diagnóstico no host policorp.

Não grava no banco, não altera Docker/rede e jamais aprova os seis gates humanos.
O único efeito de escrita é um novo arquivo privado fora do repositório.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
import sys

if __package__:
    from . import diagnose_release
else:
    import diagnose_release

ROOT = diagnose_release.ROOT
SHA = re.compile(r"[0-9a-f]{40}\Z")
ALLOWED_CHECKS = frozenset((
    "public_url", "local_url", "expected_revision_input",
    "expected_revision_host_mode", "ci_main_inputs",
    "required_local_inputs", "required_host_mode_for_revision",
    "checkout_clean", "expected_revision", "ci_main",
    "local_configuration", "local_http", "deployed_revision",
    "public_https", "published_assets",
))
ALLOWED_CHECK_RESULTS = frozenset(("PASS", "FAIL", "NOT_TESTED"))


def private_destination(filename, *, root=ROOT):
    """Requer diretório privado (0700) fora do checkout e arquivo inexistente."""
    target = Path(filename).expanduser()
    if not target.is_absolute() or not target.name.endswith(".json"):
        raise ValueError("Escolha um caminho absoluto para um novo arquivo .json.")
    try:
        parent = target.parent.resolve(strict=True)
        root = Path(root).resolve()
        metadata = parent.stat()
    except (OSError, RuntimeError):
        raise ValueError("Diretório privado da evidência não encontrado.") from None
    if not parent.is_dir() or parent == root or root in parent.parents:
        raise ValueError("Guarde a evidência fora do repositório.")
    if metadata.st_mode & 0o077 or (
        hasattr(os, "geteuid") and metadata.st_uid != os.geteuid()
    ):
        raise ValueError("O diretório da evidência precisa pertencer ao operador e ser privado (0700).")
    target = parent / target.name
    # O_EXCL no momento da gravação também protege contra concorrência/links.
    if target.exists() or target.is_symlink():
        raise ValueError("O arquivo da evidência já existe. Não sobrescrever.")
    return target


def sanitized_snapshot(report, *, at=None):
    """Permite somente campos conhecidos; descarta integralmente saídas e segredos."""
    if not isinstance(report, dict) or report.get("status") not in (
        "BLOCKED", "AUTOMATED_PASS"
    ):
        raise ValueError("Diagnóstico não retornou um estado reconhecido.")
    checks = report.get("checks")
    if not isinstance(checks, dict) or not checks:
        raise ValueError("Diagnóstico não retornou gates válidos.")
    if any(
        key not in ALLOWED_CHECKS or status not in ALLOWED_CHECK_RESULTS
        for key, status in checks.items()
    ):
        raise ValueError("Diagnóstico retornou um gate não reconhecido.")
    failed = report.get("failed_check")
    if failed is not None and (failed not in checks or checks[failed] != "FAIL"):
        raise ValueError("Falha do diagnóstico inconsistente.")
    sha = report.get("checkout_sha")
    if sha is not None and (not isinstance(sha, str) or not SHA.fullmatch(sha)):
        raise ValueError("SHA do checkout inválido.")
    approved = report.get("expected_sha")
    if approved is not None and (
        not isinstance(approved, str) or not SHA.fullmatch(approved)
    ):
        raise ValueError("SHA esperado inválido.")
    run_id = report.get("ci_main_run_id")
    if run_id is not None and (
        type(run_id) is not int or not 0 < run_id <= 9999999999999999999
    ):
        raise ValueError("ID da CI inválido.")
    if report.get("release_approved") is not False:
        raise ValueError("O diagnóstico não pode autorizar liberação operacional.")
    instant = at if at is not None else datetime.now(timezone.utc)
    if not isinstance(instant, datetime) or instant.tzinfo is None:
        raise ValueError("Carimbo de data/hora inválido.")
    strict_pass = (
        report["status"] == "AUTOMATED_PASS"
        and report.get("host_checks_ready") is True
        and report.get("image_revision_verified") is True
        and report.get("expected_revision_checked") is True
        and report.get("ci_main_verified") is True
        and all(checks.get(key) == "PASS" for key in (
            "expected_revision", "ci_main", "local_configuration",
            "local_http", "deployed_revision", "public_https",
            "published_assets",
        ))
        and sha == approved
        and run_id is not None
    )
    return {
        "schema_version": 1,
        "generated_at_utc": instant.astimezone(timezone.utc).isoformat(),
        "kind": "diagnostico_automatizado_somente",
        "status": report["status"],
        "host_automated_gates_pass": strict_pass,
        "checkout_sha": sha,
        "selected_sha": approved,
        "verified_ci_run_id": run_id,
        "checks": {key: checks[key] for key in sorted(checks)},
        "failed_check": failed,
        "human_gates_pending": list(diagnose_release.HUMAN_GATES),
        "human_evidence_certified_by_snapshot": False,
        "release_approved": False,
        "contains_guest_data": False,
    }


def save_private(target, report):
    """Cria exatamente um arquivo 0600, sem sobrescrever ou seguir symlink."""
    data = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(target, flags, 0o600)
    except OSError:
        raise RuntimeError("Não foi possível criar o arquivo privado de evidências.") from None
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
    except OSError:
        try:
            target.unlink()
        except OSError:
            pass
        raise RuntimeError("Falha ao gravar a evidência privada.") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True,
                        help="Novo arquivo absoluto .json em diretório 0700, fora do Git")
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--ci-run-id", type=int, required=True)
    parser.add_argument("--url", default="https://isadora2anos.org")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--local-url", default="http://127.0.0.1:8080")
    parser.add_argument("--allow-proxy-hop", action="store_true",
                        help="Somente após revisar proxy que reescreve cabeçalhos")
    parser.add_argument("--json", action="store_true",
                        help="Mostra apenas o resumo sanitizado, sem segredos")
    args = parser.parse_args(argv)
    try:
        target = private_destination(args.output)
        diagnostic = diagnose_release.diagnose(
            args.url, env_file=args.env_file, local_url=args.local_url,
            allow_proxy_hop=args.allow_proxy_hop, require_local_gates=True,
            require_deployed_revision=True, expected_sha=args.expected_sha,
            ci_run_id=args.ci_run_id,
        )
        snapshot = sanitized_snapshot(diagnostic)
        save_private(target, snapshot)
    except (ValueError, RuntimeError) as exc:
        # Mensagens controladas, nunca imprimir dados brutos do host.
        print("BLOQUEADO: " + str(exc), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("Relatório automatizado sanitizado gravado em arquivo privado (0600).")
        print("Diagnóstico: " + snapshot["status"])
        print("Aprovação para envio real: NÃO; seis gates humanos continuam pendentes.")
    return 0 if snapshot["host_automated_gates_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
