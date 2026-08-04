"""
Geração de etiquetas com código de barras — SEM bibliotecas externas.

Usa o padrão CODE 39 (lido por qualquer leitor USB comum), desenhado à mão
como SVG dentro de uma página HTML pronta para imprimir (abre no navegador,
Ctrl+P). Cada etiqueta mostra o código de barras + o número por extenso, então
funciona mesmo se algum leitor tiver dificuldade.

Uso típico: gerar etiquetas para os itens que NÃO têm patrimônio de fábrica
(teclado, mouse, cabos). O código usado é o patrimônio; se não houver, usa
"ID" + o número interno do item.
"""

import os
import tempfile
import webbrowser
from datetime import datetime

# Tabela CODE 39: cada caractere = 9 elementos (barra,espaço,barra,... ),
# 'n' = estreito, 'w' = largo. Exatamente 3 elementos largos em cada (autoconfere).
CODE39 = {
    "0": "nnnwwnwnn", "1": "wnnwnnnnw", "2": "nnwwnnnnw", "3": "wnwwnnnnn",
    "4": "nnnwwnnnw", "5": "wnnwwnnnn", "6": "nnwwwnnnn", "7": "nnnwnnwnw",
    "8": "wnnwnnwnn", "9": "nnwwnnwnn", "A": "wnnnnwnnw", "B": "nnwnnwnnw",
    "C": "wnwnnwnnn", "D": "nnnnwwnnw", "E": "wnnnwwnnn", "F": "nnwnwwnnn",
    "G": "nnnnnwwnw", "H": "wnnnnwwnn", "I": "nnwnnwwnn", "J": "nnnnwwwnn",
    "K": "wnnnnnnww", "L": "nnwnnnnww", "M": "wnwnnnnwn", "N": "nnnnwnnww",
    "O": "wnnnwnnwn", "P": "nnwnwnnwn", "Q": "nnnnnnwww", "R": "wnnnnnwwn",
    "S": "nnwnnnwwn", "T": "nnnnwnwwn", "U": "wwnnnnnnw", "V": "nwwnnnnnw",
    "W": "wwwnnnnnn", "X": "nwnnwnnnw", "Y": "wwnnwnnnn", "Z": "nwwnwnnnn",
    "-": "nwnnnnwnw", ".": "wwnnnnwnn", " ": "nwwnnnwnn", "$": "nwnwnwnnn",
    "/": "nwnwnnnwn", "+": "nwnnnwnwn", "%": "nnnwnwnwn", "*": "nwnnwnwnn",
}

_VALIDOS = set(CODE39.keys()) - {"*"}


def limpar_codigo(texto):
    """Deixa o texto compatível com CODE 39 (maiúsculas; troca inválidos por '-')."""
    texto = (texto or "").upper()
    return "".join(c if c in _VALIDOS else "-" for c in texto) or "SEM-CODIGO"


def svg_code39(dados, unidade=2, altura=48):
    """Desenha o código de barras CODE 39 como SVG.

    unidade = largura (px) da barra estreita; largura = 3x. altura em px.
    Retorna (svg_str, largura_total_px).
    """
    dados = limpar_codigo(dados)
    sequencia = "*" + dados + "*"          # '*' delimita início e fim
    largo = unidade * 3
    quiet = unidade * 10                    # zona de silêncio nas pontas

    barras = []
    x = quiet
    for ch in sequencia:
        padrao = CODE39[ch]
        for i, elem in enumerate(padrao):
            largura = largo if elem == "w" else unidade
            if i % 2 == 0:                  # posição par = barra preta
                barras.append(f'<rect x="{x}" y="0" width="{largura}" height="{altura}"/>')
            x += largura
        x += unidade                        # espaço estreito entre caracteres

    total = x + quiet
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="{altura}" '
        f'viewBox="0 0 {total} {altura}" shape-rendering="crispEdges">'
        f'<rect x="0" y="0" width="{total}" height="{altura}" fill="white"/>'
        f'<g fill="black">{"".join(barras)}</g></svg>'
    )
    return svg, total


def _escape(txt):
    return (str(txt or "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def gerar_html_etiquetas(dispositivos):
    """Monta o HTML de uma folha de etiquetas para os dispositivos informados.

    Cada `dispositivo` é um sqlite3.Row (ou dict) com: id, patrimonio,
    categoria, marca, modelo.
    """
    cartoes = []
    for d in dispositivos:
        codigo = d["patrimonio"] if d["patrimonio"] else f"ID{d['id']}"
        svg, _ = svg_code39(codigo)
        titulo = _escape(d["categoria"])
        subtitulo = _escape(f"{d['marca'] or ''} {d['modelo'] or ''}".strip())
        cartoes.append(
            f'<div class="etiqueta">'
            f'<div class="titulo">{titulo}</div>'
            f'<div class="sub">{subtitulo}</div>'
            f'<div class="barra">{svg}</div>'
            f'<div class="codigo">{_escape(limpar_codigo(codigo))}</div>'
            f'</div>'
        )

    gerado = datetime.now().strftime("%d/%m/%Y %H:%M")
    return f"""<!DOCTYPE html>
<html lang="pt-br"><head><meta charset="utf-8">
<title>Etiquetas — Inventário</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 10px; }}
  .cabecalho {{ margin-bottom: 8px; }}
  .cabecalho button {{ padding: 6px 14px; font-size: 14px; cursor: pointer; }}
  .folha {{ display: grid; grid-template-columns: repeat(3, 6cm); gap: 4mm; }}
  .etiqueta {{
    width: 6cm; height: 3cm; border: 1px dashed #999; padding: 3px 6px;
    box-sizing: border-box; text-align: center; overflow: hidden;
    display: flex; flex-direction: column; justify-content: center;
  }}
  .titulo {{ font-weight: bold; font-size: 12px; }}
  .sub {{ font-size: 10px; color: #333; margin-bottom: 2px;
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .barra svg {{ max-width: 100%; height: 40px; }}
  .codigo {{ font-size: 11px; letter-spacing: 1px; margin-top: 1px; }}
  @media print {{ .cabecalho {{ display: none; }} .etiqueta {{ border-color: #ccc; }} }}
</style></head>
<body>
  <div class="cabecalho">
    Gerado em {gerado} — {len(cartoes)} etiqueta(s).
    <button onclick="window.print()">🖨️ Imprimir</button>
    <span style="color:#666"> (dica: teste passar o leitor em UMA etiqueta antes de imprimir várias)</span>
  </div>
  <div class="folha">{"".join(cartoes)}</div>
</body></html>"""


def gerar_e_abrir(dispositivos):
    """Gera a folha de etiquetas e abre no navegador padrão. Retorna o caminho."""
    html = gerar_html_etiquetas(dispositivos)
    caminho = os.path.join(tempfile.gettempdir(),
                           f"etiquetas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(html)
    webbrowser.open("file://" + os.path.abspath(caminho))
    return caminho
