"""
Senha de acesso ao programa. Puro Python (hashlib), sem bibliotecas externas.

A senha NÃO é guardada em texto: guardamos só um "hash" salgado (PBKDF2).
Assim, mesmo abrindo o inventario.db, ninguém lê a senha.
"""

import hashlib
import hmac
import os

import db

_ITERACOES = 200_000


def _hash(senha, salt):
    return hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, _ITERACOES).hex()


def tem_senha(conn):
    """True se já existe uma senha cadastrada."""
    return db.get_config(conn, "senha_hash") is not None


def definir_senha(conn, senha):
    """Cria ou troca a senha."""
    salt = os.urandom(16)
    db.set_config(conn, "senha_salt", salt.hex())
    db.set_config(conn, "senha_hash", _hash(senha, salt))


def verificar_senha(conn, senha):
    """True se a senha bate com a cadastrada."""
    salt_hex = db.get_config(conn, "senha_salt")
    esperado = db.get_config(conn, "senha_hash")
    if not salt_hex or not esperado:
        return False
    calculado = _hash(senha, bytes.fromhex(salt_hex))
    # comparação em tempo constante (evita medir tempo pra adivinhar)
    return hmac.compare_digest(calculado, esperado)
