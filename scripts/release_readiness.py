#!/usr/bin/env python3
"""Audita a Release 1 por escopo técnico ou por evidências operacionais.

O modo técnico dispensa ensaios físicos e de host e exige CI verde na main.
Nenhum modo confere automaticamente autorização de produção.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import stat
import sys

GATES = {
    "dns_https": "DNS e TLS públicos com checagem HTTPS externa",
    "backup_externo": "Backup cifrado externo e restauração real isolada",
    "android_real": "PDF via WhatsApp e RSVP no Android físico",
    "iphone_real": "PDF via WhatsApp e RSVP no iPhone físico",
    "revisao_seguranca": "Revisão de segurança independente e correções",
    "aceite_operacional": "Responsável aprovou a liberação pública",
}


def evaluate(value):
    if not isinstance(value, dict) or set(value) != set(GATES):
        raise ValueError("O arquivo deve conter exatamente as seis verificações de liberação.")
    complete, missing = [], []
    timestamps = {}
    for key, label in GATES.items():
        entry = value[key]
        if not isinstance(entry, dict) or set(entry) != {
            "verified", "verified_at", "evidence_ref"
        } or type(entry["verified"]) is not bool:
            raise ValueError("Estrutura inválida em " + key)
        if entry["verified"]:
            if not isinstance(entry["evidence_ref"], str) or len(
                entry["evidence_ref"].strip()
            ) < 8:
                raise ValueError("Falta referência de evidência em " + key)
            try:
                recorded = datetime.fromisoformat(entry["verified_at"])
                if recorded.tzinfo is None or recorded.utcoffset() is None:
                    raise ValueError()
                # Aceita pequena margem de relógio; impede atestados datados no futuro.
                if recorded > datetime.now(timezone.utc) + timedelta(minutes=5):
                    raise ValueError()
            except (TypeError, ValueError):
                raise ValueError("Data ausente, sem fuso ou futura em " + key) from None
            complete.append(key)
            timestamps[key] = recorded.astimezone(timezone.utc)
        else:
            if entry["verified_at"] is not None or entry["evidence_ref"] is not None:
                raise ValueError("Não registre evidência de teste pendente em " + key)
            missing.append(key)
    # A autorização não pode ser emitida antes dos demais comprovantes.
    if "aceite_operacional" in complete:
        prior_gates = set(GATES) - {"aceite_operacional"}
        if not prior_gates.issubset(complete):
            raise ValueError("Aceite operacional exige as outras cinco evidências.")
        accepted_at = timestamps["aceite_operacional"]
        if any(accepted_at < timestamps[key] for key in prior_gates):
            raise ValueError("Aceite operacional anterior a outra evidência.")
    return complete, missing


def status_payload(value):
    """Resumo estruturado e sem referências privadas; nunca autoriza publicação."""
    complete, missing = evaluate(value)
    return {
        "schema_version": 1,
        "technical_gates_documented": 10,
        "technical_gates_total": 10,
        "operational_steps_complete": 6,
        "operational_steps_total": 7,
        "human_evidence_declared": len(complete),
        "human_evidence_total": len(GATES),
        "human_gates_pending": missing,
        "ready_for_human_review": not missing,
        "ci_or_deployed_revision_verified": False,
        "release_approved": False,
    }


def report(value):
    complete, missing = evaluate(value)
    rows = [
        "Prontidão técnica documentada: 10/10 critérios; esta ferramenta não valida CI ou SHA.",
        "Etapas operacionais: 6/7 concluídas; liberação ainda depende de homologação real.",
        "Homologação operacional: {}/{} verificações com evidências declaradas.".format(
            len(complete), len(GATES)
        ),
    ]
    for key, label in GATES.items():
        rows.append(("OK: " if key in complete else "PENDENTE: ") + label)
    if missing:
        rows.append("LIBERAÇÃO BLOQUEADA: não divulgar links de convites reais.")
    else:
        rows.append("EVIDÊNCIAS PREENCHIDAS: submeter a conferência humana final.")
        rows.append("Este relatório NÃO comprova, por si só, testes físicos ou TLS real.")
    return "\n".join(rows), not missing



MAX_MANIFEST_BYTES = 64 * 1024
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_private_manifest(filename, *, root=PROJECT_ROOT):
    """Open a private evidence file without following a final symlink.

    The shipped JSON template in docs is intentionally public and empty;
    actual human evidence must live outside Git in a private directory.
    """
    path = Path(filename).expanduser()
    if not path.is_absolute() or path.suffix != ".json":
        raise ValueError("Informe um caminho absoluto para o manifesto privado .json.")
    try:
        parent = path.parent.resolve(strict=True)
        checkout = Path(root).resolve()
        directory = parent.stat()
    except (OSError, RuntimeError):
        raise ValueError("Diretório privado do manifesto não encontrado.") from None
    if parent == checkout or checkout in parent.parents:
        raise ValueError("O manifesto privado deve ficar fora do repositório.")
    if not parent.is_dir():
        raise ValueError("O diretório privado do manifesto é inválido.")
    if os.name == "posix" and (
        directory.st_mode & 0o077 or directory.st_uid != os.geteuid()
    ):
        raise ValueError("O diretório do manifesto deve pertencer ao operador e usar 0700.")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    try:
        # Open against the validated parent and inspect the opened descriptor,
        # not just the path. Never print the file contents in error messages.
        fd = os.open(parent / path.name, flags)
        with os.fdopen(fd, "rb") as source:
            metadata = os.fstat(source.fileno())
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError("O manifesto deve ser um arquivo regular.")
            if os.name == "posix" and (
                metadata.st_mode & 0o077 or metadata.st_uid != os.geteuid()
            ):
                raise ValueError("O manifesto deve pertencer ao operador e usar 0600.")
            if metadata.st_size > MAX_MANIFEST_BYTES:
                raise ValueError("Manifesto privado acima do limite de 64 KB.")
            raw = source.read(MAX_MANIFEST_BYTES + 1)
            if len(raw) > MAX_MANIFEST_BYTES:
                raise ValueError("Manifesto privado acima do limite de 64 KB.")
    except OSError:
        raise ValueError("Manifesto privado inacessível, inválido ou link simbólico.") from None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError("O manifesto privado não contém JSON UTF-8 válido.") from None



def technical_status(sha, run_id, *, verify_ci=None):
    """Conclui SOMENTE o escopo técnico, conferindo a CI da main atual."""
    if verify_ci is None:
        if __package__:
            from .check_green_main_ci import verify as verify_ci
        else:
            from check_green_main_ci import verify as verify_ci
    checked = verify_ci(sha, run_id)
    if (
        checked.get("status") != "PASS"
        or checked.get("ci_main_verified") is not True
        or checked.get("approved_sha") != sha
        or checked.get("workflow_run_id") != run_id
        or checked.get("release_approved") is not False
    ):
        raise RuntimeError("CI principal não comprovada para o escopo técnico.")
    return {
        "schema_version": 1,
        "status": "PASS",
        "scope": "technical_only",
        "technical_gates_complete": 10,
        "technical_gates_total": 10,
        "technical_completion_percent": 100,
        "ci_main_verified": True,
        "approved_sha": sha,
        "workflow_run_id": run_id,
        "real_world_tests_excluded": True,
        "real_world_tests_executed_by_report": False,
        "operational_status": "NOT_EVALUATED",
        "ready_for_publication": False,
        "release_approved": False,
    }


def technical_report(data):
    """Texto sem qualquer insinuação de homologação de produção."""
    return (
        "PASS: escopo de desenvolvimento e testes automatizados concluído: 10/10 (100%).\n"
        "CI verde da main confirmada no SHA {} (run #{}).\n"
        "Testes físicos e do ambiente real: FORA DESTE ESCOPO, NÃO AVALIADOS.\n"
        "PUBLICAÇÃO E CONVITES REAIS: NÃO AUTORIZADOS por este relatório."
    ).format(data["approved_sha"], data["workflow_run_id"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("technical", "operational"),
                        default="operational",
                        help="technical: só CI e código; operational: evidências reais")
    parser.add_argument("--sha", help="SHA atual da main, para modo técnico")
    parser.add_argument("--run-id", type=int,
                        help="ID da CI verde da main, para modo técnico")
    parser.add_argument("--evidence-file",
                        help="Manifesto privado necessário apenas no modo operacional")
    parser.add_argument("--json", action="store_true",
                        help="Resumo JSON sem referências privadas, sem liberação automática")
    args = parser.parse_args(argv)
    if args.scope == "technical":
        if args.evidence_file is not None or args.sha is None or args.run_id is None:
            parser.error("Modo técnico exige --sha e --run-id e não aceita --evidence-file.")
        try:
            result = technical_status(args.sha, args.run_id)
        except (OSError, RuntimeError, ValueError):
            result = {
                "status": "BLOCKED", "scope": "technical_only",
                "ci_main_verified": False, "real_world_tests_excluded": True,
                "operational_status": "NOT_EVALUATED",
                "ready_for_publication": False, "release_approved": False,
            }
            print(
                json.dumps(result, ensure_ascii=False, sort_keys=True)
                if args.json else
                "BLOQUEADO: CI da main atual não comprovada; não há aceite técnico.",
                file=sys.stdout if args.json else sys.stderr,
            )
            return 1
        print(
            json.dumps(result, ensure_ascii=False, sort_keys=True)
            if args.json else technical_report(result)
        )
        return 0
    if args.evidence_file is None or args.sha is not None or args.run_id is not None:
        parser.error("Modo operacional exige --evidence-file e não aceita --sha/--run-id.")
    try:
        doc = load_private_manifest(args.evidence_file)
        if args.json:
            summary = status_payload(doc)
            output = json.dumps(summary, ensure_ascii=False, sort_keys=True)
            complete = summary["ready_for_human_review"]
        else:
            output, complete = report(doc)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print("FALHA: " + str(exc), file=sys.stderr)
        return 2
    print(output)
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
