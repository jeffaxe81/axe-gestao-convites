"""Verifica a geração segura do convite PDF, os links e o modo de demonstração."""
import io
import os
import sys

import pytest
from pypdf import PdfReader

from scripts.generate_invitation import (invitation_bytes, save_invitation,\n                                         validate_url, validate_family_link)


@pytest.mark.parametrize("url", [
    "http://convites.festa.com.br", "https://localhost",
    "https://192.168.1.9", "https://convites.example",
    "https://convites.festa.com.br/editar",
    "https://convites.festa.com.br/?token=secreto",
    "https://convites.festa.com.br/#segredo",
    "https://usuario:senha@convites.festa.com.br",
    "https://convites.festa.com.br:8443",
    "https://convites.festa.com.br.evil.invalid",
    "javascript:alert(1)",
])
def test_refuse_unsafe_invitation_links(url):
    with pytest.raises(ValueError):
        validate_url(url)


def test_invitation_has_clickable_url_and_readable_text(tmp_path):
    url = "https://convites.festa.com.br"
    file = tmp_path / "convite.pdf"
    save_invitation(file, url=url, venue="Salão das Flores")
    reader = PdfReader(str(file))
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    assert "Isadora" in text
    assert "13 de dezembro de 2026" in text
    assert "Salão das Flores" in text
    assert "ACESSAR O SITE" in text
    assert "MODELO GERAL" in text
    annotations = reader.pages[0].get("/Annots")
    assert annotations and len(annotations) == 2
    assert all(ref.get_object()["/A"]["/URI"] == url for ref in annotations)


def test_preview_is_explicitly_not_shareable(tmp_path):
    file = tmp_path / "demonstracao.pdf"
    save_invitation(file, preview=True)
    page = PdfReader(str(file)).pages[0]
    assert "DEMONSTRA" in page.extract_text()
    assert not page.get("/Annots")


def test_pdf_destination_must_be_new_and_outside_repository(tmp_path):
    file = tmp_path / "convite.pdf"
    save_invitation(file, preview=True)
    with pytest.raises(FileExistsError):
        save_invitation(file, preview=True)
    with pytest.raises(ValueError, match="fora do repositório"):
        save_invitation("convite-nao-versionar.pdf", preview=True)


def test_reject_conflicting_modes_and_excessive_venue():
    with pytest.raises(ValueError):
        invitation_bytes(preview=True, url="https://convites.festa.com.br")
    with pytest.raises(ValueError):
        invitation_bytes(preview=True, venue="x" * 180)


def test_checked_pdf_requires_successful_live_verification(monkeypatch, tmp_path):
    import sys
    from scripts import check_production, generate_invitation
    target = tmp_path / "ready.pdf"
    checked = []
    monkeypatch.setattr(check_production, "verify", lambda url: checked.append(url))
    monkeypatch.setattr(sys, "argv", [
        "generate_invitation.py", "--url", "https://convites.festa.com.br",
        "--check-production", "--output", str(target)
    ])
    generate_invitation.main()
    assert checked == ["https://convites.festa.com.br"]
    assert target.is_file()


def test_pdf_not_written_when_live_check_fails(monkeypatch, tmp_path):
    import sys
    from scripts import check_production, generate_invitation
    target = tmp_path / "blocked.pdf"
    def reject(_url):
        raise RuntimeError("HTTPS não homologado")
    monkeypatch.setattr(check_production, "verify", reject)
    monkeypatch.setattr(sys, "argv", [
        "generate_invitation.py", "--url", "https://convites.festa.com.br",
        "--check-production", "--output", str(target)
    ])
    with pytest.raises(SystemExit):
        generate_invitation.main()
    assert not target.exists()


def test_cli_checked_pdf_resolves_checker_import_without_pythonpath(tmp_path):
    import subprocess
    import sys
    process = subprocess.run(
        [sys.executable, "scripts/generate_invitation.py",
         "--url", "https://localhost", "--check-production",
         "--output", str(tmp_path / "never.pdf")],
        capture_output=True, text=True, check=False,
    )
    # Invalid local origin is rejected offline; the import itself must succeed.
    assert process.returncode == 2
    assert "ModuleNotFoundError" not in process.stderr
    assert "origem HTTPS" in process.stderr
    assert not (tmp_path / "never.pdf").exists()


FAMILY_LINK = (
    "https://convites.festa.com.br/convite#"
    "550e8400-e29b-41d4-a716-446655440000." + "a" * 64
)


def test_family_pdf_has_exact_secret_link_and_private_permissions(tmp_path):
    target = tmp_path / "convite-individual.pdf"
    assert validate_family_link(FAMILY_LINK) == FAMILY_LINK
    save_invitation(target, family_link=FAMILY_LINK, venue="Salão das Flores")
    page = PdfReader(str(target)).pages[0]
    assert "CONFIRMAR PRESENÇA" in page.extract_text()
    assert "Convite individual" in page.extract_text()
    assert all(ref.get_object()["/A"]["/URI"] == FAMILY_LINK
               for ref in page.get("/Annots"))
    assert os.stat(target).st_mode & 0o777 == 0o600


@pytest.mark.parametrize("link", [
    "https://convites.festa.com.br/convite",
    "http://convites.festa.com.br/convite#550e8400-e29b-41d4-a716-446655440000." + "a"*64,
    "https://convites.festa.com.br/#550e8400-e29b-41d4-a716-446655440000." + "a"*64,
    "https://convites.festa.com.br/convite?x=1#550e8400-e29b-41d4-a716-446655440000." + "a"*64,
    "https://convites.festa.com.br/convite#550e8400-e29b-41d4-a716-446655440000." + "X"*64,
    "https://convites.festa.com.br/convite#550e8400-e29b-41d4-a716-446655440000.bad",
    "https://convites.festa.com.br/convite#550e8400-e29b-11d4-a716-446655440000." + "a"*64,
    "https://convites.festa.com.br/convite#550e8400-e29b-41d4-a716-446655440000." + "a"*64 + " ",
    "https://convites.festa.com.br.evil.invalid/convite#550e8400-e29b-41d4-a716-446655440000." + "a"*64,
])
def test_family_link_rejects_malformed_or_tampered_capability(link):
    with pytest.raises(ValueError):
        validate_family_link(link)


def test_family_pdf_cli_hides_token_and_checks_only_public_origin(tmp_path, monkeypatch, capsys):
    from scripts import check_production, generate_invitation
    target = tmp_path / "convite-privado.pdf"
    checks = []
    monkeypatch.setattr(check_production, "verify", lambda url: checks.append(url))
    monkeypatch.setattr(sys, "stdin", io.StringIO(FAMILY_LINK + "\n"))
    monkeypatch.setattr(sys, "argv", [
        "generate_invitation.py", "--family-link-stdin",
        "--check-production", "--output", str(target),
    ])
    generate_invitation.main()
    printed = capsys.readouterr()
    assert "a" * 64 not in printed.out + printed.err
    assert checks == ["https://convites.festa.com.br"]
    assert target.exists()
    assert all(ref.get_object()["/A"]["/URI"] == FAMILY_LINK
               for ref in PdfReader(str(target)).pages[0].get("/Annots"))


def test_family_pdf_cli_fails_closed_without_valid_secret(tmp_path, monkeypatch, capsys):
    from scripts import generate_invitation
    target = tmp_path / "nao-criado.pdf"
    monkeypatch.setattr(sys, "stdin", io.StringIO("https://convites.festa.com.br\n"))
    monkeypatch.setattr(sys, "argv", [
        "generate_invitation.py", "--family-link-stdin", "--output", str(target),
    ])
    with pytest.raises(SystemExit) as error:
        generate_invitation.main()
    assert error.value.code == 2
    assert not target.exists()
    assert "Link familiar" in capsys.readouterr().err
