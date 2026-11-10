"""No implicit production authorization from CI or incomplete records."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.release_readiness import GATES, evaluate, report, main


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
    monkeypatch.setattr("sys.argv", ["gate", "--evidence-file", str(manifest)])
    assert main() == 1
    assert "LIBERAÇÃO BLOQUEADA" in capsys.readouterr().out
