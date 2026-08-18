"""
Camada de dados do Inventário da Sala de Informática.

Responsável por TODO o acesso ao banco de dados (SQLite).
Não importa tkinter de propósito: assim esta parte pode ser testada
sozinha, sem abrir a tela.

Banco = um único arquivo (inventario.db). Fazer backup é só copiar esse arquivo.
"""

import sqlite3
from datetime import datetime

# --- Listas fixas usadas na tela (combos) -------------------------------------

CATEGORIAS = [
    "Computador (PC)",
    "Notebook",
    "Monitor",
    "Teclado",
    "Mouse",
    "Impressora",
    "Nobreak/Estabilizador",
    "Cabo",
    "Celular",
    "Tablet",
    "Roteador/Switch",
    "Projetor",
    "Outro",
]

STATUS = [
    "Em uso",
    "Estoque",
    "Emprestado",
    "Em manutenção",
    "Quebrado",
    "Baixado",
]

# Marcas iniciais do combo (o usuário pode digitar novas; elas ficam salvas)
MARCAS_PADRAO = [
    "Multilaser", "Positivo", "Samsung", "Motorola", "LG", "Dell", "HP",
    "Lenovo", "Acer", "Asus", "Philco", "Apple", "Xiaomi", "Logitech",
    "Genius", "Intelbras", "Epson",
]


def agora():
    """Data/hora atual em texto (padrão ISO, ordena certo)."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# --- Conexão e criação das tabelas -------------------------------------------

def conectar(caminho_db):
    """Abre (ou cria) o banco no caminho informado e devolve a conexão."""
    conn = sqlite3.connect(caminho_db)
    conn.row_factory = sqlite3.Row           # acessar colunas pelo nome
    conn.execute("PRAGMA foreign_keys = ON")  # respeitar vínculos entre tabelas
    return conn


def criar_tabelas(conn):
    """Cria as tabelas se ainda não existirem. Seguro rodar toda vez."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS dispositivos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            patrimonio    TEXT,                      -- código de barras / nº patrimônio
            id_curto      TEXT,                      -- ID interno de 2 dígitos
            categoria     TEXT NOT NULL,
            marca         TEXT,
            modelo        TEXT,
            numero_serie  TEXT,
            status        TEXT NOT NULL DEFAULT 'Em uso',
            local         TEXT,                      -- sala/setor onde está
            responsavel   TEXT,
            data_compra   TEXT,
            garantia_ate  TEXT,
            valor         REAL,
            pai_id        INTEGER,                   -- vínculo com o "pai" (ex: mouse -> PC)
            foto_path     TEXT,
            especificacoes TEXT,                     -- ficha técnica lida do aparelho
            observacoes   TEXT,
            criado_em     TEXT,
            atualizado_em TEXT,
            FOREIGN KEY (pai_id) REFERENCES dispositivos(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS manutencoes (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            dispositivo_id INTEGER NOT NULL,
            data           TEXT,
            empresa        TEXT,                     -- empresa/técnico terceiro
            descricao      TEXT,
            custo          REAL,
            anexo_path     TEXT,                     -- nota/OS digitalizada
            criado_em      TEXT,
            FOREIGN KEY (dispositivo_id) REFERENCES dispositivos(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS config (
            chave TEXT PRIMARY KEY,
            valor TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_disp_patrimonio ON dispositivos(patrimonio);
        CREATE INDEX IF NOT EXISTS idx_disp_categoria  ON dispositivos(categoria);
        CREATE INDEX IF NOT EXISTS idx_disp_status     ON dispositivos(status);
        CREATE INDEX IF NOT EXISTS idx_manut_disp      ON manutencoes(dispositivo_id);
        """
    )
    # Migração: adiciona colunas novas em bancos criados por versões antigas.
    # Usa row[1] (nome da coluna) para funcionar com ou sem row_factory.
    colunas = {row[1] for row in conn.execute("PRAGMA table_info(dispositivos)")}
    if "id_curto" not in colunas:
        conn.execute("ALTER TABLE dispositivos ADD COLUMN id_curto TEXT")
    if "especificacoes" not in colunas:
        conn.execute("ALTER TABLE dispositivos ADD COLUMN especificacoes TEXT")
    conn.commit()


# --- Configuração (chave/valor) — usado pela senha ---------------------------

def get_config(conn, chave, padrao=None):
    r = conn.execute("SELECT valor FROM config WHERE chave = ?", (chave,)).fetchone()
    return r["valor"] if r else padrao


def set_config(conn, chave, valor):
    conn.execute(
        "INSERT INTO config (chave, valor) VALUES (?, ?) "
        "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
        (chave, valor),
    )
    conn.commit()


# --- Campos que o formulário de dispositivo envia ----------------------------

CAMPOS_DISPOSITIVO = [
    "patrimonio", "id_curto", "categoria", "marca", "modelo", "numero_serie",
    "status", "local", "responsavel", "data_compra", "garantia_ate",
    "valor", "pai_id", "foto_path", "especificacoes", "observacoes",
]


# --- CRUD de dispositivos -----------------------------------------------------

def adicionar_dispositivo(conn, dados):
    """Insere um dispositivo. `dados` é um dict com as chaves de CAMPOS_DISPOSITIVO.
    Retorna o id criado."""
    d = {c: dados.get(c) for c in CAMPOS_DISPOSITIVO}
    d["criado_em"] = agora()
    d["atualizado_em"] = d["criado_em"]
    colunas = ", ".join(d.keys())
    marcadores = ", ".join(f":{k}" for k in d.keys())
    cur = conn.execute(
        f"INSERT INTO dispositivos ({colunas}) VALUES ({marcadores})", d
    )
    conn.commit()
    return cur.lastrowid


def atualizar_dispositivo(conn, disp_id, dados):
    """Atualiza os campos de um dispositivo existente."""
    d = {c: dados.get(c) for c in CAMPOS_DISPOSITIVO}
    d["atualizado_em"] = agora()
    d["id"] = disp_id
    ajustes = ", ".join(f"{c} = :{c}" for c in CAMPOS_DISPOSITIVO)
    conn.execute(
        f"UPDATE dispositivos SET {ajustes}, atualizado_em = :atualizado_em "
        f"WHERE id = :id",
        d,
    )
    conn.commit()


def excluir_dispositivo(conn, disp_id):
    """Remove um dispositivo (e suas manutenções, por CASCADE)."""
    conn.execute("DELETE FROM dispositivos WHERE id = ?", (disp_id,))
    conn.commit()


def obter_dispositivo(conn, disp_id):
    """Retorna uma linha (sqlite3.Row) do dispositivo, ou None."""
    cur = conn.execute("SELECT * FROM dispositivos WHERE id = ?", (disp_id,))
    return cur.fetchone()


def listar_dispositivos(conn, texto="", categoria="", status=""):
    """Lista dispositivos com filtros opcionais.

    - texto: busca em patrimônio, marca, modelo, nº série, local, responsável
    - categoria / status: filtro exato (vazio = todos)
    """
    condicoes = []
    params = []

    if texto:
        like = f"%{texto.strip()}%"
        condicoes.append(
            "(IFNULL(patrimonio,'') LIKE ? OR IFNULL(id_curto,'') LIKE ? "
            "OR IFNULL(marca,'') LIKE ? OR IFNULL(modelo,'') LIKE ? "
            "OR IFNULL(numero_serie,'') LIKE ? OR IFNULL(local,'') LIKE ? "
            "OR IFNULL(responsavel,'') LIKE ?)"
        )
        params += [like] * 7
    if categoria:
        condicoes.append("categoria = ?")
        params.append(categoria)
    if status:
        condicoes.append("status = ?")
        params.append(status)

    where = ("WHERE " + " AND ".join(condicoes)) if condicoes else ""
    sql = f"SELECT * FROM dispositivos {where} ORDER BY categoria, marca, modelo"
    return conn.execute(sql, params).fetchall()


def existe_valor(conn, campo, valor, excluir_id=None):
    """True se já existe OUTRO dispositivo com aquele valor no campo indicado.
    Usado para avisar sobre patrimônio/ID repetido. `campo` é interno (lista
    fixa), nunca vem do usuário."""
    if campo not in ("patrimonio", "id_curto") or not valor:
        return False
    sql = f"SELECT 1 FROM dispositivos WHERE {campo} = ?"
    params = [valor]
    if excluir_id:
        sql += " AND id != ?"
        params.append(excluir_id)
    sql += " LIMIT 1"
    return conn.execute(sql, params).fetchone() is not None


def buscar_por_serie(conn, numero_serie):
    """Retorna o dispositivo com aquele nº de série, ou None. Usado para não
    duplicar cadastro ao preparar o mesmo tablet de novo."""
    if not numero_serie:
        return None
    return conn.execute(
        "SELECT * FROM dispositivos WHERE numero_serie = ? LIMIT 1", (numero_serie,)
    ).fetchone()


def listar_marcas(conn):
    """Marcas para o combo: as padrão MAIS as que já foram usadas no cadastro
    (assim, marca nova que o usuário digita aparece nas próximas vezes)."""
    usadas = [
        r[0] for r in conn.execute(
            "SELECT DISTINCT marca FROM dispositivos "
            "WHERE marca IS NOT NULL AND TRIM(marca) <> ''"
        ).fetchall()
    ]
    return sorted(set(MARCAS_PADRAO) | set(usadas), key=str.lower)


def get_lista_remocao(conn):
    """Lista de pacotes (apps) que o 'Preparar tablet' deve remover."""
    txt = get_config(conn, "apps_remocao", "") or ""
    return [linha.strip() for linha in txt.splitlines() if linha.strip()]


def set_lista_remocao(conn, pacotes):
    """Salva a lista de apps a remover (sem duplicatas, ordenada)."""
    limpos = sorted({p.strip() for p in pacotes if p.strip()})
    set_config(conn, "apps_remocao", "\n".join(limpos))


def get_lista_limpeza(conn):
    """Lista de pacotes (apps) que o 'Preparar tablet' deve resetar (pm clear)."""
    txt = get_config(conn, "apps_limpeza", "") or ""
    return [linha.strip() for linha in txt.splitlines() if linha.strip()]


def set_lista_limpeza(conn, pacotes):
    """Salva a lista de apps a resetar (sem duplicatas, ordenada)."""
    limpos = sorted({p.strip() for p in pacotes if p.strip()})
    set_config(conn, "apps_limpeza", "\n".join(limpos))


def listar_filhos(conn, pai_id):
    """Lista os acessórios vinculados a um dispositivo pai (ex: mouse do PC)."""
    return conn.execute(
        "SELECT * FROM dispositivos WHERE pai_id = ? ORDER BY categoria", (pai_id,)
    ).fetchall()


def opcoes_pai(conn, excluir_id=None):
    """Lista candidatos a 'pai' (id + rótulo legível) para o combo de vínculo.
    Não deixa um item ser pai dele mesmo."""
    if excluir_id:
        cur = conn.execute(
            "SELECT id, categoria, marca, modelo, patrimonio FROM dispositivos "
            "WHERE id != ? ORDER BY categoria", (excluir_id,)
        )
    else:
        cur = conn.execute(
            "SELECT id, categoria, marca, modelo, patrimonio FROM dispositivos "
            "ORDER BY categoria"
        )
    opcoes = []
    for r in cur.fetchall():
        rotulo = f"[{r['id']}] {r['categoria']} {r['marca'] or ''} {r['modelo'] or ''}".strip()
        if r["patrimonio"]:
            rotulo += f" (pat. {r['patrimonio']})"
        opcoes.append((r["id"], rotulo))
    return opcoes


# --- CRUD de manutenções ------------------------------------------------------

def adicionar_manutencao(conn, dados):
    """Registra uma manutenção. `dados`: dispositivo_id, data, empresa,
    descricao, custo, anexo_path. Retorna o id criado."""
    dados = dict(dados)
    dados["criado_em"] = agora()
    cur = conn.execute(
        "INSERT INTO manutencoes "
        "(dispositivo_id, data, empresa, descricao, custo, anexo_path, criado_em) "
        "VALUES (:dispositivo_id, :data, :empresa, :descricao, :custo, "
        ":anexo_path, :criado_em)",
        {
            "dispositivo_id": dados.get("dispositivo_id"),
            "data": dados.get("data"),
            "empresa": dados.get("empresa"),
            "descricao": dados.get("descricao"),
            "custo": dados.get("custo"),
            "anexo_path": dados.get("anexo_path"),
            "criado_em": dados["criado_em"],
        },
    )
    conn.commit()
    return cur.lastrowid


def listar_manutencoes(conn, dispositivo_id):
    """Histórico de manutenções de um dispositivo, mais recentes primeiro."""
    return conn.execute(
        "SELECT * FROM manutencoes WHERE dispositivo_id = ? "
        "ORDER BY IFNULL(data,'') DESC, id DESC",
        (dispositivo_id,),
    ).fetchall()


def excluir_manutencao(conn, manut_id):
    """Remove um registro de manutenção."""
    conn.execute("DELETE FROM manutencoes WHERE id = ?", (manut_id,))
    conn.commit()


# --- Relatórios / resumo ------------------------------------------------------

def estatisticas(conn):
    """Devolve um dict com contagens úteis para a barra de status."""
    total = conn.execute("SELECT COUNT(*) FROM dispositivos").fetchone()[0]
    por_status = {
        r["status"]: r["n"]
        for r in conn.execute(
            "SELECT status, COUNT(*) n FROM dispositivos GROUP BY status"
        ).fetchall()
    }
    return {"total": total, "por_status": por_status}


def exportar_csv(conn, caminho):
    """Exporta todos os dispositivos para um CSV (abre no Excel)."""
    import csv

    linhas = conn.execute(
        "SELECT id, patrimonio, id_curto, categoria, marca, modelo, numero_serie, status, "
        "local, responsavel, data_compra, garantia_ate, valor, especificacoes, observacoes "
        "FROM dispositivos ORDER BY categoria, marca"
    ).fetchall()
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")  # ';' abre certinho no Excel PT-BR
        w.writerow([
            "ID", "Patrimônio", "ID (2 díg.)", "Categoria", "Marca", "Modelo", "Nº Série",
            "Status", "Local", "Responsável", "Data compra", "Garantia até",
            "Valor", "Especificações", "Observações",
        ])
        for r in linhas:
            w.writerow([r[c] if r[c] is not None else "" for c in r.keys()])
    return len(linhas)


def exportar_xlsx(conn, caminho):
    """Exporta todos os dispositivos para um .xlsx de verdade (abre no Excel/
    LibreOffice). Valor e ID entram como número (dá para somar/ordenar)."""
    import xlsx

    linhas = conn.execute(
        "SELECT id, patrimonio, id_curto, categoria, marca, modelo, numero_serie, status, "
        "local, responsavel, data_compra, garantia_ate, valor, especificacoes, observacoes "
        "FROM dispositivos ORDER BY categoria, marca"
    ).fetchall()
    cabecalhos = [
        "ID", "Patrimônio", "ID (2 díg.)", "Categoria", "Marca", "Modelo", "Nº Série",
        "Status", "Local", "Responsável", "Data compra", "Garantia até",
        "Valor", "Especificações", "Observações",
    ]
    larguras = [6, 16, 9, 18, 14, 20, 18, 14, 16, 16, 13, 13, 12, 40, 40]
    dados = []
    for r in linhas:
        dados.append([
            r["id"],
            r["patrimonio"] or "", r["id_curto"] or "", r["categoria"],
            r["marca"] or "", r["modelo"] or "", r["numero_serie"] or "", r["status"],
            r["local"] or "", r["responsavel"] or "", r["data_compra"] or "",
            r["garantia_ate"] or "",
            r["valor"] if r["valor"] is not None else "",
            r["especificacoes"] or "", r["observacoes"] or "",
        ])
    xlsx.escrever(caminho, cabecalhos, dados, larguras=larguras, nome_aba="Inventário")
    return len(dados)
