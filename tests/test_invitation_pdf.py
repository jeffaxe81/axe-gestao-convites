"""Verifica a geração segura do convite PDF, os links e o modo de demonstração."""
import pytest
from pypdf import PdfReader

from scripts.generate_invitation import invitation_bytes, save_invitation, validate_url


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
    assert "CONFIRMAR PRESENÇA" in text
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
