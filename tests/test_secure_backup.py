"""Backup AES-GCM: integridade, permissões, streaming e proteção contra sobrescrita."""
import os

import pytest

from cryptography.exceptions import InvalidTag
from scripts.secure_backup import encrypt, decrypt


PASSPHRASE = "frase-secreta-de-teste-grande-e-aleatoria-12345678"


def sample_file(tmp_path, size=1024):
    source = tmp_path / "original.sql.gz"
    source.write_bytes(os.urandom(size))
    return source


def test_encrypted_round_trip(tmp_path):
    raw = sample_file(tmp_path, size=2 * 1024 * 1024 + 33)
    encrypted = tmp_path / "original.sql.gz.isadora"
    recovered = tmp_path / "restaurado.sql.gz"
    encrypt(raw, encrypted, PASSPHRASE)
    assert encrypted.read_bytes().startswith(b"ISADORA1")
    assert raw.read_bytes() not in encrypted.read_bytes()
    assert (encrypted.stat().st_mode & 0o777) == 0o600
    decrypt(encrypted, recovered, PASSPHRASE)
    assert recovered.read_bytes() == raw.read_bytes()
    assert (recovered.stat().st_mode & 0o777) == 0o600


def test_wrong_password_removes_partial_output(tmp_path):
    source = sample_file(tmp_path)
    encrypted = tmp_path / "out.isadora"
    restored = tmp_path / "result.sql.gz"
    encrypt(source, encrypted, PASSPHRASE)
    with pytest.raises(InvalidTag):
        decrypt(encrypted, restored, "incorrect-passphrase-long-enough")
    assert not restored.exists()


def test_modified_ciphertext_fails_integrity(tmp_path):
    source = sample_file(tmp_path, 1024)
    encrypted = tmp_path / "out.isadora"
    restored = tmp_path / "restored.sql.gz"
    encrypt(source, encrypted, PASSPHRASE)
    data = bytearray(encrypted.read_bytes())
    data[40] ^= 0x20
    encrypted.write_bytes(data)
    with pytest.raises(InvalidTag):
        decrypt(encrypted, restored, PASSPHRASE)
    assert not restored.exists()


def test_output_is_never_overwritten_or_deleted(tmp_path):
    source = sample_file(tmp_path)
    output = tmp_path / "locked.isadora"
    output.write_bytes(b"existing archive")
    with pytest.raises(FileExistsError):
        encrypt(source, output, PASSPHRASE)
    assert output.read_bytes() == b"existing archive"


def test_existing_restoration_is_never_overwritten_or_deleted(tmp_path):
    source = sample_file(tmp_path)
    encrypted = tmp_path / "out.isadora"
    target = tmp_path / "result.sql.gz"
    encrypt(source, encrypted, PASSPHRASE)
    target.write_bytes(b"keep me")
    with pytest.raises(FileExistsError):
        decrypt(encrypted, target, PASSPHRASE)
    assert target.read_bytes() == b"keep me"


def test_short_secret_rejected_without_output(tmp_path):
    source = sample_file(tmp_path)
    target = tmp_path / "out.isadora"
    with pytest.raises(ValueError, match="16"):
        encrypt(source, target, "short")
    assert not target.exists()


def test_rejects_invalid_extensions_and_repo_output(tmp_path):
    source = sample_file(tmp_path)
    with pytest.raises(ValueError, match="extensão"):
        encrypt(source, tmp_path / "plain.sql.gz", PASSPHRASE)
    with pytest.raises(ValueError, match="regular"):
        encrypt(tmp_path / "missing.sql.gz", tmp_path / "x.isadora", PASSPHRASE)
    with pytest.raises(ValueError, match="repositório"):
        encrypt(source, "tests/private.isadora", PASSPHRASE)
