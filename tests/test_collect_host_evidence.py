"""Evidence capture is private, non-destructive and NEVER signs off human gates."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat

import pytest

from scripts import collect_host_evidence as collector

SHA = "a" * 40
RUN_ID = 43296518036
CHECKS = {
    "public_url": "PASS", "local_url": "PASS",
    "checkout_clean": "PASS", "expected_revision": "PASS",
    "ci_main": "PASS", "local_configuration": "PASS",
    "local_http": "PASS", "deployed_revision": "PASS",
    "public_https": "PASS", "published_assets": "PASS",
}


def diagnostic(*, success=True):
    output = {
        "status": "AUTOMATED_PASS" if success else "BLOCKED",
        "checks": dict(CHECKS),
        "checkout_sha": SHA, "expected_sha": SHA,
        "ci_main_run_id": RUN_ID,
        "host_checks_ready": success,
        "image_revision_verified": success,
        "expected_revision_checked": success,
        "ci_main_verified": success,
        "release_approved": False,
        "local_config_secret": "TOKEN_SECRET=must-not-appear",
        "raw_guest_name": "FAMILIA_SECRETA_NUNCA_MOSTRAR",
        "human_gates_pending": [],  # Never trust these from raw diagnostics.
    }
    if not success:
        output["checks"]["public_https"] = "FAIL"
        output["failed_check"] = "public_https"
    return output


@pytest.fixture
def private_folder(tmp_path):
    folder = tmp_path / "isadora-private"
    folder.mkdir(mode=0o700)
    folder.chmod(0o700)
    return folder


def test_pass_snapshot_contains_only_allowlisted_metadata():
    snapshot = collector.sanitized_snapshot(
        diagnostic(), at=datetime(2026, 11, 12, 20, 0, tzinfo=timezone.utc)
    )
    serialized = json.dumps(snapshot)
    assert snapshot["host_automated_gates_pass"] is True
    assert snapshot["status"] == "AUTOMATED_PASS"
    assert snapshot["release_approved"] is False
    assert snapshot["human_evidence_certified_by_snapshot"] is False
    assert snapshot["verified_ci_run_id"] == RUN_ID
    assert len(snapshot["human_gates_pending"]) == 6
    assert snapshot["contains_guest_data"] is False
    assert "TOKEN_SECRET=" not in serialized
    assert "FAMILIA_SECRETA" not in serialized
    assert snapshot["generated_at_utc"] == "2026-11-12T20:00:00+00:00"


def test_failed_host_check_creates_blocked_evidence_not_release():
    snapshot = collector.sanitized_snapshot(diagnostic(success=False))
    assert snapshot["status"] == "BLOCKED"
    assert snapshot["failed_check"] == "public_https"
    assert snapshot["host_automated_gates_pass"] is False
    assert snapshot["release_approved"] is False


@pytest.mark.parametrize("mutation", [
    {"status": "PASS"},
    {"release_approved": True},
    {"checks": {"unexpected_token": "PASS"}},
    {"checks": {"public_https": "SUPER_PASS"}},
    {"checkout_sha": "a" * 39},
    {"ci_main_run_id": "43296518036"},
    {"failed_check": "public_https"},
])
def test_malformed_report_does_not_generate_artifact(mutation):
    report = diagnostic()
    report.update(mutation)
    with pytest.raises(ValueError):
        collector.sanitized_snapshot(report)


def test_normal_report_without_verified_ci_cannot_claim_full_host_pass():
    report = diagnostic()
    report["ci_main_verified"] = False
    report["checks"]["ci_main"] = "NOT_TESTED"
    assert not collector.sanitized_snapshot(report)["host_automated_gates_pass"]


def test_private_file_is_exclusive_and_mode_0600(private_folder):
    target = private_folder / "status.json"
    approved = collector.private_destination(str(target))
    collector.save_private(approved, collector.sanitized_snapshot(diagnostic()))
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert json.loads(target.read_text())["release_approved"] is False
    with pytest.raises(ValueError, match="já existe"):
        collector.private_destination(str(target))


def test_preexisting_symlink_is_never_followed(private_folder, tmp_path):
    target = private_folder / "status.json"
    victim = tmp_path / "valuable.txt"
    victim.write_text("unchanged")
    target.symlink_to(victim)
    with pytest.raises(ValueError, match="já existe"):
        collector.private_destination(str(target))
    assert victim.read_text() == "unchanged"


def test_unowned_or_world_readable_directory_is_rejected(tmp_path):
    folder = tmp_path / "insecure"
    folder.mkdir()
    folder.chmod(0o755)
    with pytest.raises(ValueError, match="privado"):
        collector.private_destination(str(folder / "status.json"))


def test_repo_checkout_is_not_valid_evidence_directory(tmp_path):
    repo = tmp_path / "checkout"
    repo.mkdir(mode=0o700)
    repo.chmod(0o700)
    with pytest.raises(ValueError, match="fora do repositório"):
        collector.private_destination(str(repo / "status.json"), root=repo)


def test_relative_or_wrong_extension_is_rejected(private_folder):
    with pytest.raises(ValueError, match="absoluto"):
        collector.private_destination("status.json")
    with pytest.raises(ValueError, match="absoluto"):
        collector.private_destination(str(private_folder / "status.txt"))


def test_cli_uses_strict_read_only_diagnostic_before_writing(monkeypatch, capsys, private_folder):
    calls = []
    def fake_diagnose(url, **kwargs):
        calls.append((url, kwargs))
        return diagnostic()
    monkeypatch.setattr(collector.diagnose_release, "diagnose", fake_diagnose)
    target = private_folder / "automatic-check.json"
    args = [
        "--expected-sha", SHA, "--ci-run-id", str(RUN_ID),
        "--output", str(target), "--json",
    ]
    assert collector.main(args) == 0
    assert len(calls) == 1
    assert calls[0][0] == "https://isadora2anos.org"
    assert calls[0][1]["require_local_gates"] is True
    assert calls[0][1]["require_deployed_revision"] is True
    assert calls[0][1]["expected_sha"] == SHA
    assert calls[0][1]["ci_run_id"] == RUN_ID
    text = capsys.readouterr().out
    assert "must-not-appear" not in text
    assert "FAMILIA_SECRETA" not in text
    saved = json.loads(target.read_text())
    assert json.loads(text) == saved
    assert saved["release_approved"] is False


def test_cli_failure_writes_blocked_report_and_nonzero(monkeypatch, private_folder):
    monkeypatch.setattr(collector.diagnose_release, "diagnose",
                        lambda *args, **kwargs: diagnostic(success=False))
    target = private_folder / "blocked.json"
    assert collector.main([
        "--expected-sha", SHA, "--ci-run-id", str(RUN_ID),
        "--output", str(target),
    ]) == 1
    result = json.loads(target.read_text())
    assert result["host_automated_gates_pass"] is False
    assert result["release_approved"] is False


def test_cli_never_overwrites_and_does_not_run_second_diagnostic(
    monkeypatch, private_folder
):
    target = private_folder / "proof.json"
    target.write_text("original")
    def forbid(*args, **kwargs):
        pytest.fail("No host diagnostic for duplicate output")
    monkeypatch.setattr(collector.diagnose_release, "diagnose", forbid)
    assert collector.main([
        "--expected-sha", SHA, "--ci-run-id", str(RUN_ID),
        "--output", str(target),
    ]) == 2
    assert target.read_text() == "original"
