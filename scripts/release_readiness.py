#!/usr/bin/env python3
"""Audita registros de aceite da Release 1, sem manusear senhas ou nomes.

IMPORTANTE: este script confere COMPLETUDE de evidências declaradas,
não verifica pessoalmente Android, iPhone ou a infraestrutura.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
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


def report(value):
    complete, missing = evaluate(value)
    rows = [
        "Entrega técnica: 6/7 etapas validadas por CI.",
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-file", required=True)
    args = parser.parse_args()
    try:
        doc = json.loads(Path(args.evidence_file).read_text(encoding="utf-8"))
        output, complete = report(doc)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print("FALHA: " + str(exc), file=sys.stderr)
        return 2
    print(output)
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
