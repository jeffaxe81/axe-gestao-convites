"""Independent network observation remains read-only and non-authorizing."""
import json
import socket

import pytest

from scripts import observe_external_publication as probe


def public_dns(_host, _port, *, type):
    assert (_host, _port, type) == (probe.DOMAIN, 443, socket.SOCK_STREAM)
    return [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("104.16.0.1", 443)),
        (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:4700::1111", 443, 0, 0)),
    ]


def test_dns_https_success_is_observation_not_human_approval(capsys):
    called = []
    def https(origin):
        called.append(origin)
        print("PRIVATE SHOULD NOT APPEAR IN JSON")
    result = probe.observe(lookup=public_dns, verify=https)
    assert called == ["https://isadora2anos.org"]
    assert result["status"] == "PASS"
    assert result["dns_status"] == "PASS"
    assert result["https_smoke_status"] == "PASS"
    assert result["release_approved"] is False
    assert result["human_evidence_certified"] is False
    assert result["host_deployment_revision_verified"] is False
    assert result["read_only"] is True
    assert "PRIVATE" not in json.dumps(result)
    assert "PRIVATE" not in capsys.readouterr().out


@pytest.mark.parametrize("answers", [
    [], [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))],
    [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.50.1", 443))],
    [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("0.0.0.0", 443))],
    [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("not-an-ip", 443))],
    [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("104.16.0.1", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.10.2.2", 443)),
    ],
])
def test_no_or_unsafe_dns_never_contacts_app(answers):
    def no_https(origin):
        pytest.fail("HTTPS must not run after invalid/private DNS")
    result = probe.observe(lookup=lambda *_args, **_kw: answers, verify=no_https)
    assert result["status"] == "BLOCKED"
    assert result["dns_status"] == "FAIL"
    assert result["https_smoke_status"] == "NOT_TESTED"
    assert result["release_approved"] is False


def test_resolver_error_is_blocked_and_sanitized():
    def broken_dns(*args, **kwargs):
        raise OSError("TOKEN_SECRET=never-print")
    result = probe.observe(lookup=broken_dns, verify=lambda *_: pytest.fail("unexpected"))
    assert result["status"] == "BLOCKED"
    assert "TOKEN_SECRET" not in json.dumps(result)


def test_https_tls_or_policy_failure_is_blocked_and_sanitized():
    def failed_https(*args):
        raise RuntimeError("TOKEN_SECRET=never-print")
    result = probe.observe(lookup=public_dns, verify=failed_https)
    assert result["dns_status"] == "PASS"
    assert result["https_smoke_status"] == "FAIL"
    assert result["status"] == "BLOCKED"
    assert "TOKEN_SECRET" not in json.dumps(result)


def test_cli_failure_keeps_nonzero_and_no_release(monkeypatch, capsys):
    monkeypatch.setattr(probe, "observe", lambda: probe.observe(
        lookup=lambda *_args, **kwargs: [], verify=lambda *_: None))
    assert probe.main(["--json"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["release_approved"] is False
    assert result["human_evidence_certified"] is False
    assert result["status"] == "BLOCKED"


def test_cli_success_is_not_release_approval(monkeypatch, capsys):
    monkeypatch.setattr(probe, "observe", lambda: probe.observe(
        lookup=public_dns, verify=lambda origin: None))
    assert probe.main(["--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "PASS"
    assert result["release_approved"] is False
    assert "human_evidence_certified" in result
