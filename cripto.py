"""
Criptografia do banco de dados em repouso — SEM bibliotecas externas.

NÃO inventa algoritmo novo: compõe primitivas já testadas da biblioteca padrão
do Python (hashlib/hmac):

  - Chave derivada da senha com PBKDF2-HMAC-SHA256 (salt aleatório, 200k iter.)
  - Cifra de fluxo: HMAC-SHA256 em modo contador gera o "keystream"
  - Integridade/autenticação: encrypt-then-MAC com HMAC-SHA256 (chave separada)
  - Salt e nonce aleatórios em CADA gravação; comparação em tempo constante

Isso protege o arquivo do banco QUANDO ELE ESTÁ PARADO NO DISCO (cenário: alguém
copia o inventario.db). Durante o uso, o banco fica descriptografado só na RAM.

ATENÇÃO: sem a senha, NÃO há como recuperar os dados. Faça backup do arquivo
cifrado + guarde a senha em local seguro.

Formato do arquivo:
  MAGIC(8) | iteracoes(4) | salt(16) | nonce(16) | tag(32) | ciphertext(...)
"""

import hashlib
import hmac
import os
import struct

MAGIC = b"INVENC01"          # identifica um arquivo cifrado nosso
ITERACOES_PADRAO = 200_000
TAM_SALT = 16
TAM_NONCE = 16
TAM_TAG = 32                 # HMAC-SHA256


def esta_criptografado(dados: bytes) -> bool:
    """True se os bytes começam com a nossa assinatura (arquivo cifrado)."""
    return dados[:len(MAGIC)] == MAGIC


def _derivar_chaves(senha: str, salt: bytes, iteracoes: int):
    """Deriva 64 bytes e separa em (chave_cifra, chave_mac)."""
    material = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, iteracoes, dklen=64)
    return material[:32], material[32:]


def _keystream(chave_cifra: bytes, nonce: bytes, tamanho: int) -> bytes:
    """Gera `tamanho` bytes de keystream: blocos = HMAC(chave, nonce || contador)."""
    saida = bytearray()
    contador = 0
    while len(saida) < tamanho:
        bloco = hmac.new(chave_cifra, nonce + struct.pack(">Q", contador), hashlib.sha256).digest()
        saida.extend(bloco)
        contador += 1
    return bytes(saida[:tamanho])


def _xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def criptografar(dados: bytes, senha: str, iteracoes: int = ITERACOES_PADRAO) -> bytes:
    """Cifra `dados` com a `senha`. Retorna os bytes do arquivo cifrado."""
    salt = os.urandom(TAM_SALT)
    nonce = os.urandom(TAM_NONCE)
    chave_cifra, chave_mac = _derivar_chaves(senha, salt, iteracoes)

    ciphertext = _xor(dados, _keystream(chave_cifra, nonce, len(dados)))
    cabecalho = MAGIC + struct.pack(">I", iteracoes) + salt + nonce
    tag = hmac.new(chave_mac, cabecalho + ciphertext, hashlib.sha256).digest()
    # ordem final: MAGIC | iter | salt | nonce | tag | ciphertext
    return cabecalho + tag + ciphertext


def descriptografar(dados: bytes, senha: str) -> bytes:
    """Decifra os bytes de um arquivo cifrado. Levanta ValueError se a senha
    estiver errada OU o arquivo tiver sido adulterado/corrompido."""
    if not esta_criptografado(dados):
        raise ValueError("Arquivo não está no formato cifrado esperado.")

    pos = len(MAGIC)
    (iteracoes,) = struct.unpack(">I", dados[pos:pos + 4]); pos += 4
    salt = dados[pos:pos + TAM_SALT]; pos += TAM_SALT
    nonce = dados[pos:pos + TAM_NONCE]; pos += TAM_NONCE
    tag = dados[pos:pos + TAM_TAG]; pos += TAM_TAG
    ciphertext = dados[pos:]

    chave_cifra, chave_mac = _derivar_chaves(senha, salt, iteracoes)
    cabecalho = MAGIC + struct.pack(">I", iteracoes) + salt + nonce
    tag_esperada = hmac.new(chave_mac, cabecalho + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, tag_esperada):
        raise ValueError("Senha incorreta ou arquivo corrompido.")

    return _xor(ciphertext, _keystream(chave_cifra, nonce, len(ciphertext)))
