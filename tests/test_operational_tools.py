"""Testes de proteção das ferramentas operacionais sem Docker ou internet."""
from pathlib import Path
from email.message import Message
from urllib.request import Request

import pytest

from scripts.backup_mysql import backup, validated_backup_source
from scripts.check_production import _StrictOriginRedirect, has_safe_admin_cookie, validate_origin


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


def _cookie_headers(*entries):
    headers = Message()
    for entry in entries:
        headers.add_header("Set-Cookie", entry)
    return headers


def test_checker_accepts_real_secure_admin_cookie():
    headers = _cookie_headers(
        "other=value; Path=/; Secure; HttpOnly",
        "session=abc123; Path=/; Secure; HttpOnly; SameSite=Lax",
    )
    assert has_safe_admin_cookie(headers)


@pytest.mark.parametrize("header", [
    "session=abc123; Path=/; HttpOnly; SameSite=Lax",
    "session=abc123; Path=/; Secure; SameSite=Lax",
    "session=abc123; Path=/; Secure; HttpOnly; SameSite=None",
    "session=abc123; Path=/organizar; Secure; HttpOnly; SameSite=Lax",
    "session=abc123; Path=/; insecure=true; nothttponly=true; SameSite=Lax",
    "insecure_session=abc123; Path=/; Secure; HttpOnly; SameSite=Lax",
    "session=abc123; Path=/; Secure; HttpOnly",
])
def test_checker_rejects_insecure_or_misleading_cookie(header):
    assert not has_safe_admin_cookie(_cookie_headers(header))


def test_checker_rejects_empty_cookie_headers():
    assert not has_safe_admin_cookie(_cookie_headers())


@pytest.mark.parametrize("target", [
    "http://convites.example.com/api/event",
    "https://outro.example.com/api/event",
    "https://convites.example.com.evil.com/api/event",
])
def test_checker_blocks_off_origin_redirect_before_following(target):
    redirect = _StrictOriginRedirect("convites.example.com")
    request = Request("https://convites.example.com/api/event")
    with pytest.raises(RuntimeError, match="Redirecionamento"):
        redirect.redirect_request(request, None, 302, "Found", {}, target)


@pytest.mark.parametrize("value", [
    "https://127.0.0.1", "https://10.0.0.8",
    "https://convites.example.com:8443", "https://convites.local",
    "https://convites.invalid", "https://convites..com",
])
def test_checker_rejects_non_public_or_malformed_hosts(value):
    with pytest.raises(ValueError):
        validate_origin(value)


def test_restore_rejects_symlink_even_when_target_is_private(tmp_path):
    original = tmp_path / "original.sql.gz"
    original.write_bytes(b"backup")
    original.chmod(0o600)
    alias = tmp_path / "alias.sql.gz"
    alias.symlink_to(original)
    with pytest.raises(ValueError, match="link simbólico"):
        validated_backup_source(alias)


def test_restore_rejects_world_readable_personal_data(tmp_path):
    file = tmp_path / "backup.sql.gz"
    file.write_bytes(b"backup")
    file.chmod(0o644)
    with pytest.raises(ValueError, match="chmod 600"):
        validated_backup_source(file)
    file.chmod(0o600)
    assert validated_backup_source(file) == file
