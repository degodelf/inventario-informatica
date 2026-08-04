"""
Testa a LÓGICA de sessão do app (sem a tela): criar banco normal, ativar
criptografia, fechar, reabrir com senha, alterar, reabrir de novo.
Replica exatamente os passos de app._abrir_sessao_banco / _persistir /
_ativar_cripto usando os mesmos módulos.
"""
import os
import sqlite3
import tempfile

import db
import cripto

DB_PATH = os.path.join(tempfile.gettempdir(), "sessao_teste.db")
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)


def abrir_sessao(senha_para_cifrado=None):
    """Versão sem-tela de _abrir_sessao_banco. Retorna (conn, cifrado)."""
    dados = b""
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f:
            dados = f.read()
    if dados and cripto.esta_criptografado(dados):
        blob = cripto.descriptografar(dados, senha_para_cifrado)  # levanta se senha errada
        conn = sqlite3.connect(":memory:")
        conn.deserialize(blob)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        db.criar_tabelas(conn)
        return conn, True
    conn = db.conectar(DB_PATH)
    db.criar_tabelas(conn)
    return conn, False


def persistir(conn, cifrado, senha):
    if cifrado:
        with open(DB_PATH + ".tmp", "wb") as f:
            f.write(cripto.criptografar(conn.serialize(), senha))
        os.replace(DB_PATH + ".tmp", DB_PATH)


SENHA = "banco-2026"

# 1) Primeiro uso: banco normal, cadastra 1 PC
conn, cifrado = abrir_sessao()
assert cifrado is False
db.adicionar_dispositivo(conn, {"categoria": "Computador (PC)", "marca": "Dell",
                                "status": "Em uso", "responsavel": "Ana"})
assert db.estatisticas(conn)["total"] == 1

# 2) Ativa criptografia (serializa, cifra, grava por cima do plaintext)
blob = conn.serialize()
conn.close()
conn_mem = sqlite3.connect(":memory:"); conn_mem.deserialize(blob)
conn_mem.row_factory = sqlite3.Row
with open(DB_PATH, "wb") as f:
    f.write(cripto.criptografar(conn_mem.serialize(), SENHA))
conn_mem.close()
print("Ativou criptografia e gravou o arquivo cifrado ✅")

# 3) Fecha e reabre: agora o arquivo é cifrado, precisa da senha
with open(DB_PATH, "rb") as f:
    assert cripto.esta_criptografado(f.read()), "arquivo deveria estar cifrado"

conn, cifrado = abrir_sessao(SENHA)
assert cifrado is True
assert db.estatisticas(conn)["total"] == 1, "o PC deveria ter sobrevivido"
print("Reabriu com a senha e os dados estão lá ✅")

# 4) Adiciona um Celular e persiste cifrado
db.adicionar_dispositivo(conn, {"categoria": "Celular", "marca": "Motorola",
                                "status": "Em uso", "responsavel": "João"})
persistir(conn, cifrado, SENHA)
conn.close()

# 5) Reabre de novo: devem existir 2 itens
conn, cifrado = abrir_sessao(SENHA)
assert db.estatisticas(conn)["total"] == 2, "deveriam existir 2 dispositivos"
conn.close()
print("Alteração persistida cifrada e recuperada ✅")

# 6) Senha errada é barrada
try:
    abrir_sessao("senha-errada")
    raise AssertionError("deveria ter barrado a senha errada")
except ValueError:
    pass
print("Senha errada barrada ao abrir ✅")

print("\nSESSÃO COMPLETA (criar > cifrar > reabrir > alterar > reabrir) OK ✅")
