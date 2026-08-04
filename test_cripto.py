"""Testa o cofre criptográfico e o salvar/carregar do banco em memória."""
import sqlite3
import cripto
import db

# ---- 1) Round-trip: cifrar e decifrar volta ao original
for tamanho in (0, 1, 31, 32, 33, 1000, 65537):   # inclui limites de bloco (32B)
    original = bytes(range(256)) * (tamanho // 256) + bytes(range(tamanho % 256))
    cifrado = cripto.criptografar(original, "minha-senha-forte")
    assert cripto.esta_criptografado(cifrado), "deveria ter a assinatura MAGIC"
    assert cifrado != original or tamanho == 0, "não deveria ficar igual ao original"
    volta = cripto.descriptografar(cifrado, "minha-senha-forte")
    assert volta == original, f"round-trip falhou no tamanho {tamanho}"
print("Cripto: round-trip OK em vários tamanhos ✅")

# ---- 2) Senha errada é rejeitada
cifrado = cripto.criptografar(b"dados secretos", "senha-certa")
try:
    cripto.descriptografar(cifrado, "senha-errada")
    raise AssertionError("deveria ter rejeitado a senha errada")
except ValueError:
    pass
print("Cripto: senha errada rejeitada ✅")

# ---- 3) Adulteração é detectada (mexer em 1 byte do ciphertext)
adulterado = bytearray(cifrado)
adulterado[-1] ^= 0x01
try:
    cripto.descriptografar(bytes(adulterado), "senha-certa")
    raise AssertionError("deveria ter detectado adulteração")
except ValueError:
    pass
print("Cripto: adulteração detectada ✅")

# ---- 4) Dois arquivos cifrados do MESMO dado são diferentes (salt/nonce aleatórios)
a = cripto.criptografar(b"igual", "s")
b = cripto.criptografar(b"igual", "s")
assert a != b, "salt/nonce aleatórios deveriam gerar saídas diferentes"
print("Cripto: saídas não determinísticas (salt/nonce) ✅")

# ---- 5) Banco em memória: gravar dados, serializar, recarregar
conn = sqlite3.connect(":memory:")
db.criar_tabelas(conn)
db.adicionar_dispositivo(conn, {"categoria": "Celular", "marca": "Motorola",
                                "status": "Em uso", "responsavel": "Fulano"})
blob = conn.serialize()                    # bytes do banco (Python 3.11+)
cifrado_db = cripto.criptografar(blob, "senha-do-banco")

# simula abrir de novo: decifrar e carregar
blob2 = cripto.descriptografar(cifrado_db, "senha-do-banco")
conn2 = sqlite3.connect(":memory:")
conn2.deserialize(blob2)
conn2.row_factory = sqlite3.Row
n = conn2.execute("SELECT COUNT(*) FROM dispositivos").fetchone()[0]
assert n == 1, "o dispositivo deveria ter sobrevivido ao ciclo cifrar/decifrar"
print("Banco em memória: serialize + cripto + deserialize OK ✅")

print("\nTODOS OS TESTES DE CRIPTOGRAFIA PASSARAM ✅")
