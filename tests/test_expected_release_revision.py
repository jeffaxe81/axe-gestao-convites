"""Fail-closed regression for release approval SHA in host diagnostics.

The expected revision is copied from a green GitHub CI run; the tool must not
select HEAD itself as an independent production release approval.
"""
import json

import pytest

from scripts import diagnose_release as diagnostic

URL = "https://isadora2anos.org"
SHA = "a" * 40
OLD_SHA = "b" * 40


def _no_io(monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Nenhum acesso a Git, Docker, configuração ou HTTP permitido")
    monkeypatch.setattr(diagnostic, "clean_revision", forbidden)
    monkeypatch.setattr(diagnostic.check_production, "verify", forbidden)
    monkeypatch.setattr(diagnostic.check_deployed_assets, "inspect", forbidden)
    monkeypatch.setattr(diagnostic.check_local, "inspect", forbidden)


@pytest.mark.parametrize("invalid", ["", "a" * 39, "a" * 41, "A" * 40,
                                     "sha-a", "0" * 40 + " TOKEN_SECRET=exposed"])
def test_invalid_expected_sha_blocks_before_any_local_or_remote_access(monkeypatch, invalid):
    _no_io(monkeypatch)
    report = diagnostic.diagnose(
        URL, expected_sha=invalid, require_local_gates=True,
        require_deployed_revision=True, env_file="file.env",
        local_url="http://127.0.0.1:8080",
    )
    assert report["status"] == "BLOCKED"
    assert report["failed_check"] == "expected_revision_input"
    assert report["release_approved"] is False
    assert report["expected_revision_checked"] is False
    assert "exposed" not in json.dumps(report)


@pytest.mark.parametrize("flags", [
    {},
    {"require_local_gates": True},
    {"require_deployed_revision": True},
])
def test_expected_sha_requires_both_strict_host_checks(monkeypatch, flags):
    _no_io(monkeypatch)
    report = diagnostic.diagnose(URL, expected_sha=SHA, **flags)
    assert report["status"] == "BLOCKED"
    assert report["failed_check"] == "expected_revision_host_mode"
    assert report["release_approved"] is False


def test_old_clean_checkout_blocks_before_config_http_or_docker(monkeypatch):
    monkeypatch.setattr(diagnostic, "clean_revision", lambda _root: OLD_SHA)
    def forbidden(*_args, **_kwargs):
        pytest.fail("Nenhum gate pode acessar ambiente após SHA divergente")
    monkeypatch.setattr(diagnostic.preflight, "load_env", forbidden)
    monkeypatch.setattr(diagnostic.check_local, "inspect", forbidden)
    monkeypatch.setattr(diagnostic.check_production, "verify", forbidden)
    monkeypatch.setattr(diagnostic.check_deployed_assets, "inspect", forbidden)

    report = diagnostic.diagnose(
        URL, expected_sha=SHA, require_local_gates=True,
        require_deployed_revision=True, env_file="file.env",
        local_url="http://127.0.0.1:8080",
    )
    assert report["status"] == "BLOCKED"
    assert report["checkout_sha"] == OLD_SHA
    assert report["failed_check"] == "expected_revision"
    assert report["checks"]["expected_revision"] == "FAIL"
    assert report["image_revision_verified"] is False
    assert report["expected_revision_checked"] is False
    assert report["release_approved"] is False
    assert len(report["human_gates_pending"]) == 6


def test_approved_checkout_docker_and_https_checks_still_do_not_release(monkeypatch):
    from scripts import check_deployed_revision
    calls = []
    monkeypatch.setattr(diagnostic, "clean_revision", lambda _root: SHA)
    monkeypatch.setattr(diagnostic.preflight, "load_env",
                        lambda _path: {"APP_PUBLIC_URL": URL})
    monkeypatch.setattr(diagnostic.preflight, "validate",
                        lambda _values, **kwargs: [])
    monkeypatch.setattr(diagnostic.check_local, "inspect",
                        lambda _url: calls.append("local"))
    monkeypatch.setattr(diagnostic.check_production, "verify",
                        lambda _url: calls.append("public"))
    monkeypatch.setattr(diagnostic.check_deployed_assets, "inspect",
                        lambda *_args: calls.append("assets"))
    def inspect_image(*, root, checkout):
        calls.append("docker")
        assert checkout(root) == SHA
        return {
            "status": "PASS",
            "running_image_revision": SHA,
            "revision_label_matches_checkout": True,
            "running_container_healthy": True,
        }
    monkeypatch.setattr(check_deployed_revision, "inspect", inspect_image)

    report = diagnostic.diagnose(
        URL, expected_sha=SHA, require_local_gates=True,
        require_deployed_revision=True, env_file="file.env",
        local_url="http://127.0.0.1:8080",
    )
    assert report["status"] == "AUTOMATED_PASS"
    assert report["expected_revision_checked"] is True
    assert report["expected_sha"] == SHA
    assert report["checks"]["expected_revision"] == "PASS"
    assert report["host_checks_ready"] is True
    assert report["image_revision_verified"] is True
    assert report["release_approved"] is False
    assert len(report["human_gates_pending"]) == 6
    assert calls == ["local", "docker", "public", "assets"]


def test_omitted_expected_sha_does_not_claim_approved_revision(monkeypatch):
    monkeypatch.setattr(diagnostic, "clean_revision", lambda _root: SHA)
    monkeypatch.setattr(diagnostic.check_production, "verify", lambda _url: None)
    monkeypatch.setattr(diagnostic.check_deployed_assets, "inspect", lambda *_: None)
    report = diagnostic.diagnose(URL)
    assert report["status"] == "AUTOMATED_PASS"
    assert report["checks"]["expected_revision"] == "NOT_TESTED"
    assert report["expected_revision_checked"] is False
    assert report["release_approved"] is False


def test_expected_revision_cli_rejects_invalid_input_without_io(monkeypatch, capsys):
    _no_io(monkeypatch)
    result = diagnostic.main([
        "--url", URL, "--require-local-gates", "--require-deployed-revision",
        "--env-file", ".env", "--local-url", "http://127.0.0.1:8080",
        "--expected-sha", "not-a-valid-sha", "--json",
    ])
    assert result == 1
    response = json.loads(capsys.readouterr().out)
    assert response["failed_check"] == "expected_revision_input"
    assert response["release_approved"] is False
