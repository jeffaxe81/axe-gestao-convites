#!/usr/bin/env python3
"""Gera convite PDF A5 com botão e QR Code para URL HTTPS de confirmação.

O script é offline e não envia WhatsApp nem publica o convite.
O modo --preview cria uma demonstração SEM link de confirmação.
"""
import argparse
import getpass
from io import BytesIO
import ipaddress
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from uuid import UUID

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A5
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

BUTTER = colors.HexColor("#FFF6D6")
GREEN = colors.HexColor("#435B42")
YELLOW = colors.HexColor("#EEC95D")
CHARCOAL = colors.HexColor("#554D3C")
WHITE = colors.white


def validate_url(value):
    """Aceita somente origem HTTPS pública, sem token, query ou caminho."""
    if not isinstance(value, str) or len(value) > 255:
        raise ValueError("Informe o endereço HTTPS público da confirmação.")
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Endereço HTTPS inválido.") from exc
    if (parsed.scheme != "https" or not host or parsed.netloc != host or
            port is not None or parsed.username or parsed.password or
            parsed.path not in ("", "/") or parsed.query or parsed.fragment or
            not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", host) or
            host.endswith((".local", ".internal", ".test", ".example", ".invalid"))):
        raise ValueError("Use um domínio real HTTPS, sem caminhos ou credenciais.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("O convite exige um domínio DNS, não um endereço IP.")
    return "https://" + host


def validate_family_link(value):
    """Aceita somente um link individual canônico /convite#UUID.TOKEN.

    O fragmento é uma credencial privada: nunca vai para check_production,
    arquivos de log, URL de origem ou uma mensagem de diagnóstico.
    """
    if not isinstance(value, str) or len(value) > 420:
        raise ValueError("Link familiar inválido.")
    try:
        parsed = urlsplit(value)
        origin = validate_url(parsed.scheme + "://" + parsed.netloc)
    except ValueError:
        raise ValueError("Link familiar inválido.") from None
    if parsed.path != "/convite" or parsed.query:
        raise ValueError("O link familiar deve apontar para /convite.")
    parts = parsed.fragment.split(".")
    if len(parts) != 2:
        raise ValueError("O link familiar exige identificador e token.")
    family_id, token = parts
    try:
        family_uuid = UUID(family_id)
    except (TypeError, ValueError, AttributeError):
        raise ValueError("Identificador familiar inválido.") from None
    if (family_uuid.version != 4 or str(family_uuid) != family_id or
            not re.fullmatch(r"[0-9a-f]{64}", token)):
        raise ValueError("Identificador ou token familiar inválido.")
    canonical = origin + "/convite#" + family_id + "." + token
    if canonical != value:
        raise ValueError("Use o link familiar HTTPS original, sem alterações.")
    return canonical


def _public_origin_of_family_link(link):
    """Extrai apenas a origem pública; nunca entrega um token ao verificador."""
    validated = validate_family_link(link)
    return validated.split("/convite#", 1)[0]

def _flower(pdf, cx, cy, radius=12):
    pdf.setFillColor(WHITE)
    for dx, dy in [(0, radius), (radius, 0), (0, -radius), (-radius, 0),
                   (radius * 0.7, radius * 0.7), (-radius * 0.7, radius * 0.7),
                   (radius * 0.7, -radius * 0.7), (-radius * 0.7, -radius * 0.7)]:
        pdf.circle(cx + dx, cy + dy, radius * 0.57, stroke=0, fill=1)
    pdf.setFillColor(YELLOW)
    pdf.circle(cx, cy, radius * 0.53, stroke=0, fill=1)


def _center(pdf, label, y, font="Helvetica", size=14, color=CHARCOAL):
    pdf.setFillColor(color)
    pdf.setFont(font, size)
    pdf.drawCentredString(A5[0] / 2, y, label)


def _qr(pdf, text, x, y, side):
    qr = QrCodeWidget(text)
    x0, y0, x1, y1 = qr.getBounds()
    factor = side / (x1 - x0)
    drawing = Drawing(side, side, transform=[factor, 0, 0, factor, 0, 0])
    drawing.add(qr)
    renderPDF.draw(drawing, pdf, x, y)


def invitation_bytes(url=None, venue=None, *, preview=False, family_link=None):
    if preview and (url is not None or family_link is not None):
        raise ValueError("Demonstração não pode conter URL real.")
    if not preview and (url is None) == (family_link is None):
        raise ValueError("Informe apenas a origem geral ou um link individual.")
    if family_link is not None:
        target_url = validate_family_link(family_link)
    elif not preview:
        # Origem geral só valida o domínio. Não contém um token de
        # família e, portanto, não pode habilitar ações no PDF.
        validate_url(url)
        target_url = None
    else:
        target_url = None
    venue = " ".join((venue or "Local a confirmar").split())
    if not venue or len(venue) > 160:
        raise ValueError("Local deve ter até 160 caracteres.")

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A5, pageCompression=1)
    pdf.setTitle("Convite - 2 anos da Isadora")
    pdf.setAuthor("Familia da Isadora")
    width, height = A5
    pdf.setFillColor(BUTTER)
    pdf.rect(0, 0, width, height, stroke=0, fill=1)
    pdf.setStrokeColor(YELLOW)
    pdf.setLineWidth(2.2)
    pdf.roundRect(17, 17, width - 34, height - 34, 20, stroke=1, fill=0)

    for x, y, radius in [(65, 510, 12), (354, 501, 10), (94, 245, 8),
                         (338, 244, 8), (84, 87, 7), (336, 87, 7)]:
        _flower(pdf, x, y, radius)

    _center(pdf, "UM CONVITE ESPECIAL", 527, "Helvetica-Bold", 11, GREEN)
    _center(pdf, "Isadora", 452, "Times-Bold", 54, GREEN)
    _center(pdf, "2 aninhos", 408, "Helvetica-Bold", 21, CHARCOAL)
    _center(pdf, "Venha celebrar esse dia com a gente!", 374, "Helvetica", 13)
    _center(pdf, "13 de dezembro de 2026", 338, "Helvetica-Bold", 17, GREEN)
    _center(pdf, "Domingo, às 15h", 312, "Helvetica", 15)

    _center(pdf, "LOCAL", 284, "Helvetica-Bold", 10, GREEN)
    lines = simpleSplit(venue, "Helvetica", 13, width - 84)
    if len(lines) > 2:
        raise ValueError("Local muito longo para o convite.")
    for i, line in enumerate(lines):
        _center(pdf, line, 266 - 17 * i, "Helvetica", 13)

    if family_link:
        _qr(pdf, target_url, (width - 81) / 2, 155, 81)
        _center(pdf, "QR individual: escaneie ou toque no botão.", 143,
                "Helvetica", 10)
    else:
        heading = ("DEMONSTRAÇÃO - NÃO ENVIAR" if preview
                   else "MODELO GERAL - NÃO ENVIAR")
        _center(pdf, heading, 194, "Helvetica-Bold", 15, GREEN)
        _center(pdf, "QR Code e botão ativos somente", 169, "Helvetica", 12)
        _center(pdf, "no convite individual da família.", 152, "Helvetica", 12)

    button_x, button_y, button_width, button_height = 67, 87, width - 134, 42
    pdf.setFillColor(GREEN if family_link else colors.HexColor("#9C998B"))
    pdf.roundRect(button_x, button_y, button_width, button_height, 16, stroke=0, fill=1)
    button_label = ("CONFIRMAR PRESENÇA" if family_link
                    else "SEM LINK DE CONFIRMAÇÃO")
    _center(pdf, button_label, 101, "Helvetica-Bold", 12, WHITE)
    if family_link:
        pdf.linkURL(target_url, (button_x, button_y, button_x + button_width,
                                 button_y + button_height), relative=0, thickness=0)
        # A área do QR também abre o link em leitores PDF.
        pdf.linkURL(target_url, ((width - 81) / 2, 155, (width + 81) / 2, 236),
                    relative=0, thickness=0)
        _center(pdf, "Convite individual: compartilhe só com a família.", 73,
                "Helvetica", 9)
    elif not preview:
        _center(pdf, "MODELO GERAL - NÃO ENVIAR AOS CONVIDADOS", 73,
                "Helvetica-Bold", 9, GREEN)
    _center(pdf, "Com carinho, nossa família", 53, "Helvetica-Oblique", 11, GREEN)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def save_invitation(destination, *, url=None, venue=None, preview=False, family_link=None):
    path = Path(destination).expanduser()
    repository = Path(__file__).resolve().parents[1]
    dest = path.parent.resolve() / path.name
    if dest == repository or repository in dest.parents:
        raise ValueError("Grave o PDF fora do repositório.")
    if dest.suffix.lower() != ".pdf" or not dest.parent.is_dir():
        raise ValueError("Informe arquivo .pdf em uma pasta existente.")
    pdf = invitation_bytes(url=url, venue=venue, preview=preview, family_link=family_link)
    fd = os.open(dest, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(pdf)
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    return dest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selected = parser.add_mutually_exclusive_group(required=True)
    selected.add_argument("--url", help="Origem HTTPS geral: somente modelo, NÃO enviar.")
    selected.add_argument("--family-link-stdin", action="store_true",
                          help="Lê link familiar secreto da entrada padrão, sem gravá-lo no shell.")
    selected.add_argument("--preview", action="store_true", help="PDF de demonstração sem link")
    parser.add_argument("--output", required=True, help="Caminho de saída .pdf fora do Git")
    parser.add_argument("--venue", help="Local da festa, se já confirmado")
    parser.add_argument("--check-production", action="store_true",
                        help="Confere HTTPS e acesso privado antes de gerar PDF final")
    args = parser.parse_args()
    try:
        family_link = None
        if args.family_link_stdin:
            if sys.stdin.isatty():
                raw_link = getpass.getpass("Cole o link familiar (oculto): ")
            else:
                raw_link = sys.stdin.readline(513).rstrip("\r\n")
            family_link = validate_family_link(raw_link)
        if args.check_production:
            if args.preview:
                raise ValueError("--check-production exige uma URL HTTPS final.")
            # O verificador só recebe a origem; nunca o fragmento secreto.
            origin = (_public_origin_of_family_link(family_link) if family_link
                      else args.url)
            if __package__:
                from scripts.check_production import verify
            else:
                from check_production import verify
            verify(origin)
        target = save_invitation(args.output, url=args.url, venue=args.venue,
                                 preview=args.preview, family_link=family_link)
    except (ValueError, RuntimeError, OSError) as error:
        parser.error(str(error))
    print("Convite criado: " + str(target))
    if args.preview:
        print("DEMONSTRAÇÃO - PDF sem links. Não envie aos convidados.")
    elif not family_link:
        print("MODELO GERAL - sem QR e sem links ativos; NÃO enviar aos convidados.")
    else:
        print("PDF individual privado. Testar QR/WhatsApp antes de compartilhar.")
        print("O PDF contém credencial familiar: não publicar nem versionar.")


if __name__ == "__main__":
    main()
