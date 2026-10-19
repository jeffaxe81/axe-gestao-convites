"""Preflight impede configurações inseguras sem publicar senhas nos erros."""
from pathlib import Path

import pytest

from scripts.preflight import load_env, validate


def configuration():
    return {
        "MYSQL_DATABASE": "isadora", "MYSQL_USER": "isadora",
        "MYSQL_PASSWORD": "a" * 40, "MYSQL_ROOT_PASSWORD": "b" * 40,
        "TOKEN_SECRET": "c" * 40, "SESSION_SECRET": "d" * 40,
        "ORGANIZER_USERNAME": "organizador",
        "ORGANIZER_PASSWORD_HASH": "scrypt:32768:8:1$salt$hash",
        "APP_PUBLIC_URL": "https://convites.isadora.com.br",
        "TRUSTED_PROXY_HOPS": "0",
    }


def test_good_production_env():
    assert validate(configuration()) == []


@pytest.mark.parametrize("url", [
    "http://convites.isadora.com.br", "https://localhost",
    "https://10.0.0.10", "https://convites.example",
    "https://convites.isadora.com.br/path",
    "https://usuario:senha@convites.isadora.com.br",
    "https://convites.isadora.com.br#private",
])
def test_reject_unsafe_public_origin(url):
    options = configuration()
    options["APP_PUBLIC_URL"] = url
    assert validate(options)


def test_reject_placeholder_secrets():
    options = configuration()
    options["MYSQL_PASSWORD"] = "SUBSTITUIR_POR_SENHA_COM_64_CARACTERES"
    assert any("MYSQL_PASSWORD" in item for item in validate(options))


def test_reject_reused_tokens():
    options = configuration()
    options["SESSION_SECRET"] = options["TOKEN_SECRET"]
    assert any("diferentes" in item for item in validate(options))


def test_reject_weak_password_hash():
    options = configuration()
    options["ORGANIZER_PASSWORD_HASH"] = "senha-plana"
    assert any("Werkzeug" in item for item in validate(options))


def test_proxy_opt_in_requires_manual_exception():
    options = configuration()
    options["TRUSTED_PROXY_HOPS"] = "1"
    assert validate(options)
    assert validate(options, allow_proxy=True) == []


def test_private_env_file_mode_and_duplicate_entries(tmp_path):
    file = tmp_path / ".env"
    file.write_text("MYSQL_USER=isadora\nMYSQL_USER=outra\n")
    file.chmod(0o600)
    with pytest.raises(ValueError, match="repetida"):
        load_env(file)
    file.write_text("MYSQL_USER=isadora\n")
    file.chmod(0o644)
    with pytest.raises(ValueError, match="chmod 600"):
        load_env(file)


def test_env_never_follows_symlink(tmp_path):
    target = tmp_path / "real.env"
    target.write_text("MYSQL_USER=isadora\n")
    target.chmod(0o600)
    link = tmp_path / ".env"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="regular"):
        load_env(link)
