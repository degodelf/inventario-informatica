"""
Converte um PNG em .ico embrulhando o PNG dentro do formato ICO — SEM
bibliotecas externas (o Windows Vista+ aceita ICO com PNG embutido).

Uso:  python png_para_ico.py logo_jq.png logo_jq.ico
"""

import struct
import sys


def png_para_ico(png_path, ico_path):
    with open(png_path, "rb") as f:
        png = f.read()
    # dimensões do PNG ficam no bloco IHDR (bytes 16..24)
    largura, altura = struct.unpack(">II", png[16:24])
    bw = largura if largura < 256 else 0     # 256 é gravado como 0 no ICO
    bh = altura if altura < 256 else 0
    header = struct.pack("<HHH", 0, 1, 1)               # reservado, tipo=ícone, qtd=1
    entry = struct.pack("<BBBBHHII", bw, bh, 0, 0, 1, 32, len(png), 6 + 16)
    with open(ico_path, "wb") as f:
        f.write(header + entry + png)


if __name__ == "__main__":
    origem = sys.argv[1] if len(sys.argv) > 1 else "logo_jq.png"
    destino = sys.argv[2] if len(sys.argv) > 2 else "logo_jq.ico"
    png_para_ico(origem, destino)
    print(f"Ícone gerado: {destino}")
