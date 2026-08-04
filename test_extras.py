"""Testa as melhorias que rodam sem tela: senha, etiquetas, relatório, ícone."""
import os
import tempfile

import db
import auth
import etiquetas
import relatorio
import png_para_ico

# ---- 1) Tabela CODE 39: cada caractere deve ter EXATAMENTE 3 elementos largos
for ch, pad in etiquetas.CODE39.items():
    assert len(pad) == 9, f"{ch}: padrão não tem 9 elementos"
    assert pad.count("w") == 3, f"{ch}: não tem 3 barras/espaços largos (tabela errada!)"
print("CODE 39: tabela consistente (autoconferência 3-largos) ✅")

# ---- 2) SVG do código de barras
svg, largura = etiquetas.svg_code39("PAT-123")
assert svg.startswith("<svg") and "</svg>" in svg
assert svg.count("<rect") >= 10 and largura > 0
assert etiquetas.limpar_codigo("pat/12 ãç") == "PAT/12 --"  # inválidos viram '-'
print("Etiquetas: SVG gerado e código limpo ✅")

# ---- 3) Senha (PBKDF2)
conn = db.conectar(":memory:")
db.criar_tabelas(conn)
assert auth.tem_senha(conn) is False
auth.definir_senha(conn, "1234")
assert auth.tem_senha(conn) is True
assert auth.verificar_senha(conn, "1234") is True
assert auth.verificar_senha(conn, "errada") is False
assert db.get_config(conn, "senha_hash") != "1234"  # não guarda em texto puro
print("Senha: definir/verificar OK e sem texto puro ✅")

# ---- 4) HTML de etiquetas e relatório
pc = db.adicionar_dispositivo(conn, {
    "categoria": "Computador (PC)", "marca": "Dell", "modelo": "3080",
    "status": "Em uso", "patrimonio": "PAT-000123", "valor": 3200.0,
})
disps = db.listar_dispositivos(conn)
html_e = etiquetas.gerar_html_etiquetas(disps)
assert "<svg" in html_e and "PAT-000123" in html_e
html_r = relatorio.gerar_html_relatorio(disps, filtro_desc="teste")
assert "Dell" in html_r and "R$ 3.200,00" in html_r
print("HTML de etiquetas e relatório: OK ✅")

# ---- 5) Conversor da logo PNG -> ICO
ico = os.path.join(tempfile.gettempdir(), "logo_teste.ico")
png_para_ico.png_para_ico("logo_jq.png", ico)
with open(ico, "rb") as f:
    dados = f.read()
assert dados[:4] == b"\x00\x00\x01\x00", "cabeçalho ICO inválido"
assert b"\x89PNG\r\n\x1a\n" in dados, "PNG não embutido no ICO"
print(f"Ícone: logo convertida para .ico ({len(dados)} bytes) ✅")

# ---- 6) Atualização: comparação de versão e script de troca
import atualizacao
assert atualizacao.ha_versao_mais_nova("v1.2.0", "1.1.9") is True
assert atualizacao.ha_versao_mais_nova("v1.0.0", "1.0.0") is False
assert atualizacao.ha_versao_mais_nova("v1.0.0", "1.0.1") is False
assert atualizacao._para_numeros("v2.3.4") == (2, 3, 4)
assert atualizacao.esta_configurado() is True  # usuário 'degodelf' preenchido
bat = atualizacao._script_troca(r"C:\x\Inventario_novo.exe", r"C:\x\Inventario.exe")
assert "move /Y" in bat and "Inventario.exe" in bat and 'start ""' in bat
print("Atualização: comparação de versão e script de troca OK ✅")

print("\nTODOS OS TESTES DAS MELHORIAS PASSARAM ✅")
