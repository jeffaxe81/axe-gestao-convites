#!/usr/bin/env python3
"""Verifica somente leitura se o SHA escolhido é a main atual com CI verde.

Consulta exclusivamente endpoints fixos da API pública do GitHub; não acessa
dados de convidados, não usa credenciais e não substitui aceite operacional.
"""
import argparse
import json
import re
import ssl
import sys
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

REPO = "jeffaxe81/axe-gestao-convites"
API = "https://api.github.com/repos/" + REPO
WORKFLOW = ".github/workflows/ci.yml"
MAX_RESPONSE = 64 * 1024
SHA_PATTERN = re.compile(r"[0-9a-f]{40}\Z")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("Redirecionamento não permitido na consulta de CI.")


def _api_json(path):
    """GET público de um caminho fixo, sem imprimir URLs de exceções ou payloads."""
    if path not in ("branches/main",) and not re.fullmatch(
        r"actions/runs/[1-9][0-9]{0,18}", path
    ):
        raise RuntimeError("Endpoint de consulta de CI inválido.")
    request = Request(
        API + "/" + path,
        headers={"Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "Cache-Control": "no-cache",
                 "User-Agent": "isadora-read-only-release-gate"},
    )
    opener = build_opener(HTTPSHandler(context=ssl.create_default_context()),
                          NoRedirect())
    try:
        with opener.open(request, timeout=15) as response:
            if response.status != 200 or response.geturl() != API + "/" + path:
                raise RuntimeError("A API GitHub não retornou a origem esperada.")
            raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise RuntimeError("Resposta da API GitHub excede o limite permitido.")
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise RuntimeError("Resposta da API GitHub inválida.")
            return payload
    except (HTTPError, URLError, TimeoutError, OSError, ValueError,
            UnicodeError, json.JSONDecodeError):
        raise RuntimeError("Não foi possível validar a CI pública do GitHub.") from None


def verify(sha, run_id, *, get_json=_api_json):
    """Exige CI aprovada na main *atual* e revisão idêntica à selecionada."""
    if not isinstance(sha, str) or not SHA_PATTERN.fullmatch(sha):
        raise ValueError("SHA aprovado deve ter 40 caracteres hexadecimais minúsculos.")
    if isinstance(run_id, bool) or not isinstance(run_id, int) or (
        run_id <= 0 or run_id > 9999999999999999999
    ):
        raise ValueError("ID da execução GitHub Actions inválido.")

    branch = get_json("branches/main")
    if not isinstance(branch, dict) or not isinstance(branch.get("commit"), dict) or branch["commit"].get("sha") != sha:
        raise RuntimeError("O SHA selecionado não é a revisão atual da main.")

    run = get_json(f"actions/runs/{run_id}")
    if not isinstance(run, dict):
        raise RuntimeError("Resposta da execução GitHub Actions inválida.")
    if (
        run.get("id") != run_id
        or run.get("head_sha") != sha
        or run.get("head_branch") != "main"
        or run.get("event") != "push"
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
        or run.get("path") != WORKFLOW
        or not isinstance(run.get("repository"), dict)
        or run["repository"].get("full_name") != REPO
    ):
        raise RuntimeError("A execução indicada não comprova CI verde da main selecionada.")

    return {
        "status": "PASS",
        "read_only": True,
        "repository": REPO,
        "branch": "main",
        "approved_sha": sha,
        "workflow_run_id": run_id,
        "workflow_file": WORKFLOW,
        "ci_main_verified": True,
        "release_approved": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True, help="SHA exato da main a homologar")
    parser.add_argument("--run-id", type=int, required=True,
                        help="ID da execução verde do workflow principal na main")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = verify(args.sha, args.run_id)
    except (RuntimeError, ValueError) as exc:
        if args.json:
            print(json.dumps({"status": "BLOCKED", "read_only": True,
                              "reason": str(exc), "release_approved": False},
                             ensure_ascii=False))
        else:
            print("BLOQUEADO: " + str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("PASS: CI verde na main atual e SHA exato confirmados por GitHub.")
        print("NÃO libera convites reais: resta homologação no ambiente e aceite.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
