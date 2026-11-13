"""Release evidence declarations must remain private and out of Git.

No network, Docker, production database or actual guest information is used.
"""
import json
import os
import stat

import pytest

from scripts import release_readiness as readiness


def private_folder(tmp_path):
    folder = tmp_path / "evidencias"
    folder.mkdir(mode=0o700)
    folder.chmod(0o700)
    return folder


def write_manifest(folder, *, mode=0o600, data=None, filename="humanas.json"):
    path = folder / filename
    value = (readiness.GATES if data is None else data)
    if value is readiness.GATES:
        value = {key: {"verified": False, "verified_at": None, "evidence_ref": None}
                 for key in readiness.GATES}
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(mode)
    return path


def test_private_manifest_is_read_and_remains_blocked(tmp_path, capsys):
    path = write_manifest(private_folder(tmp_path))
    assert readiness.load_private_manifest(str(path))["aceite_operacional"]["verified"] is False
    assert readiness.main(["--evidence-file", str(path), "--json"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["release_approved"] is False
    assert result["ready_for_human_review"] is False
    assert result["human_evidence_declared"] == 0
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.parametrize("mode", [0o644, 0o640, 0o666, 0o777])
def test_world_or_group_readable_manifest_is_rejected(tmp_path, mode):
    path = write_manifest(private_folder(tmp_path), mode=mode)
    with pytest.raises(ValueError, match="0600"):
        readiness.load_private_manifest(str(path))


def test_public_directory_blocks_before_reading_manifest(tmp_path):
    folder = private_folder(tmp_path)
    path = write_manifest(folder)
    folder.chmod(0o755)
    with pytest.raises(ValueError, match="0700"):
        readiness.load_private_manifest(str(path))


def test_manifest_inside_checkout_is_rejected(tmp_path):
    checkout = tmp_path / "repo"
    checkout.mkdir(mode=0o700)
    checkout.chmod(0o700)
    path = write_manifest(checkout)
    with pytest.raises(ValueError, match="fora do repositório"):
        readiness.load_private_manifest(str(path), root=checkout)


def test_final_symlink_cannot_be_used_as_manifest(tmp_path):
    folder = private_folder(tmp_path)
    original = write_manifest(folder, filename="original.json")
    link = folder / "humanas.json"
    link.symlink_to(original)
    with pytest.raises(ValueError, match="simbólicos"):
        readiness.load_private_manifest(str(link))
    assert json.loads(original.read_text())["dns_https"]["verified"] is False


def test_oversized_manifest_is_rejected_without_parsing(tmp_path):
    folder = private_folder(tmp_path)
    path = folder / "huge.json"
    path.write_bytes(b"x" * (readiness.MAX_MANIFEST_BYTES + 1))
    path.chmod(0o600)
    with pytest.raises(ValueError, match="tamanho"):
        readiness.load_private_manifest(str(path))


@pytest.mark.parametrize("name", ["relative.json", "/tmp/no-extension", "private.txt"])
def test_wrong_filename_or_relative_path_is_rejected_before_read(name):
    with pytest.raises(ValueError, match="caminho absoluto"):
        readiness.load_private_manifest(name)


def test_directory_cannot_be_parsed_as_file(tmp_path):
    folder = private_folder(tmp_path)
    fake = folder / "manifest.json"
    fake.mkdir(mode=0o700)
    with pytest.raises(ValueError, match="0600"):
        readiness.load_private_manifest(str(fake))


def test_error_messages_do_not_expose_path_or_manifest_bytes(tmp_path, capsys):
    folder = private_folder(tmp_path)
    file = folder / "TOKEN_SECRET-should-never-appear.json"
    file.write_text("FAMILIA_SUPER_PRIVADA", encoding="utf-8")
    file.chmod(0o600)
    assert readiness.main(["--evidence-file", str(file), "--json"]) == 2
    captured = capsys.readouterr()
    assert "TOKEN_SECRET" not in captured.out + captured.err
    assert "FAMILIA_SUPER_PRIVADA" not in captured.out + captured.err


def test_no_plaintext_output_contains_evidence_ref(tmp_path, capsys):
    folder = private_folder(tmp_path)
    data = {key: {"verified": False, "verified_at": None, "evidence_ref": None}
            for key in readiness.GATES}
    data["dns_https"] = {
        "verified": True, "verified_at": "2026-11-11T12:00:00-03:00",
        "evidence_ref": "referencia-interna-secreta-a-omitir",
    }
    path = write_manifest(folder, data=data)
    assert readiness.main(["--evidence-file", str(path)]) == 1
    text = capsys.readouterr().out
    assert "secreta" not in text
    assert "LIBERAÇÃO BLOQUEADA" in text
