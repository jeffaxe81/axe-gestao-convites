"""Exportação exclusivamente administrativa de confirmações para planilhas.

Nunca exportar tokens de edição, hashes ou configurações internas.
Nomes de convidados são dados não confiáveis e não podem virar fórmulas CSV.
"""
import csv
import io
import re


COLUMNS = ("Situação", "Família / contato", "Participante",
           "Categoria", "Idade", "Buffet", "Lembrancinha")


def safe_cell(value):
    """Impede injeção de fórmulas em Excel e outros leitores de CSV."""
    text = str(value) if value is not None else ""
    # Evita fórmulas iniciadas depois de espaços/controles, mesmo em nomes inesperados.
    if re.match(r"^[\s\ufeff]*[=+\-@]", text) or text[:1] in ("\t", "\r", "\n"):
        return "'" + text
    return text


def export_attendance_csv(summary):
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_ALL,
                        lineterminator="\r\n")
    writer.writerow(COLUMNS)
    for family in summary["confirmed"]:
        for person in family["participants"]:
            child = person["kind"] == "CHILD"
            age = person.get("age_years")
            writer.writerow([safe_cell(item) for item in (
                "Confirmado", family["contact_name"], person["name"],
                "Criança" if child else "Acima de 12",
                age if child else "",
                "Não" if child and age <= 5 else "Sim",
                "Sim" if child else "Não",
            )])
    for family in summary["declined"]:
        writer.writerow([safe_cell(item) for item in (
            "Recusou", family["contact_name"], "", "", "", "Não", "Não",
        )])
    # UTF-8 BOM para reconhecimento adequado do Excel/Windows pt-BR.
    return output.getvalue().encode("utf-8-sig")
