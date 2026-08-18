"""
Gera planilhas .xlsx DE VERDADE (abrem no Excel/LibreOffice) — SEM bibliotecas
externas. Um .xlsx nada mais é que um .zip com alguns arquivos XML dentro; aqui
montamos esses XML na mão, no mesmo espírito das etiquetas Code 39 e da cripto.

Suporta texto e números (número entra como número, para o Excel somar/filtrar),
cabeçalho em negrito, largura de colunas e filtro automático.

Uso:
    import xlsx
    xlsx.escrever("saida.xlsx", ["Nome", "Valor"],
                  [["Teclado", 80], ["Mouse", 50]], larguras=[20, 12])
"""

import zipfile
from datetime import datetime
from xml.sax.saxutils import escape


def _col(n):
    """1 -> 'A', 2 -> 'B', 27 -> 'AA' (referência de coluna do Excel)."""
    letras = ""
    while n > 0:
        n, resto = divmod(n - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def _celula(ref, valor, estilo=0):
    """XML de uma célula. Número vira <v>; o resto vira texto embutido."""
    if isinstance(valor, bool):
        valor = "Sim" if valor else "Não"
    s = f' s="{estilo}"' if estilo else ""
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return f'<c r="{ref}"{s}><v>{valor}</v></c>'
    texto = escape(str(valor))
    # xml:space preserva espaços no começo/fim
    return f'<c r="{ref}"{s} t="inlineStr"><is><t xml:space="preserve">{texto}</t></is></c>'


def _linha_xml(num, valores, estilo=0):
    celulas = []
    for i, v in enumerate(valores, start=1):
        if v is None or v == "":
            continue                       # célula vazia = não escreve (planilha esparsa)
        celulas.append(_celula(f"{_col(i)}{num}", v, estilo))
    return f'<row r="{num}">' + "".join(celulas) + "</row>"


_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
    '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
    "</Types>"
)

_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
    "</Relationships>"
)

_WB_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
    '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    "</Relationships>"
)

# Dois estilos: 0 = normal, 1 = negrito (cabeçalho)
_STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    '<fonts count="2">'
    '<font><sz val="11"/><name val="Calibri"/></font>'
    '<font><b/><sz val="11"/><name val="Calibri"/></font>'
    "</fonts>"
    '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
    '<borders count="1"><border/></borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    '<cellXfs count="2">'
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
    "</cellXfs>"
    '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
    "</styleSheet>"
)


def _workbook(nome_aba):
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{escape(nome_aba)}" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )


def _sheet(cabecalhos, linhas, larguras):
    cols_xml = ""
    if larguras:
        partes = "".join(
            f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>'
            for i, w in enumerate(larguras, start=1)
        )
        cols_xml = f"<cols>{partes}</cols>"

    corpo = [_linha_xml(1, cabecalhos, estilo=1)]
    for i, ln in enumerate(linhas, start=2):
        corpo.append(_linha_xml(i, ln))

    n_col = len(cabecalhos)
    n_lin = len(linhas) + 1
    ref = f"A1:{_col(n_col)}{n_lin}"
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        + cols_xml
        + "<sheetData>" + "".join(corpo) + "</sheetData>"
        + f'<autoFilter ref="{ref}"/>'
        + "</worksheet>"
    )


def escrever(caminho, cabecalhos, linhas, larguras=None, nome_aba="Planilha"):
    """Grava um .xlsx em `caminho`.

    - cabecalhos: lista de textos (linha 1, em negrito)
    - linhas: lista de listas (texto ou número por célula)
    - larguras: lista opcional de larguras de coluna (em "caracteres")
    - nome_aba: nome da guia
    Retorna a quantidade de linhas de dados escritas."""
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("xl/workbook.xml", _workbook(nome_aba))
        z.writestr("xl/_rels/workbook.xml.rels", _WB_RELS)
        z.writestr("xl/styles.xml", _STYLES)
        z.writestr("xl/worksheets/sheet1.xml", _sheet(cabecalhos, linhas, larguras))
    return len(linhas)
