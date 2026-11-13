"""Planilha de famílias: modelo e conferência sem persistir dados pessoais."""
import csv
import io
import re
from app.guest_xlsx import xlsx_rows

HEADERS = ("familia", "responsavel", "telefone", "adultos", "criancas_0_5", "criancas_6_12")
EXAMPLE = ("familia-silva", "Maria Silva", "11999999999", "2", "1", "0")
MAX_ROWS = 500


def template_csv():
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";")
    writer.writerow(HEADERS)
    writer.writerow(EXAMPLE)
    return "\ufeff" + output.getvalue()


def preview_csv(contents: bytes, include_records=False):
    """Validate only. Never create guests, RSVPs, links or send invitations."""
    if len(contents) > 60 * 1024:
        raise ValueError("Planilha excede o limite de 60 KB.")
    try:
        source = contents.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Salve a planilha em CSV UTF-8.") from exc
    if "\x00" in source:
        raise ValueError("Arquivo contém caracteres inválidos.")
    reader = csv.reader(io.StringIO(source, newline=""), delimiter=";", strict=True)
    return preview_rows(reader, include_records=include_records)


def preview_xlsx(contents: bytes, include_records=False):
    return preview_rows(xlsx_rows(contents), include_records=include_records)


def preview_rows(reader, include_records=False):
    iterator = iter(reader)
    try:
        header = next(iterator)
    except StopIteration as exc:
        raise ValueError("Planilha vazia.") from exc
    except csv.Error as exc:
        raise ValueError("CSV malformado, confira as aspas e os separadores.") from exc
    if tuple(header) != HEADERS:
        raise ValueError("Cabeçalho inválido. Use as seis colunas do modelo.")
    rows, records, seen, errors = [], [], set(), []
    try:
        for line, cells in enumerate(iterator, start=2):
            if line > MAX_ROWS + 1:
                raise ValueError("Máximo de 500 famílias por planilha.")
            if not any(c.strip() for c in cells):
                continue
            if len(cells) != len(HEADERS):
                errors.append(f"Linha {line}: são necessárias seis colunas.")
                continue
            key, name, phone, adults, young, older = [x.strip() for x in cells]
            if not re.fullmatch(r"[a-zA-Z0-9_-]{3,64}", key):
                errors.append(f"Linha {line}: identificador da família inválido.")
            elif key.casefold() in seen:
                errors.append(f"Linha {line}: família duplicada.")
            seen.add(key.casefold())
            if not name or len(name) > 160 or any(ord(c) < 32 for c in name):
                errors.append(f"Linha {line}: nome do responsável inválido.")
            if phone and not re.fullmatch(r"\+?[0-9]{10,15}", phone):
                errors.append(f"Linha {line}: telefone deve conter 10 a 15 dígitos, com + opcional.")
            counts = []
            for label, value in zip(HEADERS[3:], (adults, young, older)):
                if not re.fullmatch(r"[0-9]{1,2}", value) or int(value) > 30:
                    errors.append(f"Linha {line}: {label} deve ser de 0 a 30.")
                    counts.append(0)
                else:
                    counts.append(int(value))
            if sum(counts) < 1:
                errors.append(f"Linha {line}: informe ao menos uma pessoa.")
            # Only quantitative totals leave this function: no names or phone in UI preview.
            rows.append(counts)
            records.append({'key': key.lower(), 'name': name, 'phone': phone,
                            'adults': counts[0], 'young': counts[1], 'older': counts[2]})
    except csv.Error as exc:
        raise ValueError("CSV malformado, confira as aspas e os separadores.") from exc
    if not rows:
        errors.append("Informe ao menos uma família.")
    report = {
        "valid": not errors,
        "families": len(rows),
        "adults": sum(row[0] for row in rows),
        "children_0_5": sum(row[1] for row in rows),
        "children_6_12": sum(row[2] for row in rows),
        "errors": errors[:25],
        "truncated_errors": len(errors) > 25,
        "saved": False,
        "links_created": 0,
    }
    if include_records and not errors:
        return report, records
    return report
