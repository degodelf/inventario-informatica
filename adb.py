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
    histórico, logins do app. Ex: fecha todas as abas do Chrome. (ok, msg).
    ATENÇÃO: no Chrome isso TAMBÉM desloga a conta. Para manter a conta, use
    limpar_chrome()."""
    _cod, saida = _run(["-s", serial, "shell", "pm", "clear", pacote], timeout=30)
    return ("Success" in saida), saida.strip()


# --- Chrome: fechar abas + limpar cache/cookies MANTENDO a conta --------------
# Usa o protocolo DevTools (o mesmo do chrome://inspect) via ADB. Não usa
# 'pm clear', então NÃO desloga a conta do Chrome.

def _porta_livre():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    porta = s.getsockname()[1]
    s.close()
    return porta


def _ws_frame(payload: bytes) -> bytes:
    """Monta um frame WebSocket de texto, mascarado (exigido do lado cliente)."""
    import os
    import struct
    quadro = bytearray([0x81])            # FIN=1, opcode=1 (texto)
    n = len(payload)
    if n < 126:
        quadro.append(0x80 | n)
    elif n < 65536:
        quadro.append(0x80 | 126)
        quadro += struct.pack(">H", n)
    else:
        quadro.append(0x80 | 127)
        quadro += struct.pack(">Q", n)
    mask = os.urandom(4)
    quadro += mask
    quadro += bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return bytes(quadro)


def _ws_enviar_comandos(url_ws, comandos, timeout=8):
    """Abre um WebSocket com o DevTools e dispara os comandos (JSON)."""
    import base64
    import json
    import os
    import socket
    from urllib.parse import urlparse

    u = urlparse(url_ws)                   # ws://127.0.0.1:porta/devtools/page/ID
    chave = base64.b64encode(os.urandom(16)).decode()
    handshake = (
        f"GET {u.path} HTTP/1.1\r\n"
        f"Host: {u.hostname}:{u.port}\r\n"
        "Upgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {chave}\r\nSec-WebSocket-Version: 13\r\n\r\n"
    )
    s = socket.create_connection((u.hostname, u.port), timeout=timeout)
    try:
        s.sendall(handshake.encode())
        s.recv(4096)                       # resposta do handshake (101)
        for cmd in comandos:
            s.sendall(_ws_frame(json.dumps(cmd).encode("utf-8")))
        s.settimeout(2)
        try:
            s.recv(4096)                   # dá um tempo pro Chrome processar
        except Exception:  # noqa: BLE001
            pass
    finally:
        s.close()


def limpar_chrome(serial, pacote="com.android.chrome", limpar_dados=True):
    """Fecha todas as abas do Chrome e (opcional) limpa cache/cookies, SEM
    deslogar a conta. Requer o Chrome ABERTO no aparelho. Retorna (ok, msg)."""
    import json
    import urllib.request

    porta = _porta_livre()
    cod, _ = _run(["-s", serial, "forward", f"tcp:{porta}", f"localabstract:{pacote}_devtools_remote"])
    if cod != 0:
        return False, "Não abri o canal de debug do Chrome (ele precisa estar aberto no aparelho)."

    base = f"http://127.0.0.1:{porta}"
    try:
        with urllib.request.urlopen(base + "/json", timeout=10) as r:
            alvos = json.load(r)
        paginas = [a for a in alvos if a.get("type") == "page"]

        # 1) limpar cache/cookies usando uma aba como contexto
        if limpar_dados:
            url_ws = paginas[0].get("webSocketDebuggerUrl") if paginas else None
            if not url_ws:
                try:
                    with urllib.request.urlopen(base + "/json/new", timeout=10) as r:
                        url_ws = json.load(r).get("webSocketDebuggerUrl")
                except Exception:  # noqa: BLE001
                    url_ws = None
            if url_ws:
                _ws_enviar_comandos(url_ws, [
                    {"id": 1, "method": "Network.enable"},
                    {"id": 2, "method": "Network.clearBrowserCache"},
                    {"id": 3, "method": "Network.clearBrowserCookies"},
                ])

        # 2) fechar todas as abas (relista, pode ter aberto uma nova)
        with urllib.request.urlopen(base + "/json", timeout=10) as r:
            alvos = json.load(r)
        fechadas = 0
        for a in alvos:
            if a.get("type") == "page":
                try:
                    urllib.request.urlopen(base + "/json/close/" + a["id"], timeout=5).read()
                    fechadas += 1
                except Exception:  # noqa: BLE001
                    pass
        extra = " + cache/cookies limpos" if limpar_dados else ""
        return True, f"{fechadas} aba(s) fechada(s){extra}."
    except Exception as e:  # noqa: BLE001
        return False, f"Falha no debug do Chrome (ele está aberto?): {e}"
    finally:
        _run(["-s", serial, "forward", "--remove", f"tcp:{porta}"])
