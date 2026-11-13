"""Do not expose private database diagnostics in CLI exceptions."""
from io import BytesIO

import pytest

from scripts import backup_mysql


class FailedDump:
    def __init__(self, *args, **kwargs):
        self.stdout = BytesIO(b"CREATE TABLE private_table (id INT);")
        self.stderr = BytesIO(b"MYSQL_PASSWORD=my-secret contact_name=Familia-Teste")
    def wait(self):
        return 4


def test_mysql_dump_failure_never_leaks_stderr_or_keeps_partial_backup(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(backup_mysql.subprocess, "Popen", FailedDump)
    target = tmp_path / "diagnostic.sql.gz"
    with pytest.raises(RuntimeError, match="mysqldump falhou") as exc:
        backup_mysql.backup(target)
    assert "my-secret" not in str(exc.value)
    assert "Familia-Teste" not in str(exc.value)
    assert not target.exists()


def test_mysql_table_digest_failure_redacts_stderr(monkeypatch):
    monkeypatch.setattr(backup_mysql.subprocess, "Popen", FailedDump)
    with pytest.raises(RuntimeError, match="Comparação da tabela") as exc:
        backup_mysql.query_digest("isadora", "families", "id")
    assert "my-secret" not in str(exc.value)
    assert "Familia-Teste" not in str(exc.value)
