"""The release CI attestation must match the exact public main revision.

Entire suite is synthetic; it cannot provide production deployment evidence.
"""
import json
from urllib.error import URLError

import pytest

from scripts import check_green_main_ci as ci

SHA = "a" * 40
OLD = "b" * 40
ID = 43257995941


def accepted_run():
    return {
        "id": ID,
        "head_sha": SHA,
        "head_branch": "main",
        "event": "push",
        "status": "completed",
        "conclusion": "success",
        "path": ".github/workflows/ci.yml",
        "repository": {"full_name": ci.REPO},
    }


def good_api(path):
    if path == "branches/main":
        return {"commit": {"sha": SHA}}
    if path == f"actions/runs/{ID}":
        return accepted_run()
    pytest.fail("Unexpected API path " + path)


def test_current_main_with_successful_push_ci_is_technical_evidence_only():
    report = ci.verify(SHA, ID, get_json=good_api)
    assert report == {
        "status": "PASS", "read_only": True, "repository": ci.REPO,
        "branch": "main", "approved_sha": SHA, "workflow_run_id": ID,
        "workflow_file": ci.WORKFLOW, "ci_main_verified": True,
        "release_approved": False,
    }


@pytest.mark.parametrize("bad_sha,bad_id", [
    ("", ID), ("A" * 40, ID), ("a" * 39, ID),
    ("a" * 41, ID), (SHA, 0), (SHA, -1),
    (SHA, True), (SHA, "43257995941"), (SHA, 10 ** 20),
])
def test_bad_inputs_do_not_contact_github(bad_sha, bad_id):
    def no_network(path):
        pytest.fail("GitHub API must not be called")
    with pytest.raises(ValueError):
        ci.verify(bad_sha, bad_id, get_json=no_network)


@pytest.mark.parametrize("branch", [
    {"commit": {"sha": OLD}}, {"commit": {}},
    {"commit": "invalid"}, {}, [], None,
])
def test_noncurrent_or_malformed_main_blocks_before_workflow_lookup(branch):
    calls = []
    def get_json(path):
        calls.append(path)
        assert path == "branches/main"
        return branch
    with pytest.raises(RuntimeError, match="revisão atual da main"):
        ci.verify(SHA, ID, get_json=get_json)
    assert calls == ["branches/main"]


@pytest.mark.parametrize("override", [
    {"head_sha": OLD},
    {"id": ID + 1},
    {"head_branch": "test/branch"},
    {"head_branch": "develop"},
    {"event": "pull_request"},
    {"status": "in_progress"},
    {"status": "queued", "conclusion": None},
    {"conclusion": "failure"},
    {"conclusion": "cancelled"},
    {"path": ".github/workflows/docs.yml"},
    {"repository": {"full_name": "untrusted/fork"}},
    {"repository": None},
])
def test_wrong_or_unfinished_ci_does_not_approve(override):
    def get_json(path):
        if path == "branches/main":
            return {"commit": {"sha": SHA}}
        run = accepted_run()
        run.update(override)
        return run
    with pytest.raises(RuntimeError, match="não comprova CI verde"):
        ci.verify(SHA, ID, get_json=get_json)


@pytest.mark.parametrize("broken", [None, [], "malformed", 3])
def test_non_object_workflow_data_blocks(broken):
    def get_json(path):
        return {"commit": {"sha": SHA}} if path == "branches/main" else broken
    with pytest.raises(RuntimeError, match="execução GitHub Actions inválida"):
        ci.verify(SHA, ID, get_json=get_json)


def test_public_api_path_restriction_never_allows_arbitrary_domains(monkeypatch):
    def no_network(*args, **kwargs):
        pytest.fail("Unexpected outbound request")
    monkeypatch.setattr(ci, "build_opener", no_network)
    for path in (
        "https://evil.example", "../users", "branches/main?secret=1",
        "actions/runs/../users", "actions/runs/0",
        "actions/runs/000001", "actions/runs/1/redirect",
    ):
        with pytest.raises(RuntimeError, match="Endpoint"):
            ci._api_json(path)


def test_transport_error_is_sanitized_for_public_release_report(monkeypatch):
    class FailedOpener:
        def open(self, request, timeout):
            raise URLError("TOKEN_SECRET=must-not-appear")
    monkeypatch.setattr(ci, "build_opener", lambda *args: FailedOpener())
    with pytest.raises(RuntimeError) as err:
        ci._api_json("branches/main")
    assert "must-not-appear" not in str(err.value)


def test_cli_failed_ci_outputs_no_operational_approval(monkeypatch, capsys):
    def blocked(*args):
        raise RuntimeError("A execução indicada não comprova CI verde da main selecionada.")
    monkeypatch.setattr(ci, "verify", blocked)
    code = ci.main(["--sha", SHA, "--run-id", str(ID), "--json"])
    result = json.loads(capsys.readouterr().out)
    assert code == 1
    assert result["release_approved"] is False
    assert result["status"] == "BLOCKED"


def test_cli_success_still_requires_real_host_evidence(monkeypatch, capsys):
    monkeypatch.setattr(ci, "verify", lambda *args: ci.verify(
        SHA, ID, get_json=good_api))
    assert ci.main(["--sha", SHA, "--run-id", str(ID), "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["ci_main_verified"] is True
    assert result["release_approved"] is False
