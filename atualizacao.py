"""
Verificação de atualização via GitHub Releases — SEM bibliotecas externas.

Como funciona: consulta a API pública do GitHub pela última "release" do seu
repositório e compara com a versão deste programa. Se houver uma mais nova,
o app avisa e abre a página de download.

>>> IMPORTANTE: depois de criar seu repositório no GitHub, preencha abaixo
    GITHUB_USUARIO e GITHUB_REPO com os seus. <<<
"""

import json
import os
import subprocess
import sys
import tempfile
import urllib.request

# Versão ATUAL deste programa. Suba este número a cada nova versão publicada
# (e crie a release no GitHub com a tag igual, ex: v1.1.0).
VERSAO = "1.13.0"

# Dados do GitHub (repositório onde você publica as releases):
GITHUB_USUARIO = "degodelf"
GITHUB_REPO = "inventario-informatica"   # crie o repo com este nome


def esta_configurado():
    """True quando o usuário já preencheu o GITHUB_USUARIO."""
    return GITHUB_USUARIO and GITHUB_USUARIO != "SEU_USUARIO"


def _para_numeros(versao):
    """'v1.2.3' -> (1, 2, 3) para poder comparar corretamente."""
    versao = (versao or "").lstrip("vV").strip()
    numeros = []
    for parte in versao.split("."):
        digitos = "".join(c for c in parte if c.isdigit())
        numeros.append(int(digitos) if digitos else 0)
    return tuple(numeros) if numeros else (0,)


def ha_versao_mais_nova(tag_remota, versao_local=VERSAO):
    """True se a tag da release for maior que a versão local."""
    return _para_numeros(tag_remota) > _para_numeros(versao_local)


def checar_online(timeout=6):
    """Consulta o GitHub. Retorna um dict com:
       tem_nova, versao_nova, pagina, exe_url.
    Pode levantar exceção (sem internet, bloqueado, etc.) — quem chama trata."""
    url = f"https://api.github.com/repos/{GITHUB_USUARIO}/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "inventario-sala-informatica",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        dados = json.load(resp)

    tag = dados.get("tag_name", "")
    pagina = dados.get("html_url", "")
    exe_url = ""
    for asset in dados.get("assets", []):
        if asset.get("name", "").lower().endswith(".exe"):
            exe_url = asset.get("browser_download_url", "")
            break

    return {
        "tem_nova": ha_versao_mais_nova(tag),
        "versao_nova": tag,
        "pagina": pagina,
        "exe_url": exe_url,
    }


def baixar(url, destino, progresso=None, timeout=60):
    """Baixa o arquivo da `url` para `destino`. `progresso(baixado, total)` é
    chamado durante o download (opcional). Só funciona com repositório PÚBLICO
    (release pública não exige login)."""
    req = urllib.request.Request(
        url, headers={"User-Agent": "inventario-sala-informatica"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        baixado = 0
        with open(destino, "wb") as f:
            while True:
                pedaco = resp.read(65536)
                if not pedaco:
                    break
                f.write(pedaco)
                baixado += len(pedaco)
                if progresso:
                    progresso(baixado, total)
    return destino


def _script_troca(exe_novo, exe_atual):
    """Texto do .bat que espera o programa fechar, troca o .exe e reabre."""
    return (
        "@echo off\r\n"
        ":retry\r\n"
        f'move /Y "{exe_novo}" "{exe_atual}" >nul 2>&1\r\n'
        "if errorlevel 1 (\r\n"
        "  ping 127.0.0.1 -n 2 >nul\r\n"   # espera ~1s e tenta de novo
        "  goto retry\r\n"
        ")\r\n"
        f'start "" "{exe_atual}"\r\n'
        'del "%~f0"\r\n'                    # o .bat se apaga no fim
    )


def instalar_e_reiniciar(exe_novo, exe_atual=None):
    """Aplica a atualização: cria um .bat que substitui o .exe atual pelo novo
    (depois que este processo fechar) e reabre o programa. Só faz sentido no
    .exe empacotado (frozen). Quem chama deve fechar o app logo em seguida."""
    if exe_atual is None:
        exe_atual = sys.executable
    caminho_bat = os.path.join(tempfile.gettempdir(), "atualizar_inventario.bat")
    with open(caminho_bat, "w", encoding="ascii", errors="ignore") as f:
        f.write(_script_troca(exe_novo, exe_atual))
    # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP para o .bat sobreviver ao fechamento
    flags = 0x00000008 | 0x00000200
    subprocess.Popen(["cmd", "/c", caminho_bat], creationflags=flags, close_fds=True)
