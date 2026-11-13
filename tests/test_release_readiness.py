"""No implicit production authorization from CI or incomplete records."""
import json
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.release_readiness import GATES, evaluate, report, status_payload, main, load_private_manifest, MAX_MANIFEST_BYTES


def empty_manifest():
    return {key: {"verified": False, "verified_at": None, "evidence_ref": None}
            for key in GATES}


def test_template_requires_all_external_approvals():
    manifest = json.loads(Path("docs/release-evidence-template.json").read_text())
    assert manifest == empty_manifest()
    text, ready = report(manifest)
    assert not ready
    assert text.count("PENDENTE:") == 6
    assert "LIBERAÇÃO BLOQUEADA" in text
    assert "6/7" in text


def test_no_partial_release_if_one_approval_missing():
    manifest = empty_manifest()
    for key in list(GATES)[:-1]:
        manifest[key] = {
            "verified": True,
            "verified_at": "2026-11-08T10:00:00-03:00",
            "evidence_ref": "revisao-privada-0001",
        }
    text, ready = report(manifest)
    assert not ready
    assert "5/6" in text
    assert "PENDENTE: Responsável aprovou" in text


def test_all_references_only_mark_records_ready_for_human_review():
    manifest = empty_manifest()
    for key in GATES:
        manifest[key] = {
            "verified": True,
            "verified_at": "2026-11-08T10:00:00-03:00",
            "evidence_ref": "prova-interna-de-teste-0001",
        }
    text, ready = report(manifest)
    assert ready
    assert "EVIDÊNCIAS PREENCHIDAS" in text
    assert "conferência humana final" in text
    assert "NÃO comprova" in text




def test_acceptance_requires_all_prior_evidence():
    manifest = empty_manifest()
    manifest["aceite_operacional"] = {
        "verified": True,
        "verified_at": "2026-11-10T18:00:00-03:00",
        "evidence_ref": "aceite-privado-0001",
    }
    with pytest.raises(ValueError, match="outras cinco evidências"):
        evaluate(manifest)


def test_acceptance_must_follow_last_completed_evidence_across_timezones():
    manifest = empty_manifest()
    for key in GATES:
        manifest[key] = {
            "verified": True,
            "verified_at": "2026-11-10T17:00:00-03:00",
            "evidence_ref": "comprovacao-privada-0001",
        }
    # 19:00Z = 16:00-03:00, anterior às cinco evidências das 20:00Z.
    manifest["aceite_operacional"]["verified_at"] = "2026-11-10T19:00:00+00:00"
    with pytest.raises(ValueError, match="anterior a outra evidência"):
        evaluate(manifest)


def test_acceptance_after_every_evidence_is_eligible_for_human_review():
    manifest = empty_manifest()
    for key in GATES:
        manifest[key] = {
            "verified": True,
            "verified_at": "2026-11-09T17:00:00-03:00",
            "evidence_ref": "comprovacao-privada-0001",
        }
    manifest["aceite_operacional"]["verified_at"] = "2026-11-10T21:00:00+00:00"
    summary, eligible = report(manifest)
    assert eligible
    assert "conferência humana final" in summary


def test_future_dated_evidence_never_unlocks_human_review():
    manifest = empty_manifest()
    for key in GATES:
        manifest[key] = {
            "verified": True,
            "verified_at": "2026-11-08T10:00:00-03:00",
            "evidence_ref": "prova-interna-de-teste-0001",
        }
    manifest["aceite_operacional"]["verified_at"] = (
        datetime.now(timezone.utc) + timedelta(days=1)
    ).isoformat()
    with pytest.raises(ValueError):
        report(manifest)


def test_small_clock_skew_is_not_rejected():
    manifest = empty_manifest()
    manifest["dns_https"] = {
        "verified": True,
        "verified_at": (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat(),
        "evidence_ref": "validacao-externa-privada-0001",
    }
    complete, missing = evaluate(manifest)
    assert complete == ["dns_https"]
    assert len(missing) == 5

@pytest.mark.parametrize("broken", [
    {"bad": True},
    {"verified": True, "verified_at": None, "evidence_ref": "nada"},
    {"verified": True, "verified_at": "2026-11-08T12:00", "evidence_ref": "reg-00123"},
    {"verified": True, "verified_at": "2026-11-08T12:00+00:00", "evidence_ref": "abc"},
    {"verified": False, "verified_at": "2026-11-08T12:00+00:00", "evidence_ref": None},
])
def test_invalid_record_rejected(broken):
    manifest = empty_manifest()
    manifest["android_real"] = broken
    with pytest.raises(ValueError):
        evaluate(manifest)


def test_incomplete_manifest_exits_nonzero(tmp_path, monkeypatch, capsys):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(empty_manifest()), encoding="utf-8")
    manifest.chmod(0o600)
    monkeypatch.setattr("sys.argv", ["gate", "--evidence-file", str(manifest)])
    assert main() == 1
    assert "LIBERAÇÃO BLOQUEADA" in capsys.readouterr().out


def test_structured_progress_separates_development_from_operational_release():
    summary = status_payload(empty_manifest())
    assert summary["technical_gates_documented"] == 10
    assert summary["operational_steps_complete"] == 6
    assert summary["operational_steps_total"] == 7
    assert summary["human_evidence_declared"] == 0
    assert len(summary["human_gates_pending"]) == 6
    assert summary["ci_or_deployed_revision_verified"] is False
    assert summary["ready_for_human_review"] is False
    assert summary["release_approved"] is False


def test_complete_declarations_never_authorize_real_invitations():
    manifest = empty_manifest()
    for key in GATES:
        manifest[key] = {
            "verified": True,
            "verified_at": "2026-11-10T20:00:00+00:00",
            "evidence_ref": "registro-interno-00001",
        }
    summary = status_payload(manifest)
    assert summary["human_evidence_declared"] == 6
    assert summary["human_gates_pending"] == []
    assert summary["ready_for_human_review"] is True
    assert summary["release_approved"] is False
    assert summary["ci_or_deployed_revision_verified"] is False


def test_json_cli_redacts_private_references_and_keeps_blocked_exit(tmp_path, capsys):
    manifest = empty_manifest()
    manifest["dns_https"] = {
        "verified": True,
        "verified_at": "2026-11-10T20:00:00+00:00",
        "evidence_ref": "arquivo-privado-nao-exibir-familia-abc",
    }
    path = tmp_path / "human-evidence.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    path.chmod(0o600)
    assert main(["--evidence-file", str(path), "--json"]) == 1
    raw = capsys.readouterr().out
    summary = json.loads(raw)
    assert "familia-abc" not in raw
    assert "evidence_ref" not in raw
    assert summary["human_evidence_declared"] == 1
    assert "dns_https" not in summary["human_gates_pending"]
    assert summary["release_approved"] is False


def test_json_cli_complete_manifest_only_enters_human_review(tmp_path, capsys):
    manifest = empty_manifest()
    for key in GATES:
        manifest[key] = {
            "verified": True,
            "verified_at": "2026-11-10T20:00:00+00:00",
            "evidence_ref": "registro-privado-de-homologacao",
        }
    path = tmp_path / "human-evidence.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    path.chmod(0o600)
    assert main(["--evidence-file", str(path), "--json"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["ready_for_human_review"] is True
    assert summary["release_approved"] is False


def test_private_manifest_loader_rejects_public_files(tmp_path):
    source = tmp_path / "manifest.json"
    source.write_text(json.dumps(empty_manifest()), encoding="utf-8")
    source.chmod(0o644)
    with pytest.raises(ValueError, match="0600"):
        load_private_manifest(str(source))


def test_private_manifest_loader_accepts_secure_file(tmp_path):
    source = tmp_path / "manifest.json"
    source.write_text(json.dumps(empty_manifest()), encoding="utf-8")
    source.chmod(0o600)
    assert load_private_manifest(str(source)) == empty_manifest()
    assert stat.S_IMODE(source.stat().st_mode) == 0o600


def test_private_manifest_loader_rejects_symlink(tmp_path):
    original = tmp_path / "original.json"
    original.write_text(json.dumps(empty_manifest()), encoding="utf-8")
    original.chmod(0o600)
    linked = tmp_path / "linked.json"
    linked.symlink_to(original)
    with pytest.raises(ValueError, match="link simbólico"):
        load_private_manifest(str(linked))


def test_private_manifest_loader_rejects_unsafe_parent(tmp_path):
    folder = tmp_path / "world-readable"
    folder.mkdir()
    folder.chmod(0o755)
    target = folder / "manifest.json"
    target.write_text(json.dumps(empty_manifest()), encoding="utf-8")
    target.chmod(0o600)
    with pytest.raises(ValueError, match="0700"):
        load_private_manifest(str(target))


def test_private_manifest_loader_refuses_checkout_file(tmp_path):
    checkout = tmp_path / "repo"
    checkout.mkdir(mode=0o700)
    target = checkout / "evidence.json"
    target.write_text(json.dumps(empty_manifest()), encoding="utf-8")
    target.chmod(0o600)
    with pytest.raises(ValueError, match="fora do repositório"):
        load_private_manifest(str(target), root=checkout)


def test_private_manifest_loader_blocks_oversized_document(tmp_path):
    target = tmp_path / "evidence.json"
    target.write_bytes(b"x" * (MAX_MANIFEST_BYTES + 1))
    target.chmod(0o600)
    with pytest.raises(ValueError, match="64 KB"):
        load_private_manifest(str(target))


def test_private_manifest_cli_never_prints_private_payload(tmp_path, capsys):
    target = tmp_path / "evidence.json"
    target.write_bytes(b'{"private":"contato-telefone-sigiloso"')
    target.chmod(0o600)
    assert main(["--evidence-file", str(target), "--json"]) == 2
    logs = capsys.readouterr()
    assert "contato-telefone-sigiloso" not in logs.err
    assert "contato-telefone-sigiloso" not in logs.out


def test_private_manifest_cli_rejects_path_in_repo(capsys):
    assert main(["--evidence-file", "docs/release-evidence-template.json"]) == 2
    assert "absoluto" in capsys.readouterr().err
