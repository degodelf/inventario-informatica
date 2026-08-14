"""
Lê as ESPECIFICAÇÕES (ficha técnica) do COMPUTADOR onde o programa roda —
SEM bibliotecas externas. Usa o PowerShell/CIM do próprio Windows.

Serve para o botão "Ler specs" do cadastro: em vez de digitar processador,
memória, disco etc., o programa lê tudo do Windows e preenche.

Só Windows. Em outros sistemas, `ler_computador()` devolve um aviso curto.
As specs do Android (celular/tablet) ficam no módulo `adb.py`.
"""

import json
import subprocess
import sys

_NOWINDOW = 0x08000000  # CREATE_NO_WINDOW: não pisca janela de console


def _powershell(comando, timeout=25):
    """Roda um comando PowerShell e devolve (codigo, saida_texto)."""
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


# Um único comando pega tudo de uma vez e devolve JSON (rápido e fácil de ler).
_CMD = r"""
$cs   = Get-CimInstance Win32_ComputerSystem
$os   = Get-CimInstance Win32_OperatingSystem
$cpu  = Get-CimInstance Win32_Processor | Select-Object -First 1
$bios = Get-CimInstance Win32_BIOS
$gpu  = Get-CimInstance Win32_VideoController | Where-Object { $_.Name } | Select-Object -First 1
$discos = Get-CimInstance Win32_DiskDrive | ForEach-Object {
    ('{0} GB {1}' -f [math]::Round($_.Size/1GB), $_.Model)
}
[pscustomobject]@{
    Fabricante = $cs.Manufacturer
    Modelo     = $cs.Model
    Serie      = $bios.SerialNumber
    CPU        = $cpu.Name
    Nucleos    = $cpu.NumberOfCores
    Logicos    = $cpu.NumberOfLogicalProcessors
    RAM_GB     = [math]::Round($cs.TotalPhysicalMemory/1GB, 1)
    Disco      = ($discos -join ' | ')
    GPU        = $gpu.Name
    SO         = $os.Caption
    Versao     = $os.Version
    Maquina    = $env:COMPUTERNAME
} | ConvertTo-Json -Compress
"""


def _limpa(v):
    v = (str(v) if v is not None else "").strip()
    # BIOS de PC montado às vezes traz lixo genérico no nº de série
    if v.lower() in ("", "none", "default string", "to be filled by o.e.m.",
                     "system serial number", "0", "not specified"):
        return ""
    return v


def ler_computador():
    """Lê as specs da máquina local. Retorna um dict:
       {ok, texto, marca, modelo, numero_serie, erro}

    - texto: ficha técnica formatada (vai para o campo Especificações)
    - marca/modelo/numero_serie: para preencher esses campos se estiverem vazios
    """
    if not sys.platform.startswith("win"):
        return {"ok": False, "erro": "Leitura automática só está disponível no Windows.",
                "texto": "", "marca": "", "modelo": "", "numero_serie": ""}

    cod, saida = _powershell(_CMD)
    saida = saida.strip()
    if cod != 0 or not saida:
        return {"ok": False, "erro": "Não consegui ler as informações do Windows.",
                "texto": "", "marca": "", "modelo": "", "numero_serie": ""}
    try:
        d = json.loads(saida)
    except Exception:  # noqa: BLE001
        return {"ok": False, "erro": "Resposta do Windows em formato inesperado.",
                "texto": "", "marca": "", "modelo": "", "numero_serie": ""}

    fabricante = _limpa(d.get("Fabricante"))
    modelo = _limpa(d.get("Modelo"))
    serie = _limpa(d.get("Serie"))
    cpu = _limpa(d.get("CPU"))
    ram = d.get("RAM_GB")
    disco = _limpa(d.get("Disco"))
    gpu = _limpa(d.get("GPU"))
    so = _limpa(d.get("SO"))
    versao = _limpa(d.get("Versao"))
    nucleos = d.get("Nucleos")
    logicos = d.get("Logicos")
    maquina = _limpa(d.get("Maquina"))

    linhas = []
    if cpu:
        proc = f"Processador: {cpu}"
        if nucleos:
            proc += f" ({nucleos} núcleos"
            proc += f" / {logicos} threads)" if logicos else ")"
        linhas.append(proc)
    if ram:
        linhas.append(f"Memória RAM: {ram} GB")
    if disco:
        linhas.append(f"Armazenamento: {disco}")
    if gpu:
        linhas.append(f"Vídeo: {gpu}")
    if so:
        linhas.append(f"Sistema: {so}" + (f" (build {versao})" if versao else ""))
    if serie:
        linhas.append(f"Nº de série (BIOS): {serie}")
    if maquina:
        linhas.append(f"Nome na rede: {maquina}")

    return {
        "ok": True,
        "erro": "",
        "texto": "\n".join(linhas),
        "marca": fabricante,
        "modelo": modelo,
        "numero_serie": serie,
    }
