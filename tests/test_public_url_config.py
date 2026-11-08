"""Domain can be assigned later without rebuilding the code or disclosing secrets."""
from pathlib import Path
import stat
import subprocess
import sys
import pytest
from scripts.set_public_url import LOCAL_ORIGIN, normalize_origin, update_env
from scripts.preflight import validate
from tests.test_preflight import configuration


def _env(tmp_path, contents="APP_PUBLIC_URL=http://127.0.0.1:8080\nTOKEN_SECRET=very_private_secret\n"):
    file = tmp_path / ".env"
    file.write_bytes(contents.encode("utf-8"))
    file.chmod(0o600)
    return file


def test_change_domain_without_changing_secret(tmp_path):
    file = _env(tmp_path)
    assert update_env(file, normalize_origin("convites.festa.com.br")) == "https://convites.festa.com.br"
    assert file.read_text() == "APP_PUBLIC_URL=https://convites.festa.com.br\nTOKEN_SECRET=very_private_secret\n"
    assert stat.S_IMODE(file.stat().st_mode) == 0o600
    assert update_env(file, normalize_origin("https://outro.festa.com.br")) == "https://outro.festa.com.br"
    assert "TOKEN_SECRET=very_private_secret" in file.read_text()


def test_reset_to_local_without_domain(tmp_path):
    file = _env(tmp_path)
    update_env(file, normalize_origin("convites.festa.com.br"))
    update_env(file, normalize_origin(local=True))
    assert file.read_text().startswith("APP_PUBLIC_URL=" + LOCAL_ORIGIN)


@pytest.mark.parametrize("invalid", [
    "http://convites.festa.com.br", "https://localhost", "https://10.10.10.1",
    "https://convites.festa.com.br/rsvp", "https://convites.festa.com.br?token=secret",
    "convites.festa.com.br:443", "https://user:password@convites.festa.com.br",
    "convites.invalid", "",
])
def test_refuse_unsafe_domain_without_mutation(tmp_path, invalid):
    file = _env(tmp_path)
    before = file.read_bytes()
    with pytest.raises(ValueError):
        update_env(file, normalize_origin(invalid))
    assert file.read_bytes() == before


def test_preflight_rejects_local_in_production_but_accepts_valid_domain(tmp_path):
    file = _env(tmp_path)
    config = configuration()
    config["APP_PUBLIC_URL"] = LOCAL_ORIGIN
    assert validate(config, allow_local=True) == []
    assert validate(config)
    config["APP_PUBLIC_URL"] = update_env(file, normalize_origin("convites.festa.com.br"))
    assert validate(config) == []


def test_reject_symlink_and_public_permissions(tmp_path):
    target = _env(tmp_path)
    alias = tmp_path / "alias.env"
    alias.symlink_to(target)
    with pytest.raises(ValueError, match="simbólico"):
        update_env(alias, "https://convites.festa.com.br")
    target.chmod(0o644)
    with pytest.raises(ValueError, match="chmod 600"):
        update_env(target, "https://convites.festa.com.br")


def test_reject_duplicate_variable(tmp_path):
    file = _env(tmp_path, "APP_PUBLIC_URL=http://localhost:8080\nAPP_PUBLIC_URL=http://localhost:8080\n")
    with pytest.raises(ValueError, match="exatamente uma"):
        update_env(file, "https://convites.festa.com.br")


def test_preserve_crlf_and_other_lines(tmp_path):
    file = _env(tmp_path, "MYSQL_PASSWORD=unknown\r\nAPP_PUBLIC_URL=http://127.0.0.1:8080\r\n")
    update_env(file, "https://convites.festa.com.br")
    assert file.read_bytes() == (b"MYSQL_PASSWORD=unknown\r\n"
                                 b"APP_PUBLIC_URL=https://convites.festa.com.br\r\n")


def test_direct_cli_local_then_public_domain(tmp_path):
    file = _env(tmp_path)
    script = Path(__file__).resolve().parents[1] / "scripts" / "set_public_url.py"
    command = [sys.executable, str(script), "--env-file", str(file)]
    result = subprocess.run(command + ["--local"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "MODO LOCAL" in result.stdout
    assert "very_private_secret" not in result.stdout + result.stderr
    later = subprocess.run(command + ["--domain", "convites.festa.com.br"],
                           capture_output=True, text=True)
    assert later.returncode == 0, later.stderr
    assert "https://convites.festa.com.br" in file.read_text()
    assert "very_private_secret" not in later.stdout + later.stderr
