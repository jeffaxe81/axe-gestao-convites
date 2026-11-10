"""Testes do diagnóstico read-only e dos seus gates de liberação."""
import json

import pytest

from scripts import diagnose_release as diagnostic


SHA = "a" * 40
URL = "https://isadora2anos.org"


def successful_checks(monkeypatch):
    calls = []
    monkeypatch.setattr(diagnostic, "clean_revision", lambda _root: SHA)
    monkeypatch.setattr(
        diagnostic.check_production, "verify",
        lambda origin: calls.append(("public", origin)),
    )
    monkeypatch.setattr(
        diagnostic.check_deployed_assets, "inspect",
        lambda origin, root: calls.append(("assets", origin)),
    )
    monkeypatch.setattr(
        diagnostic.check_local, "inspect",
        lambda origin: calls.append(("local", origin)),
    )
    return calls


def test_success_still_does_not_authorize_real_invitations(monkeypatch):
    calls = successful_checks(monkeypatch)
    result = diagnostic.diagnose(URL)
    assert result["status"] == "AUTOMATED_PASS"
    assert result["release_approved"] is False
    assert result["read_only"] is True
    assert result["host_checks_ready"] is False
    assert result["local_gate_coverage"] == "NOT_TESTED"
    assert result["checkout_sha"] == SHA
    assert result["checks"]["local_configuration"] == "NOT_TESTED"
    assert result["checks"]["local_http"] == "NOT_TESTED"
    assert len(result["human_gates_pending"]) == 6
    assert calls == [("public", URL), ("assets", URL)]


@pytest.mark.parametrize("bad", [
    "http://isadora2anos.org", "http://localhost:8080",
    "https://isadora2anos.org/organizar",
    "https://isadora2anos.org/?token=segredo",
    "https://isadora2anos.org/#convite=segredo",
    "https://usuario:senha@isadora2anos.org",
    "https://isadora2anos.org:8443",
])
def test_invalid_public_url_never_contacts_network(monkeypatch, bad):
    monkeypatch.setattr(diagnostic, "clean_revision",
                        lambda _: pytest.fail("Git must not be reached"))
    monkeypatch.setattr(diagnostic.check_production, "verify",
                        lambda _: pytest.fail("Network must not be reached"))
    result = diagnostic.diagnose(bad)
    assert result["status"] == "BLOCKED"
    assert result["checks"]["public_url"] == "FAIL"


def test_local_url_must_be_loopback_before_any_http(monkeypatch):
    monkeypatch.setattr(diagnostic, "clean_revision",
                        lambda _: pytest.fail("Git must not be reached"))
    result = diagnostic.diagnose(URL, local_url="http://192.168.0.10:8080")
    assert result["status"] == "BLOCKED"
    assert result["checks"]["local_url"] == "FAIL"


def test_modified_checkout_blocks_external_access(monkeypatch):
    def dirty(_):
        raise RuntimeError("sensitive/path/ignored")
    monkeypatch.setattr(diagnostic, "clean_revision", dirty)
    monkeypatch.setattr(diagnostic.check_production, "verify",
                        lambda _: pytest.fail("No network with dirty checkout"))
    result = diagnostic.diagnose(URL)
    assert result["status"] == "BLOCKED"
    assert result["failed_check"] == "checkout_clean"
    assert "sensitive" not in json.dumps(result)


def test_config_must_match_verified_origin(monkeypatch):
    successful_checks(monkeypatch)
    monkeypatch.setattr(diagnostic.preflight, "load_env",
                        lambda _: {"APP_PUBLIC_URL": "https://outrodominio.org"})
    monkeypatch.setattr(diagnostic.preflight, "validate",
                        lambda values, **kw: [])
    result = diagnostic.diagnose(URL, env_file="does-not-need-to-exist")
    assert result["status"] == "BLOCKED"
    assert result["failed_check"] == "local_configuration"


def test_invalid_preflight_is_sanitized(monkeypatch):
    successful_checks(monkeypatch)
    monkeypatch.setattr(diagnostic.preflight, "load_env",
                        lambda _: {"APP_PUBLIC_URL": URL, "TOKEN_SECRET": "NEVER_PRINT_ME"})
    monkeypatch.setattr(diagnostic.preflight, "validate",
                        lambda values, **kw: ["TOKEN_SECRET=NEVER_PRINT_ME"])
    result = diagnostic.diagnose(URL, env_file="some-file")
    assert result["status"] == "BLOCKED"
    assert "NEVER_PRINT_ME" not in json.dumps(result)


def test_local_and_public_checks_run_in_order(monkeypatch):
    calls = successful_checks(monkeypatch)
    monkeypatch.setattr(diagnostic.preflight, "load_env",
                        lambda _: {"APP_PUBLIC_URL": URL})
    monkeypatch.setattr(diagnostic.preflight, "validate",
                        lambda values, **kw: [])
    result = diagnostic.diagnose(
        URL, env_file="file.env", local_url="http://127.0.0.1:8080",
    )
    assert result["status"] == "AUTOMATED_PASS"
    assert result["host_checks_ready"] is True
    assert result["local_gate_coverage"] == "COMPLETE"
    assert all(result["checks"][x] == "PASS" for x in (
        "local_configuration", "local_http", "public_https", "published_assets"
    ))
    assert calls == [
        ("local", "http://127.0.0.1:8080"),
        ("public", URL),
        ("assets", URL),
    ]


def test_remote_failure_stops_before_asset_download(monkeypatch):
    successful_checks(monkeypatch)
    def down(_):
        raise RuntimeError("http://private.invalid?secret=never")
    monkeypatch.setattr(diagnostic.check_production, "verify", down)
    monkeypatch.setattr(diagnostic.check_deployed_assets, "inspect",
                        lambda *args: pytest.fail("Must stop on HTTPS failure"))
    result = diagnostic.diagnose(URL)
    assert result["status"] == "BLOCKED"
    assert result["failed_check"] == "public_https"
    assert "private.invalid" not in json.dumps(result)


def test_cli_json_is_sanitized_and_nonzero_if_blocked(monkeypatch, capsys):
    monkeypatch.setattr(diagnostic, "diagnose", lambda *args, **kw: {
        "status": "BLOCKED", "release_approved": False,
        "read_only": True, "checks": {"public_https": "FAIL"},
        "human_gates_pending": list(diagnostic.HUMAN_GATES),
    })
    code = diagnostic.main(["--url", URL, "--json"])
    output = capsys.readouterr().out
    assert code == 1
    parsed = json.loads(output)
    assert parsed["release_approved"] is False
    assert "senha" not in output.lower()


def test_cli_success_is_not_deployment_approval(monkeypatch, capsys):
    monkeypatch.setattr(diagnostic, "diagnose", lambda *args, **kw: {
        "status": "AUTOMATED_PASS", "release_approved": False,
        "read_only": True, "checks": {"public_https": "PASS"},
        "local_gate_coverage": "NOT_TESTED",
        "human_gates_pending": list(diagnostic.HUMAN_GATES),
    })
    assert diagnostic.main(["--url", URL]) == 0
    assert "BLOQUEADA" in capsys.readouterr().out


@pytest.mark.parametrize("optional", [
    {},
    {"env_file": "file.env"},
    {"local_url": "http://127.0.0.1:8080"},
])
def test_host_mode_blocks_missing_local_inputs_without_http(monkeypatch, optional):
    monkeypatch.setattr(diagnostic, "clean_revision",
                        lambda _: pytest.fail("Git should not run with missing inputs"))
    monkeypatch.setattr(diagnostic.check_production, "verify",
                        lambda _: pytest.fail("External HTTP should not run"))
    monkeypatch.setattr(diagnostic.check_local, "inspect",
                        lambda _: pytest.fail("Local HTTP should not run"))
    result = diagnostic.diagnose(URL, require_local_gates=True, **optional)
    assert result["status"] == "BLOCKED"
    assert result["release_approved"] is False
    assert result["host_checks_ready"] is False
    assert result["failed_check"] == "required_local_inputs"
    assert result["checks"]["required_local_inputs"] == "FAIL"


def test_host_mode_passes_only_with_all_automatic_checks(monkeypatch):
    successful_checks(monkeypatch)
    monkeypatch.setattr(diagnostic.preflight, "load_env",
                        lambda _: {"APP_PUBLIC_URL": URL})
    monkeypatch.setattr(diagnostic.preflight, "validate",
                        lambda values, **kw: [])
    result = diagnostic.diagnose(
        URL, env_file="file.env", local_url="http://127.0.0.1:8080",
        require_local_gates=True,
    )
    assert result["status"] == "AUTOMATED_PASS"
    assert result["host_checks_ready"] is True
    assert result["local_gate_coverage"] == "COMPLETE"
    assert result["release_approved"] is False


def test_host_mode_blocks_local_failure_without_external_http(monkeypatch):
    successful_checks(monkeypatch)
    monkeypatch.setattr(diagnostic.preflight, "load_env",
                        lambda _: {"APP_PUBLIC_URL": URL})
    monkeypatch.setattr(diagnostic.preflight, "validate",
                        lambda values, **kw: ["configuration error"])
    monkeypatch.setattr(diagnostic.check_production, "verify",
                        lambda _: pytest.fail("External HTTP should not run"))
    result = diagnostic.diagnose(
        URL, env_file="file.env", local_url="http://127.0.0.1:8080",
        require_local_gates=True,
    )
    assert result["status"] == "BLOCKED"
    assert result["failed_check"] == "local_configuration"
    assert result["host_checks_ready"] is False


def test_cli_strict_mode_reports_missing_inputs_without_secrets(monkeypatch, capsys):
    monkeypatch.setattr(diagnostic, "clean_revision",
                        lambda _: pytest.fail("Git should not run"))
    assert diagnostic.main(["--url", URL, "--require-local-gates", "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["failed_check"] == "required_local_inputs"
    assert report["local_gate_coverage"] == "NOT_TESTED"
    assert report["release_approved"] is False
