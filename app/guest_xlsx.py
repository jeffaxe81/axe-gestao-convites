"""Read-only XLSX first-sheet reader for the guest-list preview.

Only literal cells are supported. No formulas, macros or external connections run.
"""
from io import BytesIO
from zipfile import ZipFile, BadZipFile
from xml.etree import ElementTree as ET

NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
BASE = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
MAX_UNCOMPRESSED = 2 * 1024 * 1024


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
            sheet = "xl/worksheets/sheet1.xml"
            if sheet not in names:
                raise ValueError("Primeira aba Excel não encontrada.")
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
