#!/usr/bin/env python3
"""Gera convite PDF A5 com botão e QR Code para URL HTTPS de confirmação.

O script é offline e não envia WhatsApp nem publica o convite.
O modo --preview cria uma demonstração SEM link de confirmação.
"""
import argparse
from io import BytesIO
import ipaddress
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

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


def invitation_bytes(url=None, venue=None, *, preview=False):
    if preview and url is not None:
        raise ValueError("Demonstração não pode conter URL real.")
    if not preview:
        url = validate_url(url)
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

    if preview:
        _center(pdf, "DEMONSTRAÇÃO - NÃO ENVIAR", 194, "Helvetica-Bold", 15, GREEN)
        _center(pdf, "O botão e o QR Code aparecerão", 169, "Helvetica", 12)
        _center(pdf, "após configurar o domínio real.", 152, "Helvetica", 12)
    else:
        _qr(pdf, url, (width - 81) / 2, 155, 81)
        _center(pdf, "Escaneie o QR Code ou toque no botão:", 143, "Helvetica", 10)

    button_x, button_y, button_width, button_height = 67, 87, width - 134, 42
    pdf.setFillColor(GREEN if not preview else colors.HexColor("#9C998B"))
    pdf.roundRect(button_x, button_y, button_width, button_height, 16, stroke=0, fill=1)
    _center(pdf, "CONFIRMAR PRESENÇA", 101, "Helvetica-Bold", 13, WHITE)
    if not preview:
        pdf.linkURL(url, (button_x, button_y, button_x + button_width,
                          button_y + button_height), relative=0, thickness=0)
        # A área do QR também abre o link em leitores PDF.
        pdf.linkURL(url, ((width - 81) / 2, 155, (width + 81) / 2, 236),
                    relative=0, thickness=0)
    _center(pdf, "Com carinho, nossa família", 53, "Helvetica-Oblique", 11, GREEN)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def save_invitation(destination, *, url=None, venue=None, preview=False):
    path = Path(destination).expanduser()
    repository = Path(__file__).resolve().parents[1]
    dest = path.parent.resolve() / path.name
    if dest == repository or repository in dest.parents:
        raise ValueError("Grave o PDF fora do repositório.")
    if dest.suffix.lower() != ".pdf" or not dest.parent.is_dir():
        raise ValueError("Informe arquivo .pdf em uma pasta existente.")
    pdf = invitation_bytes(url=url, venue=venue, preview=preview)
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
    selected.add_argument("--url", help="Origem HTTPS final, ex.: https://convites.seudominio.com.br")
    selected.add_argument("--preview", action="store_true", help="PDF de demonstração sem link")
    parser.add_argument("--output", required=True, help="Caminho de saída .pdf fora do Git")
    parser.add_argument("--venue", help="Local da festa, se já confirmado")
    parser.add_argument("--check-production", action="store_true",
                        help="Confere HTTPS e acesso privado antes de gerar PDF final")
    args = parser.parse_args()
    try:
        if args.check_production:
            if args.preview:
                raise ValueError("--check-production exige --url HTTPS final.")
            from scripts.check_production import verify
            verify(args.url)
        target = save_invitation(args.output, url=args.url, venue=args.venue,
                                 preview=args.preview)
    except (ValueError, RuntimeError, OSError) as error:
        parser.error(str(error))
    print("Convite criado: " + str(target))
    if args.preview:
        print("DEMONSTRAÇÃO - PDF sem links. Não envie aos convidados.")
    else:
        print("ATENÇÃO: confirme HTTPS e teste o QR/WhatsApp antes de compartilhar.")


if __name__ == "__main__":
    main()
