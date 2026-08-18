"""
Gera arquivos .pdf DE VERDADE (abrem em qualquer leitor) — SEM bibliotecas
externas. Um PDF é texto estruturado + uma tabela de referências (xref); aqui
montamos isso na mão, no mesmo espírito do xlsx.py.

Foco: relatórios tabulares. Usa a fonte padrão do PDF **Courier** (largura fixa),
então as colunas alinham sozinhas por contagem de caracteres — sem precisar de
tabelas de métricas de fonte. Faz paginação automática, repete o cabeçalho da
tabela em cada página e numera as páginas.

Orientação paisagem A4 (842 x 595 pt). Texto em WinAnsi (acentos do português).

Uso:
    import pdf
    pdf.gerar("saida.pdf", "Título", "gerado em ...", ["resumo1", "resumo2"],
              "CABEÇALHO DA TABELA (monoespaçado)", ["linha 1", "linha 2", ...])
"""

# Página A4 paisagem, em pontos
LARGURA, ALTURA = 842, 595
MARGEM_ESQ = 40
TOPO = ALTURA - 40
BASE = 34
ENTRELINHA = 11


def _txt_bytes(s):
    """Escapa caracteres especiais de string PDF e codifica em WinAnsi (cp1252)."""
    s = (s or "").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return s.encode("cp1252", "replace")


def _paginar(titulo, info, resumo, cabecalho, linhas):
    """Divide o conteúdo em páginas. Cada página é uma lista de (fonte, tam, texto)."""
    budget = int((TOPO - BASE) / ENTRELINHA)      # nº de linhas que cabem

    preambulo = [("F2", 11, titulo), ("F1", 8, info)]
    for r in resumo:
        preambulo.append(("F1", 8, r))
    preambulo.append(("F1", 8, ""))               # linha em branco
    preambulo.append(("F2", 8, cabecalho))

    dados = [("F1", 8, ln) for ln in linhas]

    paginas = []
    cap1 = max(budget - len(preambulo), 1)
    paginas.append(preambulo + dados[:cap1])
    i = cap1
    while i < len(dados):
        cabec = [("F2", 8, cabecalho)]
        capn = max(budget - len(cabec), 1)
        paginas.append(cabec + dados[i:i + capn])
        i += capn
    return paginas


def _stream_pagina(linhas, num, total):
    buf = bytearray()
    buf += b"BT\n"
    buf += f"{MARGEM_ESQ} {TOPO} Td\n".encode()
    buf += f"{ENTRELINHA} TL\n".encode()
    for fonte, tam, texto in linhas:
        buf += f"/{fonte} {tam} Tf\n".encode()
        buf += b"(" + _txt_bytes(texto) + b") Tj\n"
        buf += b"T*\n"
    buf += b"ET\n"
    # rodapé com o número da página
    buf += b"BT\n"
    buf += f"/F1 7 Tf {MARGEM_ESQ} 18 Td\n".encode()
    buf += b"(" + _txt_bytes(f"Pagina {num} de {total}") + b") Tj\nET\n"
    return bytes(buf)


def gerar(caminho, titulo, info, resumo, cabecalho, linhas):
    """Grava um relatório em PDF. `resumo` é uma lista de linhas de texto;
    `cabecalho` e `linhas` são strings monoespaçadas (já formatadas em colunas)."""
    paginas = _paginar(titulo, info, resumo, cabecalho, linhas)
    n_pag = len(paginas)

    objetos = {}                                  # numero -> corpo (bytes)
    objetos[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objetos[3] = (b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier "
                  b"/Encoding /WinAnsiEncoding >>")
    objetos[4] = (b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier-Bold "
                  b"/Encoding /WinAnsiEncoding >>")

    kids = []
    for k in range(n_pag):
        obj_conteudo = 5 + 2 * k
        obj_pagina = 6 + 2 * k
        kids.append(f"{obj_pagina} 0 R")
        fluxo = _stream_pagina(paginas[k], k + 1, n_pag)
        objetos[obj_conteudo] = (
            b"<< /Length " + str(len(fluxo)).encode() + b" >>\nstream\n"
            + fluxo + b"\nendstream"
        )
        objetos[obj_pagina] = (
            f"<< /Type /Page /Parent 2 0 R /Contents {obj_conteudo} 0 R >>".encode()
        )

    objetos[2] = (
        f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {n_pag} "
        f"/MediaBox [0 0 {LARGURA} {ALTURA}] "
        f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> >>".encode()
    )

    # Monta o arquivo, guardando o offset (em bytes) de cada objeto para o xref
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    maxnum = max(objetos)
    for num in range(1, maxnum + 1):
        offsets[num] = len(out)
        out += f"{num} 0 obj\n".encode()
        out += objetos[num]
        out += b"\nendobj\n"

    pos_xref = len(out)
    out += f"xref\n0 {maxnum + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for num in range(1, maxnum + 1):
        out += f"{offsets[num]:010d} 00000 n \n".encode()
    out += b"trailer\n"
    out += f"<< /Size {maxnum + 1} /Root 1 0 R >>\n".encode()
    out += b"startxref\n"
    out += f"{pos_xref}\n".encode()
    out += b"%%EOF"

    with open(caminho, "wb") as f:
        f.write(out)
    return n_pag
