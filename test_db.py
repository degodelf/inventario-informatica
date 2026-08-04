"""Teste rápido da camada de dados (roda sem tela)."""
import os
import tempfile
import db

# Banco temporário só para o teste
caminho = os.path.join(tempfile.gettempdir(), "teste_inventario.db")
if os.path.exists(caminho):
    os.remove(caminho)

conn = db.conectar(caminho)
db.criar_tabelas(conn)

# 1) Cadastra um PC (com patrimônio) e um mouse vinculado a ele
pc_id = db.adicionar_dispositivo(conn, {
    "patrimonio": "PAT-000123", "categoria": "Computador (PC)",
    "marca": "Dell", "modelo": "OptiPlex 3080", "numero_serie": "SN9988",
    "status": "Em uso", "local": "Sala de Informática", "responsavel": "Recepção",
    "valor": 3200.00,
})
mouse_id = db.adicionar_dispositivo(conn, {
    "categoria": "Mouse", "marca": "Logitech", "status": "Em uso",
    "pai_id": pc_id, "local": "Sala de Informática",
})
print(f"PC id={pc_id}, Mouse id={mouse_id}")

# 2) Registra uma manutenção terceirizada com "anexo"
db.adicionar_manutencao(conn, {
    "dispositivo_id": pc_id, "data": "2026-08-04",
    "empresa": "TecFix Ltda", "descricao": "Troca de fonte queimada",
    "custo": 180.00, "anexo_path": "anexos/os_tecfix_001.pdf",
})

# 3) Consultas
assert db.estatisticas(conn)["total"] == 2, "deveria haver 2 dispositivos"
assert len(db.listar_filhos(conn, pc_id)) == 1, "PC deveria ter 1 acessório"
assert len(db.listar_manutencoes(conn, pc_id)) == 1, "PC deveria ter 1 manutenção"
assert len(db.listar_dispositivos(conn, texto="Dell")) == 1, "busca por Dell"
assert len(db.listar_dispositivos(conn, categoria="Mouse")) == 1, "filtro Mouse"
assert len(db.listar_dispositivos(conn, status="Quebrado")) == 0, "nenhum quebrado"

# 4) Atualização
db.atualizar_dispositivo(conn, mouse_id, {
    "categoria": "Mouse", "status": "Quebrado", "pai_id": pc_id,
})
assert len(db.listar_dispositivos(conn, status="Quebrado")) == 1, "mouse agora quebrado"

# 5) Exportar CSV
n = db.exportar_csv(conn, os.path.join(tempfile.gettempdir(), "teste_export.csv"))
assert n == 2

# 6) Excluir PC leva junto a manutenção (CASCADE)
db.excluir_dispositivo(conn, pc_id)
assert len(db.listar_manutencoes(conn, pc_id)) == 0, "manutenção sumiu junto com o PC"

conn.close()
print("TODOS OS TESTES PASSARAM ✅")
