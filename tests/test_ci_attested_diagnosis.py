"""CI attestation is an optional, fail-closed gate for strict host checks.

Only in-memory synthetic proofs are used. Never contacts a real host or API.
"""
import json

import pytest

from scripts import diagnose_release as diag
from scripts import check_green_main_ci as ci
from scripts import check_deployed_revision as docker

SHA = "a" * 40
OLD = "b" * 40
RUN_ID = 43257995941
URL = "https://isadora2anos.org"


def _forbid_io(monkeypatch):
    def forbid(*_args, **_kwargs):
        pytest.fail("An invalid gate must not read Git/env/Docker or HTTP")
    monkeypatch.setattr(diag, "clean_revision", forbid)
    monkeypatch.setattr(diag.preflight, "load_env", forbid)
    monkeypatch.setattr(diag.check_local, "inspect", forbid)
    monkeypatch.setattr(diag.check_production, "verify", forbid)
    monkeypatch.setattr(ci, "verify", forbid)


@pytest.mark.parametrize("args,expected_failure", [
    ({"ci_run_id": RUN_ID}, "ci_main_inputs"),
    ({"ci_run_id": RUN_ID, "expected_sha": SHA}, "expected_revision_host_mode"),
    ({"ci_run_id": RUN_ID, "expected_sha": SHA, "require_local_gates": True},
     "expected_revision_host_mode"),
    ({"ci_run_id": RUN_ID, "expected_sha": SHA, "require_deployed_revision": True},
     "expected_revision_host_mode"),
    ({"ci_run_id": 0, "expected_sha": SHA, "require_local_gates": True,
      "require_deployed_revision": True}, "ci_main_inputs"),
    ({"ci_run_id": "not-integer", "expected_sha": SHA, "require_local_gates": True,
      "require_deployed_revision": True}, "ci_main_inputs"),
    ({"ci_run_id": True, "expected_sha": SHA, "require_local_gates": True,
      "require_deployed_revision": True}, "ci_main_inputs"),
])
def test_ci_gate_invalid_host_mode_or_run_id_is_rejected_before_io(
    monkeypatch, args, expected_failure
):
    _forbid_io(monkeypatch)
    report = diag.diagnose(URL, **args)
    assert report["status"] == "BLOCKED"
    assert report["failed_check"] == expected_failure
    assert report["ci_main_verified"] is False
    assert report["release_approved"] is False


def test_dirty_or_outdated_checkout_stops_before_public_ci_lookup(monkeypatch):
    monkeypatch.setattr(diag, "clean_revision", lambda _root: OLD)
    def forbid(*args, **kw):
        pytest.fail("Do not contact GitHub if local revision is stale")
    monkeypatch.setattr(ci, "verify", forbid)
    report = diag.diagnose(
        URL, expected_sha=SHA, ci_run_id=RUN_ID, require_local_gates=True,
        require_deployed_revision=True, env_file=".env",
        local_url="http://127.0.0.1:8080",
    )
    assert report["status"] == "BLOCKED"
    assert report["failed_check"] == "expected_revision"
    assert "ci_main" not in report["checks"]
    assert report["ci_main_verified"] is False


def test_failed_public_ci_blocks_before_private_env_docker_and_http(monkeypatch):
    monkeypatch.setattr(diag, "clean_revision", lambda _root: SHA)
    def failed(*args):
        raise RuntimeError("TOKEN_SECRET=must-never-leak")
    monkeypatch.setattr(ci, "verify", failed)
    def forbid(*_args, **_kwargs):
        pytest.fail("No local or remote checks after CI fails")
    monkeypatch.setattr(diag.preflight, "load_env", forbid)
    monkeypatch.setattr(diag.check_local, "inspect", forbid)
    monkeypatch.setattr(diag.check_production, "verify", forbid)
    monkeypatch.setattr(docker, "inspect", forbid)

    report = diag.diagnose(
        URL, expected_sha=SHA, ci_run_id=RUN_ID, require_local_gates=True,
        require_deployed_revision=True, env_file=".env",
        local_url="http://127.0.0.1:8080",
    )
    assert report["status"] == "BLOCKED"
    assert report["failed_check"] == "ci_main"
    assert report["ci_main_verified"] is False
    assert "must-never-leak" not in json.dumps(report)
    assert report["release_approved"] is False


def test_successful_public_ci_then_host_checks_still_requires_human_approval(monkeypatch):
    calls = []
    monkeypatch.setattr(diag, "clean_revision", lambda _root: SHA)

    def prove(sha, run_id):
        assert (sha, run_id) == (SHA, RUN_ID)
        calls.append("github")
        return {
            "status": "PASS", "ci_main_verified": True,
            "approved_sha": SHA, "workflow_run_id": RUN_ID,
        }

    monkeypatch.setattr(ci, "verify", prove)
    monkeypatch.setattr(diag.preflight, "load_env",
                        lambda _file: {"APP_PUBLIC_URL": URL})
    monkeypatch.setattr(diag.preflight, "validate",
                        lambda _values, **kw: [])
    monkeypatch.setattr(diag.check_local, "inspect",
                        lambda _url: calls.append("local"))
    monkeypatch.setattr(diag.check_production, "verify",
                        lambda _url: calls.append("https"))
    monkeypatch.setattr(diag.check_deployed_assets, "inspect",
                        lambda *_: calls.append("assets"))
    def inspect_image(*, root, checkout):
        calls.append("docker")
        assert checkout(root) == SHA
        return {
            "status": "PASS", "running_image_revision": SHA,
            "revision_label_matches_checkout": True,
            "running_container_healthy": True,
        }
    monkeypatch.setattr(docker, "inspect", inspect_image)

    report = diag.diagnose(
        URL, expected_sha=SHA, ci_run_id=RUN_ID, require_local_gates=True,
        require_deployed_revision=True, env_file=".env",
        local_url="http://127.0.0.1:8080",
    )
    assert report["status"] == "AUTOMATED_PASS"
    assert report["ci_main_verified"] is True
    assert report["ci_main_run_id"] == RUN_ID
    assert report["checks"]["ci_main"] == "PASS"
    assert report["expected_revision_checked"] is True
    assert report["image_revision_verified"] is True
    assert report["host_checks_ready"] is True
    assert report["release_approved"] is False
    assert len(report["human_gates_pending"]) == 6
    assert calls == ["github", "local", "docker", "https", "assets"]


def test_optional_ci_is_explicitly_not_tested(monkeypatch):
    monkeypatch.setattr(diag, "clean_revision", lambda _root: SHA)
    monkeypatch.setattr(diag.check_production, "verify", lambda _url: None)
    monkeypatch.setattr(diag.check_deployed_assets, "inspect", lambda *_: None)
    monkeypatch.setattr(ci, "verify", lambda *_args: pytest.fail("No CI requested"))
    report = diag.diagnose(URL)
    assert report["status"] == "AUTOMATED_PASS"
    assert report["checks"]["ci_main"] == "NOT_TESTED"
    assert report["ci_main_verified"] is False
    assert report["release_approved"] is False


def test_cli_rejects_ci_run_without_expected_sha(monkeypatch, capsys):
    _forbid_io(monkeypatch)
    assert diag.main([
        "--url", URL, "--ci-run-id", str(RUN_ID), "--json",
    ]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["failed_check"] == "ci_main_inputs"
    assert result["release_approved"] is False
