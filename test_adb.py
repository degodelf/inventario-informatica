"""Testa o parser do getprop e a extração de info (sem precisar de aparelho)."""
import adb

# Amostra real da saída de 'adb shell getprop' (tablet Samsung)
amostra = """
[ro.product.manufacturer]: [samsung]
[ro.product.model]: [SM-T500]
[ro.build.version.release]: [11]
[ro.serialno]: [R9WR30ABCDE]
[persist.sys.timezone]: [America/Sao_Paulo]
"""
props = adb.parse_props(amostra)
assert props["ro.product.model"] == "SM-T500"
assert props["ro.serialno"] == "R9WR30ABCDE"

info = adb.extrair_info(props, serial="R9WR30ABCDE")
assert info["marca"] == "Samsung"          # manufacturer .title()
assert info["modelo"] == "SM-T500"
assert info["numero_serie"] == "R9WR30ABCDE"
assert info["versao_android"] == "11"
print("ADB: getprop -> cadastro OK ✅")

# Se não vier ro.serialno, usa o serial do próprio adb
info2 = adb.extrair_info({"ro.product.model": "Moto G"}, serial="ZY223XY")
assert info2["numero_serie"] == "ZY223XY"
print("ADB: fallback de nº de série OK ✅")

print("\nTESTE DO PARSER ADB PASSOU ✅")
