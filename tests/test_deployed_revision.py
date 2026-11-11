"""Sem liberar produção apenas por rótulo Docker ou commit Git."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import check_deployed_revision as checker

SHA = "a" * 40
CONTAINER = "b" * 64


def fake_checkout(root):
    assert isinstance(root, Path)
    return SHA


def runner(revision=SHA, health="healthy", running="true", container=CONTAINER):
    commands = []

    def execute(command, root):
        commands.append(command)
        if command == ["docker", "compose", "ps", "-q", "app"]:
            return container
        if command == [
            "docker", "inspect", "--type=container", "--format",
            checker.INSPECT_FORMAT, CONTAINER,
        ]:
            return running + "|" + health + "|" + revision
        raise AssertionError("Chamada inesperada ou mutação Docker")

    return execute, commands


def test_clean_checkout_matches_running_labeled_image(tmp_path):
    execute, commands = runner()
    report = checker.inspect(tmp_path, execute_command=execute, checkout=fake_checkout)
    assert report["status"] == "PASS"
    assert report["checkout_sha"] == SHA
    assert report["running_image_revision"] == SHA
    assert report["backend_code_proven"] is False
    assert report["public_domain_verified"] is False
    assert report["release_approved"] is False
    assert commands[0] == ["docker", "compose", "ps", "-q", "app"]
    assert len(commands) == 2
    assert all("up" not in item and "down" not in item for cmd in commands for item in cmd)


@pytest.mark.parametrize("broken,reason", [
    ({"revision": "unknown"}, "sem revisão"),
    ({"revision": "b"*40}, "difere"),
    ({"revision": "a"*39}, "sem revisão"),
    ({"health": "starting"}, "não está saudável"),
    ({"running": "false"}, "não está saudável"),
    ({"container": ""}, "contêiner app"),
    ({"container": "not-a-docker-id"}, "contêiner app"),
])
def test_missing_or_wrong_revision_never_passes(tmp_path, broken, reason):
    execute, _commands = runner(**broken)
    with pytest.raises(RuntimeError, match=reason):
        checker.inspect(tmp_path, execute_command=execute, checkout=fake_checkout)


def test_git_checkout_must_be_exact_full_sha(tmp_path):
    execute, commands = runner()
    with pytest.raises(RuntimeError, match="Git local inválida"):
        checker.inspect(tmp_path, execute_command=execute,
                        checkout=lambda root: "a"*7)
    assert commands == []


def test_docker_errors_do_not_expose_cli_output(tmp_path, monkeypatch):
    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(
            returncode=1, stdout="TOKEN_SECRET=exposed",
            stderr="SESSION_SECRET=exposed",
        )
    monkeypatch.setattr(checker.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="Docker não pôde ser consultado") as error:
        checker.execute(["docker", "compose", "ps", "-q", "app"], tmp_path)
    assert "exposed" not in str(error.value)


def test_cli_failure_never_claims_release_approval(monkeypatch, capsys):
    monkeypatch.setattr(checker, "inspect",
                        lambda: (_ for _ in ()).throw(RuntimeError("Imagem sem revisão Git válida.")))
    result = checker.main(["--json"])
    assert result == 1
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "BLOCKED"
    assert report["release_approved"] is False


def test_cli_success_still_requires_human_release(monkeypatch, capsys, tmp_path):
    actual_inspect = checker.inspect
    monkeypatch.setattr(checker, "inspect",
                        lambda: actual_inspect(tmp_path, execute_command=runner()[0],
                                               checkout=fake_checkout))
    assert checker.main(["--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "PASS"
    assert report["release_approved"] is False
