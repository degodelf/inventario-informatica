"""
Lê informações de um aparelho conectado por USB SEM depuração (via Windows).
Quando o tablet está em modo MTP (Transferência de arquivos) ou câmera, o
Windows o enxerga como "Dispositivo portátil" — e expõe o NOME (modelo) e,
no ID do dispositivo, geralmente o Nº DE SÉRIE. É a mesma informação que
aparece em "Propriedades" do aparelho.

Usa o PowerShell (só Windows). Não gerencia nada — só lê, para o cadastro.
"""

import json
import subprocess
import sys

_NOWINDOW = 0x08000000  # CREATE_NO_WINDOW: não pisca janela de console


def _powershell(comando, timeout=25):
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", comando],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout,
            creationflags=_NOWINDOW if sys.platform.startswith("win") else 0,
        )
        return r.returncode, (r.stdout or "")
    except Exception as e:  # noqa: BLE001
        return -1, str(e)


def serie_do_id(instance_id):
    """O nº de série costuma ser o último trecho do ID do dispositivo
    (depois da última barra). Descarta se parecer um ID composto (com '&')."""
    if not instance_id:
        return ""
    ultimo = instance_id.split("\\")[-1].strip()
    if "&" in ultimo or not ultimo:
        return ""
    return ultimo


def listar_portateis():
    """Lista aparelhos portáteis (MTP/câmera) plugados agora. Só Windows.
    Retorna lista de dicts: {nome, serie, id}."""
    if not sys.platform.startswith("win"):
        return []
    comando = (
        "Get-PnpDevice -PresentOnly | "
        "Where-Object { $_.Class -eq 'WPD' -or $_.Class -eq 'Image' } | "
        "Select-Object FriendlyName, InstanceId | ConvertTo-Json -Compress"
    )
    cod, saida = _powershell(comando)
    saida = saida.strip()
    if cod != 0 or not saida:
        return []
    try:
        dados = json.loads(saida)
    except Exception:  # noqa: BLE001
        return []
    if isinstance(dados, dict):          # 1 resultado vem como objeto, não lista
        dados = [dados]

    aparelhos = []
    for d in dados:
        nome = (d.get("FriendlyName") or "").strip()
        inst = d.get("InstanceId") or ""
        # ignora entradas genéricas sem utilidade
        if not nome:
            continue
        aparelhos.append({"nome": nome, "serie": serie_do_id(inst), "id": inst})
    return aparelhos
