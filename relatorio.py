"""
Relatório do inventário em HTML — SEM bibliotecas externas.

Abre no navegador já pronto para imprimir. Para virar PDF: Ctrl+P >
"Salvar como PDF". Respeita os filtros que estiverem ativos na tela.
"""

import os
import tempfile
import webbrowser
from datetime import datetime


def _escape(txt):
    return (str(txt if txt is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _fmt_valor(v):
    if v is None or v == "":
        return ""
    try:
        return "R$ " + f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return _escape(v)


def gerar_html_relatorio(dispositivos, filtro_desc=""):
    """Monta o HTML do relatório a partir de uma lista de dispositivos (Rows)."""
    linhas = []
    total_valor = 0.0
    for d in dispositivos:
        if d["valor"]:
            total_valor += float(d["valor"])
        linhas.append(
            "<tr>"
            f"<td>{_escape(d['patrimonio'])}</td>"
            f"<td>{_escape(d['categoria'])}</td>"
            f"<td>{_escape(d['marca'])}</td>"
            f"<td>{_escape(d['modelo'])}</td>"
            f"<td>{_escape(d['numero_serie'])}</td>"
            f"<td>{_escape(d['status'])}</td>"
            f"<td>{_escape(d['local'])}</td>"
            f"<td>{_escape(d['responsavel'])}</td>"
            f"<td style='text-align:right'>{_fmt_valor(d['valor'])}</td>"
            "</tr>"
        )

    gerado = datetime.now().strftime("%d/%m/%Y %H:%M")
    desc = f" — {_escape(filtro_desc)}" if filtro_desc else ""
    return f"""<!DOCTYPE html>
<html lang="pt-br"><head><meta charset="utf-8">
<title>Relatório — Inventário</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 18px; color: #222; }}
  h1 {{ font-size: 18px; margin: 0; }}
  .info {{ color: #555; font-size: 12px; margin: 4px 0 14px; }}
  button {{ padding: 6px 14px; font-size: 14px; cursor: pointer; margin-bottom: 12px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
  th, td {{ border: 1px solid #bbb; padding: 4px 6px; text-align: left; }}
  th {{ background: #f0f0f0; }}
  tr:nth-child(even) td {{ background: #fafafa; }}
  tfoot td {{ font-weight: bold; background: #f0f0f0; }}
  @media print {{ button {{ display: none; }} }}
</style></head>
<body>
  <h1>Inventário da Sala de Informática</h1>
  <div class="info">Gerado em {gerado}{desc} — {len(linhas)} dispositivo(s).</div>
  <button onclick="window.print()">🖨️ Imprimir / Salvar como PDF</button>
  <table>
    <thead><tr>
      <th>Patrimônio</th><th>Categoria</th><th>Marca</th><th>Modelo</th>
      <th>Nº Série</th><th>Status</th><th>Local</th><th>Responsável</th>
      <th style="text-align:right">Valor</th>
    </tr></thead>
    <tbody>{"".join(linhas)}</tbody>
    <tfoot><tr>
      <td colspan="8" style="text-align:right">Total estimado</td>
      <td style="text-align:right">{_fmt_valor(total_valor)}</td>
    </tr></tfoot>
  </table>
</body></html>"""


def gerar_e_abrir(dispositivos, filtro_desc=""):
    """Gera o relatório e abre no navegador. Retorna o caminho do arquivo."""
    html = gerar_html_relatorio(dispositivos, filtro_desc)
    caminho = os.path.join(tempfile.gettempdir(),
                           f"relatorio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(html)
    webbrowser.open("file://" + os.path.abspath(caminho))
    return caminho
