"""MySQL subprocesses must not create a second pipe that can deadlock.

The test doubles never access a database or a real Docker container.
"""
import gzip
import hashlib
from io import BytesIO
import subprocess

import pytest

from scripts import backup_mysql


class NoReadStderr:
    def read(self, *args, **kwargs):
        pytest.fail("Private MySQL stderr must never be buffered or read")


class FakeProcess:
    def __init__(self, exit_code=0, stdout=b"synthetic-test"):
        self.stdout = BytesIO(stdout)
        self.stdin = BytesIO()
        self.stderr = NoReadStderr()
        self.exit_code = exit_code

    def wait(self):
        return self.exit_code


def process_spy(monkeypatch, exit_code=0, stdout=b"synthetic-test"):
    called = []

    def make_process(command, **kwargs):
        called.append((command, kwargs))
        assert kwargs.get("stderr") == subprocess.DEVNULL
        assert kwargs.get("stderr") != subprocess.PIPE
        return FakeProcess(exit_code, stdout)

    monkeypatch.setattr(backup_mysql.subprocess, "Popen", make_process)
    return called


def test_dump_failing_process_never_pipes_stderr_or_leaves_backup(
    monkeypatch, tmp_path
):
    calls = process_spy(monkeypatch, exit_code=4)
    target = tmp_path / "familia-ficticia.sql.gz"
    with pytest.raises(RuntimeError, match="mysqldump falhou") as error:
        backup_mysql.backup(target)
    assert len(calls) == 1
    assert "docker" in calls[0][0]
    assert not target.exists()
    assert "MYSQL_PASSWORD" not in str(error.value)


def test_digest_reads_stdout_only_and_ignores_stderr(monkeypatch):
    calls = process_spy(monkeypatch, stdout=b"data-ficticia")
    digest, length = backup_mysql.query_digest(
        "isadora_test", "families", "id"
    )
    assert digest == hashlib.sha256(b"data-ficticia").hexdigest()
    assert length == len(b"data-ficticia")
    assert len(calls) == 1


def test_restore_streams_stdin_without_piping_stderr(monkeypatch, tmp_path):
    calls = process_spy(monkeypatch)
    db_commands = []
    monkeypatch.setattr(backup_mysql, "database_name", lambda: "isadora_test")
    monkeypatch.setattr(
        backup_mysql, "query_digest", lambda database, table, columns: (
            "same-digest", 123
        )
    )
    monkeypatch.setattr(
        backup_mysql, "run_db",
        lambda *args: db_commands.append(args) or b"",
    )
    source = tmp_path / "synthetic.sql.gz"
    with gzip.open(source, "wb") as output:
        output.write(b"CREATE TABLE fake_test (id INT);")
    source.chmod(0o600)

    backup_mysql.verify_restore(source)

    assert len(calls) == 1
    assert calls[0][1]["stdin"] == subprocess.PIPE
    assert calls[0][1]["stdout"] == subprocess.DEVNULL
    assert len(db_commands) == 2
    assert "CREATE DATABASE" in db_commands[0][1]
    assert "DROP DATABASE" in db_commands[1][1]
