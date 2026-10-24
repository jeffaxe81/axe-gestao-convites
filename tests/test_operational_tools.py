"""Testes de proteção das ferramentas operacionais sem Docker ou internet."""
from pathlib import Path

import pytest

from scripts.backup_mysql import backup
from scripts.check_production import validate_origin


@pytest.mark.parametrize("value", [
    "http://convites.example.com",
    "https://localhost",
    "https://127.0.0.1:443",
    "https://convites.example.com/path",
    "https://user:password@convites.example.com",
    "https://convites.example.com/?token=segredo",
    "https://convites.example.com/#fragment",
    "convites.example.com",
])
def test_publication_checker_rejects_unsafe_origin(value):
    with pytest.raises(ValueError):
        validate_origin(value)


def test_publication_checker_accepts_public_https_origin():
    assert validate_origin("https://convites.example.com") == (
        "https://convites.example.com", "convites.example.com"
    )


def test_backup_refuses_repository_destination_without_writing():
    destination = Path(__file__).resolve().parents[1] / "unsafe-backup.sql.gz"
    with pytest.raises(ValueError, match="fora do repositório"):
        backup(destination)
    assert not destination.exists()


def test_backup_requires_gzip_sql_extension_without_writing(tmp_path):
    destination = tmp_path / "unsafe.sql"
    with pytest.raises(ValueError, match="sql.gz"):
        backup(destination)
    assert not destination.exists()
