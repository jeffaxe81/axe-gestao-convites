"""Read-only XLSX first-sheet reader for the guest-list preview.

Only literal cells are supported. No formulas, macros or external connections run.
"""
from io import BytesIO
from posixpath import join, normpath
import re
from zipfile import ZipFile, BadZipFile
from xml.etree import ElementTree as ET

NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
BASE = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
MAX_UNCOMPRESSED = 2 * 1024 * 1024
MAX_EXCEL_ROWS = 1_048_576
WORKBOOK_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
PACKAGE_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
WORKSHEET_REL_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
)


def first_sheet_path(archive, names):
    """Resolve a primeira aba exibida no Excel via workbook + relacionamentos.

    O nome físico sheet1.xml pode pertencer a uma aba posterior. Uma planilha
    sem metadados ou com aba oculta como primeira é rejeitada em vez de importar
    dados de uma aba diferente da que o organizador selecionou.
    """
    if "xl/workbook.xml" not in names or "xl/_rels/workbook.xml.rels" not in names:
        raise ValueError("Estrutura XLSX incompleta: informações das abas ausentes.")
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    first = workbook.find("x:sheets/x:sheet", NS)
    if first is None:
        raise ValueError("Nenhuma aba Excel disponível.")
    if first.attrib.get("state", "visible") != "visible":
        raise ValueError("A primeira aba Excel precisa estar visível.")
    relationship_id = first.attrib.get(WORKBOOK_REL)
    if not relationship_id:
        raise ValueError("Primeira aba Excel sem relacionamento válido.")

    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    matching = [
        item for item in rels.findall(PACKAGE_REL + "Relationship")
        if item.attrib.get("Id") == relationship_id
    ]
    if (len(matching) != 1 or
            matching[0].attrib.get("Type") != WORKSHEET_REL_TYPE or
            matching[0].attrib.get("TargetMode", "Internal") != "Internal"):
        raise ValueError("Relacionamento da primeira aba Excel inválido.")

    target = matching[0].attrib.get("Target", "")
    if not target or "\\" in target or "%" in target or "?" in target or "#" in target:
        raise ValueError("Caminho da primeira aba Excel inválido.")
    path = (normpath(target.lstrip("/")) if target.startswith("/")
            else normpath(join("xl", target)))
    if not path.startswith("xl/worksheets/") or not path.endswith(".xml") or path not in names:
        raise ValueError("Primeira aba Excel não encontrada no arquivo.")
    return path


def parse_excel_row(value):
    """Rejeitar índices fora do formato e limite Excel antes de chamar int().

    O uso anterior de isdecimal()/int() permitia números com milhares de
    dígitos, que geravam ValueError não normalizado e podiam virar HTTP 500.
    """
    if not re.fullmatch(r"[1-9][0-9]{0,6}", value):
        raise ValueError("Número de linha Excel inválido.")
    number = int(value)
    if number > MAX_EXCEL_ROWS:
        raise ValueError("Número de linha Excel inválido.")
    return number


def hidden_attribute(element):
    """Excel serializa o atributo hidden como 1/0 ou true/false."""
    value = element.attrib.get("hidden")
    return value is not None and value.strip().lower() not in ("0", "false")


def verify_visible_columns(sheet):
    """Não importar uma coluna obrigatória que o organizador não vê."""
    for column in sheet.findall("x:cols/x:col", NS):
        if not hidden_attribute(column):
            continue
        try:
            lower = int(column.attrib["min"])
            upper = int(column.attrib["max"])
        except (KeyError, ValueError) as exc:
            raise ValueError("Definição de coluna oculta inválida.") from exc
        if lower < 1 or upper < lower:
            raise ValueError("Definição de coluna oculta inválida.")
        if lower <= 6 and upper >= 1:
            raise ValueError(
                "Colunas A até F não podem estar ocultas. Reexiba antes de importar."
            )


def xlsx_rows(contents):
    if len(contents) > 60 * 1024:
        raise ValueError("Planilha excede o limite de 60 KB.")
    try:
        with ZipFile(BytesIO(contents)) as archive:
            names = archive.namelist()
            if len(names) > 120 or len(names) != len(set(names)):
                raise ValueError("Arquivo Excel contém componentes demais.")
            total = sum(i.file_size for i in archive.infolist())
            if total > MAX_UNCOMPRESSED:
                raise ValueError("Arquivo Excel excede o limite de expansão.")
            if any(name.endswith("vbaProject.bin") for name in names):
                raise ValueError("Planilhas com macros não são aceitas.")
            sheet = first_sheet_path(archive, names)
            strings = []
            if "xl/sharedStrings.xml" in names:
                root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                for item in root.findall("x:si", NS):
                    strings.append("".join(node.text or "" for node in item.iter(BASE + "t")))
            root = ET.fromstring(archive.read(sheet))
            verify_visible_columns(root)
            result = []
            seen_rows = set()
            for row in root.findall(".//x:sheetData/x:row", NS):
                if hidden_attribute(row):
                    raise ValueError(
                        "A planilha contém linhas ocultas. Reexiba antes de importar."
                    )
                row_id = row.attrib.get("r")
                row_number = None
                if row_id is not None:
                    row_number = parse_excel_row(row_id)
                    if row_number in seen_rows:
                        raise ValueError("Linha repetida ou inválida na planilha Excel.")
                    seen_rows.add(row_number)
                values = [""] * 6
                seen_columns = set()
                for cell in row.findall("x:c", NS):
                    ref = cell.attrib.get("r", "")
                    match = re.fullmatch(r"([A-Z]+)([1-9][0-9]{0,6})", ref.upper())
                    if match is None:
                        raise ValueError("Referência de célula Excel inválida.")
                    col, cell_row = match.groups()
                    if len(col) != 1 or not ("A" <= col <= "F"):
                        raise ValueError("Use somente as colunas A até F.")
                    cell_number = parse_excel_row(cell_row)
                    if row_number is not None and cell_number != row_number:
                        raise ValueError("Célula fora da linha declarada no Excel.")
                    if col in seen_columns:
                        raise ValueError("Célula duplicada na planilha Excel.")
                    seen_columns.add(col)
                    if cell.find("x:f", NS) is not None:
                        raise ValueError("Não use fórmulas na planilha de convidados.")
                    data_type = cell.attrib.get("t")
                    value = cell.find("x:v", NS)
                    inline = cell.find("x:is", NS)
                    text = value.text if value is not None and value.text is not None else ""
                    if data_type == "s":
                        # Índices XLSX devem ser decimais ASCII. Evite converter
                        # dados arbitrários ou inteiros enormes e nunca exponha
                        # o conteúdo inválido na mensagem de erro ao organizador.
                        if not re.fullmatch(r"[0-9]{1,10}", text):
                            raise ValueError("Índice de texto compartilhado inválido no Excel.")
                        idx = int(text)
                        if idx >= len(strings):
                            raise ValueError("Índice de texto compartilhado inválido no Excel.")
                        text = strings[idx]
                    elif data_type == "inlineStr" and inline is not None:
                        text = "".join(n.text or "" for n in inline.iter(BASE + "t"))
                    elif data_type in ("e", "b"):
                        raise ValueError("Use somente texto e números na planilha.")
                    values[ord(col) - 65] = text
                result.append(values)
                if len(result) > 502:
                    raise ValueError("Máximo de 500 famílias por planilha.")
            return result
    except (BadZipFile, ET.ParseError, KeyError, OverflowError, IndexError) as exc:
        raise ValueError("Arquivo XLSX inválido ou danificado.") from exc
