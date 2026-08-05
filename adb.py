"""
Conversa com aparelhos Android via ADB (USB). O adb.exe fica embutido no
programa (pasta 'adb'). Só funciona no Windows.

Pré-requisitos no aparelho: "Opções do desenvolvedor" > "Depuração USB"
ligada, e o computador autorizado (aparece um aviso na tela do aparelho na
primeira conexão).
"""

import os
import re
import subprocess
import sys

_NOWINDOW = 0x08000000  # CREATE_NO_WINDOW: evita piscar janela de console
_RE_PROP = re.compile(r"^\[(.+?)\]:\s*\[(.*)\]$")


def _base_recursos():
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def caminho_adb():
    return os.path.join(_base_recursos(), "adb", "adb.exe")


def disponivel():
    """True se o adb.exe está presente (embutido)."""
    return os.path.exists(caminho_adb())


def _run(args, timeout=20):
    """Roda o adb com os argumentos. Retorna (codigo, saida_texto)."""
    try:
        r = subprocess.run(
            [caminho_adb()] + args,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout,
            creationflags=_NOWINDOW if sys.platform.startswith("win") else 0,
        )
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return -1, "Tempo esgotado ao falar com o ADB."
    except Exception as e:  # noqa: BLE001
        return -1, str(e)


def listar_dispositivos():
    """Lista os aparelhos conectados. Retorna lista de dicts {serial, estado}.
    estado: 'device' = pronto; 'unauthorized' = falta autorizar na tela;
    'offline' = com problema."""
    _cod, saida = _run(["devices"])
    aparelhos = []
    for linha in saida.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("List of devices"):
            continue
        partes = linha.split("\t")
        if len(partes) == 2:
            aparelhos.append({"serial": partes[0].strip(), "estado": partes[1].strip()})
    return aparelhos


def _todas_props(serial):
    """Lê todas as propriedades do aparelho (getprop) numa chamada só."""
    _cod, saida = _run(["-s", serial, "shell", "getprop"])
    props = {}
    for linha in saida.splitlines():
        m = _RE_PROP.match(linha.strip())
        if m:
            props[m.group(1)] = m.group(2)
    return props


def parse_props(texto):
    """Transforma a saída de 'getprop' em dict (exposto para teste)."""
    props = {}
    for linha in texto.splitlines():
        m = _RE_PROP.match(linha.strip())
        if m:
            props[m.group(1)] = m.group(2)
    return props


def extrair_info(props, serial=""):
    """A partir das propriedades, monta o dicionário de cadastro."""
    fabricante = props.get("ro.product.manufacturer", "")
    return {
        "marca": fabricante.title() if fabricante else "",
        "modelo": props.get("ro.product.model", ""),
        "numero_serie": props.get("ro.serialno", "") or serial,
        "versao_android": props.get("ro.build.version.release", ""),
    }


def info_dispositivo(serial):
    """Lê as informações de um aparelho já autorizado. Retorna dict com
    marca, modelo, numero_serie, versao_android."""
    return extrair_info(_todas_props(serial), serial)


# --- Gerenciamento de aplicativos ---------------------------------------------

def listar_apps(serial, incluir_sistema=False):
    """Lista os pacotes instalados. Por padrão, só os de TERCEIROS (-3),
    que são os que fazem sentido desinstalar. Retorna lista ordenada."""
    args = ["-s", serial, "shell", "pm", "list", "packages"]
    if not incluir_sistema:
        args.append("-3")
    _cod, saida = _run(args, timeout=30)
    pacotes = []
    for linha in saida.splitlines():
        linha = linha.strip()
        if linha.startswith("package:"):
            pacotes.append(linha[len("package:"):].strip())
    return sorted(pacotes)


def desinstalar_app(serial, pacote):
    """Desinstala um app do aparelho. Retorna (ok, mensagem)."""
    _cod, saida = _run(["-s", serial, "uninstall", pacote], timeout=60)
    return ("Success" in saida), saida.strip()


def parar_app(serial, pacote):
    """Força a parada de um app (temporário; pode reiniciar). Retorna (ok, msg)."""
    cod, saida = _run(["-s", serial, "shell", "am", "force-stop", pacote], timeout=20)
    return (cod == 0), (saida.strip() or "Parado.")


def limpar_dados_app(serial, pacote):
    """Reseta um app ao estado 'novo' (pm clear): apaga dados, cache, abas,
    histórico, logins do app. Ex: fecha todas as abas do Chrome. (ok, msg)."""
    _cod, saida = _run(["-s", serial, "shell", "pm", "clear", pacote], timeout=30)
    return ("Success" in saida), saida.strip()
