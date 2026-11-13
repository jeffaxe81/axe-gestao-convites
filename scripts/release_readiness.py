#!/usr/bin/env python3
"""Audita registros de aceite da Release 1, sem manusear senhas ou nomes.

IMPORTANTE: este script confere COMPLETUDE de evidências declaradas,
não verifica pessoalmente Android, iPhone ou a infraestrutura.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
MAX_MANIFEST_BYTES = 64 * 1024


def load_private_manifest(filename, *, root=ROOT):
    """Lê somente arquivo 0600 de diretório 0700 fora do checkout.

    Usa O_NOFOLLOW e fstat no descritor aberto para não seguir symlinks
    finais, nem confiar em uma checagem de permissões anterior ao open.
    Nenhuma mensagem de erro inclui o nome do arquivo ou seu conteúdo.
    """
    candidate = Path(filename).expanduser()
    if not candidate.is_absolute() or candidate.suffix != ".json":
        raise ValueError("O manifesto deve ser um arquivo .json de caminho absoluto.")
    try:
        directory = candidate.parent.resolve(strict=True)
        checkout = Path(root).resolve()
        directory_stat = directory.stat()
        if not directory.is_dir() or directory == checkout or checkout in directory.parents:
            raise ValueError("O manifesto deve ficar fora do repositório.")
        if (directory_stat.st_mode & 0o077) or (
            hasattr(os, "geteuid") and directory_stat.st_uid != os.geteuid()
        ):
            raise ValueError("A pasta do manifesto deve pertencer ao operador e ser privada (0700).")
        if candidate.is_symlink():
            raise ValueError("Links simbólicos não são aceitos para evidências humanas.")
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        # A FIFO can block on open() before fstat rejects non-regular files.
        # Nonblocking open permits rejecting it without waiting for a writer.
        if hasattr(os, "O_NONBLOCK"):
            flags |= os.O_NONBLOCK
        fd = os.open(candidate, flags)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or
                    (hasattr(os, "geteuid") and info.st_uid != os.geteuid())):
                raise ValueError("O manifesto deve ser arquivo privado (0600) do operador.")
            if info.st_size > MAX_MANIFEST_BYTES:
                raise ValueError("Manifesto excede o tamanho máximo permitido.")
            raw = stream.read(MAX_MANIFEST_BYTES + 1)
        if len(raw) > MAX_MANIFEST_BYTES:
            raise ValueError("Manifesto excede o tamanho máximo permitido.")
        return json.loads(raw.decode("utf-8"))
    except (OSError, RuntimeError, UnicodeError, json.JSONDecodeError):
        raise ValueError("Não foi possível ler manifesto privado válido.") from None


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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-file", required=True)
    parser.add_argument("--json", action="store_true",
                        help="Resumo JSON sem referências privadas, sem liberação automática")
    args = parser.parse_args(argv)
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
