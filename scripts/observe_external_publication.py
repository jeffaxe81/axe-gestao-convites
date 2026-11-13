#!/usr/bin/env python3
"""Observa DNS e HTTPS públicos a partir da rede do próprio executor.

Se rodado pelo GitHub Actions, observa da rede externa daquele runner.
Não verifica versão do contêiner, não certifica provas humanas ou liberação.
Não faz login, não envia RSVP/convites e não escreve no banco de dados.
"""
import argparse
from contextlib import redirect_stdout
from io import StringIO
import ipaddress
import json
import socket

try:
    from . import check_production
except ImportError:
    import check_production

DOMAIN = "isadora2anos.org"
ORIGIN = "https://" + DOMAIN


def observe(*, lookup=None, verify=None):
    """Obtém só estados públicos fixos, sem imprimir IPs ou erros brutos."""
    dns_lookup = lookup if lookup is not None else socket.getaddrinfo
    https_verify = verify if verify is not None else check_production.verify
    report = {
        "status": "BLOCKED",
        "origin": ORIGIN,
        "dns_status": "FAIL",
        "https_smoke_status": "NOT_TESTED",
        "read_only": True,
        "external_network_required": True,
        "host_deployment_revision_verified": False,
        "human_evidence_certified": False,
        "release_approved": False,
    }
    try:
        answers = dns_lookup(DOMAIN, 443, type=socket.SOCK_STREAM)
        if not answers:
            return report
        addresses = [ipaddress.ip_address(answer[4][0]) for answer in answers]
        # Bloqueia resultados inválidos, locais e privados (DNS rebinding).
        if not all(addr.is_global for addr in addresses):
            return report
    except (OSError, ValueError, TypeError, IndexError, KeyError):
        return report
    report["dns_status"] = "PASS"
    try:
        # A verificação de aplicação usa HTTPS com validação de certificado
        # e GETs somente de endpoints públicos ou protegidos (sem login).
        # Seu texto não é incorporado ao relatório sanitizado.
        with redirect_stdout(StringIO()):
            https_verify(ORIGIN)
    except Exception:
        report["https_smoke_status"] = "FAIL"
        return report
    report["https_smoke_status"] = "PASS"
    report["status"] = "PASS"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true",
                        help="Estados sanitizados, sem IP, certificado, cookies ou conteúdo de evento")
    args = parser.parse_args(argv)
    result = observe()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print("DNS público: " + result["dns_status"])
        print("HTTPS e verificações públicas: " + result["https_smoke_status"])
        print("Aprovação operacional: NÃO. Rede independente + seis comprovantes exigidos.")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
