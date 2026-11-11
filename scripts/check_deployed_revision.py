#!/usr/bin/env python3
"""Confere a revisão declarada da imagem da aplicação em execução.

Apenas leitura local: não reinicia contêineres, não acessa segredos e não
comprova, sozinho, o conteúdo interno da imagem ou a liberação operacional.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

if __package__:
    from .diagnose_release import ROOT, clean_revision
else:
    from diagnose_release import ROOT, clean_revision

SHA = re.compile(r"[0-9a-f]{40}\\Z")
CONTAINER_ID = re.compile(r"[0-9a-f]{12,64}\\Z")
# Metadado OPC de imagem propagado para o contêiner pelo Docker.
INSPECT_FORMAT = (
    '{{.State.Running}}|'
    '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}|'
    '{{index .Config.Labels "org.opencontainers.image.revision"}}'
)


def execute(command, root):
    """Uma chamada local de leitura, nunca um comando shell."""
    try:
        result = subprocess.run(
            command, cwd=str(root), capture_output=True,
            text=True, check=False, timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError("Docker não pôde ser consultado.") from None
    if result.returncode:
        # Não expor stderr/stdout: o erro pode conter variáveis do Compose.
        raise RuntimeError("Docker não pôde ser consultado.")
    return result.stdout.strip()


def inspect(root=ROOT, *, execute_command=execute, checkout=clean_revision):
    root = Path(root).resolve()
    sha = checkout(root)
    if not isinstance(sha, str) or not SHA.fullmatch(sha):
        raise RuntimeError("Revisão Git local inválida.")

    container = execute_command(["docker", "compose", "ps", "-q", "app"], root)
    if not CONTAINER_ID.fullmatch(container):
        raise RuntimeError("Não há exatamente um contêiner app identificável.")

    result = execute_command(
        ["docker", "inspect", "--type=container", "--format",
         INSPECT_FORMAT, container], root,
    )
    parts = result.split("|")
    if len(parts) != 3:
        raise RuntimeError("Metadados de imagem inválidos.")
    running, health, revision = parts
    if running != "true" or health != "healthy":
        raise RuntimeError("O contêiner app não está saudável.")
    if not SHA.fullmatch(revision):
        raise RuntimeError("Imagem sem revisão Git válida no rótulo Docker.")
    if revision != sha:
        raise RuntimeError("Revisão do contêiner difere do checkout Git.")

    return {
        "status": "PASS",
        "read_only": True,
        "checkout_sha": sha,
        "running_image_revision": revision,
        "running_container_healthy": True,
        "revision_label_matches_checkout": True,
        "backend_code_proven": False,
        "public_domain_verified": False,
        "release_approved": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = inspect()
    except (RuntimeError, ValueError, OSError) as exc:
        if args.json:
            print(json.dumps({
                "status": "BLOCKED", "read_only": True,
                "reason": str(exc), "release_approved": False,
            }, ensure_ascii=False))
        else:
            print("BLOQUEADO: " + str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("PASS: etiqueta Git da imagem em execução coincide com o checkout limpo.")
        print("NÃO comprova bytes do backend, publicação externa ou liberação real.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
