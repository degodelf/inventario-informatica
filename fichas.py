"""
Catálogo de fichas técnicas por MODELO — SEM bibliotecas externas.

Ideia: a detecção por cabo (MTP) só traz marca + modelo + nº de série. Este
catálogo guarda a "ficha técnica" de modelos conhecidos (tela, processador,
RAM, armazenamento, bateria, câmeras, sistema) para o programa PREENCHER
sozinho o campo Especificações a partir do modelo — sem digitar.

É uma base de conhecimento (curada à mão). Modelos não cadastrados aqui
simplesmente não são preenchidos — aí é só pedir para incluir o modelo.

Observação: para tablets/celulares há variações de RAM/armazenamento por SKU;
as fichas trazem a configuração típica. O nº de série/identificador real vem
do próprio aparelho (USB); a ficha é do MODELO.
"""

import re
import unicodedata


def _norm(s):
    """minúsculas, sem acento, só letras/números separados por espaço."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = s.lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


# Cada entrada: marca (token), modelo (tokens que PRECISAM aparecer) e a ficha.
# Ordem: do MAIS específico para o mais genérico (o primeiro que casar vence).
CATALOGO = [
    # ---- Samsung Galaxy Tab ----
    {"marca": "samsung", "modelo": "tab a7 lite", "ficha":
        "Aparelho: Samsung Galaxy Tab A7 Lite (SM-T220 Wi-Fi / SM-T225 LTE)\n"
        "Tela: 8,7\" TFT LCD, 1340x800\n"
        "Processador: MediaTek Helio P22T (octa-core)\n"
        "Memoria RAM: 3 GB\n"
        "Armazenamento: 32 GB (microSD ate 1 TB)\n"
        "Bateria: 5.100 mAh\n"
        "Cameras: 8 MP (traseira) / 2 MP (frontal)\n"
        "Sistema: Android 11"},
    {"marca": "samsung", "modelo": "tab a7", "ficha":
        "Aparelho: Samsung Galaxy Tab A7 10.4 (SM-T500 Wi-Fi / SM-T505 LTE)\n"
        "Tela: 10,4\" TFT LCD, 2000x1200\n"
        "Processador: Qualcomm Snapdragon 662 (octa-core)\n"
        "Memoria RAM: 3 GB\n"
        "Armazenamento: 32 ou 64 GB (microSD)\n"
        "Bateria: 7.040 mAh\n"
        "Cameras: 8 MP (traseira) / 5 MP (frontal)\n"
        "Sistema: Android 10"},
    {"marca": "samsung", "modelo": "tab a8", "ficha":
        "Aparelho: Samsung Galaxy Tab A8 10.5 (SM-X200 Wi-Fi / SM-X205 LTE)\n"
        "Tela: 10,5\" TFT LCD, 1920x1200 (WUXGA)\n"
        "Processador: Unisoc Tiger T618 (octa-core)\n"
        "Memoria RAM: 3 ou 4 GB\n"
        "Armazenamento: 32/64/128 GB (microSD)\n"
        "Bateria: 7.040 mAh\n"
        "Cameras: 8 MP (traseira) / 5 MP (frontal)\n"
        "Sistema: Android 11 (One UI 3.1)"},
    {"marca": "samsung", "modelo": "tab e", "ficha":
        "Aparelho: Samsung Galaxy Tab E 9.6 (SM-T560 Wi-Fi / SM-T561 3G)\n"
        "Tela: 9,6\" TFT LCD, 1280x800\n"
        "Processador: quad-core 1.3 GHz\n"
        "Memoria RAM: 1,5 GB\n"
        "Armazenamento: 8 GB (microSD)\n"
        "Bateria: 5.000 mAh\n"
        "Cameras: 5 MP (traseira) / 2 MP (frontal)\n"
        "Sistema: Android 4.4 (atualizavel ate 6.0)"},

    # ---- Multilaser (muitas variacoes de SKU; config tipica) ----
    {"marca": "multilaser", "modelo": "m10", "ficha":
        "Aparelho: Multilaser M10 (linha 10,1\")\n"
        "Tela: 10,1\" IPS, 1280x800\n"
        "Processador: quad-core ARM Cortex-A7\n"
        "Memoria RAM: 2 GB (ha versoes de 1 GB)\n"
        "Armazenamento: 32 GB (microSD)\n"
        "Conectividade: Wi-Fi (+ 3G/4G em alguns modelos)\n"
        "Sistema: Android (Go/normal, conforme a versao)"},
    {"marca": "multilaser", "modelo": "m7", "ficha":
        "Aparelho: Multilaser M7 (linha 7\")\n"
        "Tela: 7\" IPS, 1024x600\n"
        "Processador: quad-core ARM Cortex-A7\n"
        "Memoria RAM: 1 GB (ha versoes de 2 GB)\n"
        "Armazenamento: 16 GB (microSD)\n"
        "Conectividade: Wi-Fi (+ 3G em alguns modelos)\n"
        "Sistema: Android Go"},

    # ---- Positivo ----
    {"marca": "positivo", "modelo": "twist tab", "ficha":
        "Aparelho: Positivo Twist Tab (T770/T780)\n"
        "Tela: 7\" IPS, 1024x600\n"
        "Processador: quad-core 1.5 GHz\n"
        "Memoria RAM: 1 GB (T770) / 2 GB (T780)\n"
        "Armazenamento: 32 GB (microSD)\n"
        "Bateria: 3.000 mAh\n"
        "Sistema: Android 8.1 (Go)"},

    # ---- Lenovo ----
    {"marca": "lenovo", "modelo": "tab m10", "ficha":
        "Aparelho: Lenovo Tab M10 (TB-X505/X605/X306)\n"
        "Tela: 10,1\" IPS, 1280x800 (HD) ou 1920x1200 (FHD)\n"
        "Processador: Qualcomm Snapdragon (429/450) / MediaTek Helio P22T\n"
        "Memoria RAM: 2 a 4 GB\n"
        "Armazenamento: 32 ou 64 GB (microSD)\n"
        "Bateria: ~4.850 mAh\n"
        "Sistema: Android 9/10/11 (conforme a geracao)"},
]


def _tem_token(texto, token):
    """True se `token` aparece em `texto` respeitando limite de palavra, mas
    permitindo sufixo de LETRA (ex.: 'm10' casa 'm10a', mas 'a7' NÃO casa 'a70').
    Regra: não pode ter alfanumérico antes, nem DÍGITO logo depois."""
    padrao = r"(?<![a-z0-9])" + re.escape(token) + r"(?![0-9])"
    return re.search(padrao, texto) is not None


def buscar(marca, modelo):
    """Devolve a ficha técnica do modelo, ou None se não estiver no catálogo."""
    m = _norm(marca)
    mod = _norm(modelo)
    if not mod and not m:
        return None
    texto = (m + " " + mod).strip()
    for item in CATALOGO:
        if item["marca"] and item["marca"] not in texto:
            continue
        tokens = _norm(item["modelo"]).split()
        if tokens and all(_tem_token(texto, t) for t in tokens):
            return item["ficha"]
    return None
