"""Read-only XLSX first-sheet reader for the guest-list preview.

Only literal cells are supported. No formulas, macros or external connections run.
"""
from io import BytesIO
from posixpath import join, normpath
from zipfile import ZipFile, BadZipFile
from xml.etree import ElementTree as ET

NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
BASE = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
MAX_UNCOMPRESSED = 2 * 1024 * 1024
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
            result = []
            for row in root.findall(".//x:sheetData/x:row", NS):
                values = [""] * 6
                for cell in row.findall("x:c", NS):
                    ref = cell.attrib.get("r", "")
                    col = "".join(ch for ch in ref if ch.isalpha()).upper()
                    if not col or len(col) != 1 or not ("A" <= col <= "F"):
                        if col:
                            raise ValueError("Use somente as colunas A até F.")
                        continue
                    if cell.find("x:f", NS) is not None:
                        raise ValueError("Não use fórmulas na planilha de convidados.")
                    data_type = cell.attrib.get("t")
                    value = cell.find("x:v", NS)
                    inline = cell.find("x:is", NS)
                    text = value.text if value is not None and value.text is not None else ""
                    if data_type == "s" and text:
                        idx = int(text)
                        if idx < 0 or idx >= len(strings):
                            raise ValueError("Texto compartilhado inválido no Excel.")
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
