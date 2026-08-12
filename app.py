"""
Inventário da Sala de Informática — tela principal (Tkinter).

Programa de janela para Windows. Guarda tudo em um único arquivo de banco
(inventario.db) e as notas/OS digitalizadas na pasta 'anexos', ambos ao lado
do .exe — assim o backup é só copiar a pasta.

Rodar durante o desenvolvimento:   python app.py
Gerar o .exe:                       ver build.bat / LEIAME.txt
"""

import os
import sys
import shutil
import sqlite3
import threading
import webbrowser
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

import db
import auth
import cripto
import etiquetas
import relatorio
import atualizacao
import adb
import mtp

# Tema visual moderno (Windows 11). Opcional: se não estiver instalado, o
# programa continua funcionando com o tema padrão do Tkinter.
try:
    import sv_ttk
    _TEMA_DISPONIVEL = True
except ImportError:
    _TEMA_DISPONIVEL = False


# --- Onde ficam os dados (ao lado do .exe, ou do script no desenvolvimento) ---

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "inventario.db")
ANEXOS_DIR = os.path.join(BASE_DIR, "anexos")


def _recurso(nome):
    """Caminho de um arquivo EMPACOTADO (logo, etc.). No .exe onefile os
    recursos são extraídos para sys._MEIPASS; rodando pelo código, ficam ao
    lado do script."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, nome)


def _barra_titulo(win):
    """Deixa a barra de título da janela clara/escura conforme o tema atual.
    Só faz efeito no Windows (usa a API DWM); em outros sistemas, ignora.
    Ideal chamar com a janela ainda 'withdraw' e dar deiconify depois."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        win.update_idletasks()
        escuro = ctypes.c_int(1 if (_TEMA_DISPONIVEL and sv_ttk.get_theme() == "dark") else 0)
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (Win10 20H1+); versões antigas = 19
        for attr in (20, 19):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attr, ctypes.byref(escuro), ctypes.sizeof(escuro)
            )
    except Exception:
        pass


# --- Utilitários --------------------------------------------------------------

def parse_valor(txt):
    """Converte texto em número. Aceita '3.200,00', '3200.00', 'R$ 180,50'..."""
    txt = (txt or "").strip().replace("R$", "").replace(" ", "")
    if not txt:
        return None
    if "," in txt and "." in txt:          # 3.200,00 -> 3200.00
        txt = txt.replace(".", "").replace(",", ".")
    elif "," in txt:                        # 180,50 -> 180.50
        txt = txt.replace(",", ".")
    try:
        return float(txt)
    except ValueError:
        return None


def fmt_valor(v):
    """Número -> 'R$ 3.200,00'. None/vazio -> ''."""
    if v is None or v == "":
        return ""
    try:
        return "R$ " + f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return str(v)


def abrir_arquivo(caminho):
    """Abre um arquivo no programa padrão do sistema."""
    if not caminho or not os.path.exists(caminho):
        messagebox.showwarning("Arquivo", "Arquivo não encontrado:\n" + str(caminho))
        return
    try:
        if sys.platform.startswith("win"):
            os.startfile(caminho)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.system(f'open "{caminho}"')
        else:
            os.system(f'xdg-open "{caminho}"')
    except Exception as e:  # noqa: BLE001
        messagebox.showerror("Erro ao abrir", str(e))


def copiar_anexo(origem):
    """Copia um arquivo para a pasta 'anexos' com nome único.
    Devolve o caminho relativo salvo no banco (ex: 'anexos/20260804_...pdf')."""
    os.makedirs(ANEXOS_DIR, exist_ok=True)
    base = os.path.basename(origem)
    nome = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{base}"
    shutil.copy2(origem, os.path.join(ANEXOS_DIR, nome))
    return os.path.join("anexos", nome)


# --- Formulário de cadastro/edição de dispositivo -----------------------------

class FormularioDispositivo(tk.Toplevel):
    """Janela para criar ou editar um dispositivo.
    Ao fechar salvando, define self.salvou = True."""

    def __init__(self, master, conn, disp=None, preset=None):
        super().__init__(master)
        self.conn = conn
        self.disp = disp                 # sqlite3.Row existente, ou None (novo)
        self.salvou = False
        self.salvou_id = None            # id do item salvo (para selecionar na lista)
        self.foto_path = disp["foto_path"] if disp else None

        self.withdraw()                       # esconde até ficar pronto (barra de título correta)
        self.title("Editar dispositivo" if disp else "Novo dispositivo")
        self.transient(master)
        self.resizable(False, False)

        self._preview_img = None          # segura a imagem para não sumir da tela

        self._montar()
        if disp:
            self._preencher(disp)
        else:
            self.vars["local"].set("Informática")   # local já vem preenchido em novos
            if preset:
                self._aplicar_preset(preset)
        self._atualizar_preview()

        _barra_titulo(self)
        self.deiconify()
        self.grab_set()
        self.vars["patrimonio"].focus_set()   # pronto para o leitor de código
        self.bind("<Escape>", lambda e: self.destroy())

    def _montar(self):
        self.vars = {}
        quadro = ttk.Frame(self, padding=12)
        quadro.grid(sticky="nsew")

        def linha(rotulo, chave, r, largura=34):
            ttk.Label(quadro, text=rotulo).grid(row=r, column=0, sticky="e", padx=(0, 8), pady=3)
            var = tk.StringVar()
            e = ttk.Entry(quadro, textvariable=var, width=largura)
            e.grid(row=r, column=1, sticky="w", pady=3)
            self.vars[chave] = var
            return e

        def combo(rotulo, chave, valores, r):
            ttk.Label(quadro, text=rotulo).grid(row=r, column=0, sticky="e", padx=(0, 8), pady=3)
            var = tk.StringVar()
            c = ttk.Combobox(quadro, textvariable=var, values=valores, width=32, state="readonly")
            c.grid(row=r, column=1, sticky="w", pady=3)
            self.vars[chave] = var
            return c

        # Coluna 0/1
        e_pat = linha("Patrimônio / Cód. barras:", "patrimonio", 0)
        e_pat.configure(width=22)
        # ID interno de 2 dígitos, ao lado do patrimônio
        ttk.Label(quadro, text="ID (2 díg.):").grid(row=0, column=2, sticky="e", padx=(10, 4))
        self.vars["id_curto"] = tk.StringVar()
        ttk.Entry(quadro, textvariable=self.vars["id_curto"], width=6).grid(row=0, column=3, sticky="w")
        combo("Categoria: *", "categoria", db.CATEGORIAS, 1)
        # Marca: combo EDITÁVEL — escolhe da lista ou digita uma nova (fica salva)
        ttk.Label(quadro, text="Marca:").grid(row=2, column=0, sticky="e", padx=(0, 8), pady=3)
        self.vars["marca"] = tk.StringVar()
        ttk.Combobox(quadro, textvariable=self.vars["marca"],
                     values=db.listar_marcas(self.conn), width=32).grid(
                         row=2, column=1, sticky="w", pady=3)
        linha("Modelo:", "modelo", 3)
        linha("Nº de série:", "numero_serie", 4)
        combo("Status: *", "status", db.STATUS, 5)
        linha("Local / Sala:", "local", 6)
        linha("Responsável:", "responsavel", 7)
        linha("Data de compra:", "data_compra", 8)
        linha("Garantia até:", "garantia_ate", 9)
        linha("Valor (R$):", "valor", 10)

        # Vínculo com "pai" (ex: mouse -> PC)
        ttk.Label(quadro, text="Vinculado a:").grid(row=11, column=0, sticky="e", padx=(0, 8), pady=3)
        self.pai_opcoes = [("(nenhum)", None)] + [
            (rot, i) for (i, rot) in db.opcoes_pai(
                self.conn, self.disp["id"] if self.disp else None
            )
        ]
        self.var_pai = tk.StringVar(value="(nenhum)")
        self.combo_pai = ttk.Combobox(
            quadro, textvariable=self.var_pai,
            values=[rot for (rot, _) in self.pai_opcoes],
            width=32, state="readonly",
        )
        self.combo_pai.grid(row=11, column=1, sticky="w", pady=3)

        # Foto
        ttk.Label(quadro, text="Foto:").grid(row=12, column=0, sticky="e", padx=(0, 8), pady=3)
        quadro_foto = ttk.Frame(quadro)
        quadro_foto.grid(row=12, column=1, sticky="w", pady=3)
        self.lbl_foto = ttk.Label(quadro_foto, text="(nenhuma)", width=24)
        self.lbl_foto.grid(row=0, column=0, sticky="w")
        ttk.Button(quadro_foto, text="Escolher…", command=self._escolher_foto).grid(row=0, column=1, padx=4)
        ttk.Button(quadro_foto, text="Ver", command=self._ver_foto).grid(row=0, column=2)

        # Miniatura da foto (só PNG/GIF têm pré-visualização sem bibliotecas extras)
        self.lbl_preview = ttk.Label(quadro, anchor="center")
        self.lbl_preview.grid(row=16, column=0, columnspan=2, pady=(8, 0))

        # Observações
        ttk.Label(quadro, text="Observações:").grid(row=13, column=0, sticky="ne", padx=(0, 8), pady=3)
        self.txt_obs = tk.Text(quadro, width=34, height=3)
        self.txt_obs.grid(row=13, column=1, sticky="w", pady=3)

        # Botões
        botoes = ttk.Frame(quadro)
        botoes.grid(row=14, column=0, columnspan=2, pady=(12, 0), sticky="e")
        ttk.Button(botoes, text="Salvar", command=self._salvar).grid(row=0, column=0, padx=4)
        ttk.Button(botoes, text="Cancelar", command=self.destroy).grid(row=0, column=1)

        ttk.Label(quadro, text="* obrigatório", foreground="#888").grid(
            row=15, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )

    def _escolher_foto(self):
        caminho = filedialog.askopenfilename(
            title="Escolher foto",
            filetypes=[("Imagens", "*.jpg *.jpeg *.png *.gif *.bmp"), ("Todos", "*.*")],
        )
        if caminho:
            self.foto_path = caminho
            self.lbl_foto.configure(text=os.path.basename(caminho))
            self._atualizar_preview()

    def _ver_foto(self):
        abrir_arquivo(self.foto_path)

    def _atualizar_preview(self):
        """Mostra uma miniatura da foto (PNG/GIF). Outros formatos: usar 'Ver'."""
        self._preview_img = None
        if not self.foto_path or not os.path.exists(self.foto_path):
            self.lbl_preview.configure(image="", text="")
            return
        try:
            img = tk.PhotoImage(file=self.foto_path)   # suporta PNG e GIF
            fator = max(1, img.width() // 140)          # reduz para ~140px de largura
            if fator > 1:
                img = img.subsample(fator, fator)
            self._preview_img = img
            self.lbl_preview.configure(image=img, text="")
        except Exception:  # noqa: BLE001  (JPG/BMP não pré-visualizam sem Pillow)
            self.lbl_preview.configure(image="", text="(sem prévia — use 'Ver' para abrir)")

    def _preencher(self, d):
        for chave in ["patrimonio", "id_curto", "categoria", "marca", "modelo",
                      "numero_serie", "status", "local", "responsavel",
                      "data_compra", "garantia_ate"]:
            self.vars[chave].set(d[chave] or "")
        self.vars["valor"].set(fmt_valor(d["valor"]).replace("R$ ", "") if d["valor"] is not None else "")
        self.txt_obs.insert("1.0", d["observacoes"] or "")
        if d["foto_path"]:
            self.lbl_foto.configure(text=os.path.basename(d["foto_path"]))
        # pai
        for rot, i in self.pai_opcoes:
            if i == d["pai_id"]:
                self.var_pai.set(rot)
                break

    def _aplicar_preset(self, preset):
        """Pré-preenche campos ao criar um item novo (ex: dados detectados por USB)."""
        for chave, valor in preset.items():
            if chave == "observacoes":
                self.txt_obs.delete("1.0", "end")
                self.txt_obs.insert("1.0", valor or "")
            elif chave in self.vars:
                self.vars[chave].set(valor or "")

    def _salvar(self):
        categoria = self.vars["categoria"].get().strip()
        status = self.vars["status"].get().strip()
        if not categoria:
            messagebox.showwarning("Faltou dado", "Escolha a categoria.")
            return
        if not status:
            messagebox.showwarning("Faltou dado", "Escolha o status.")
            return

        # id do pai selecionado
        pai_id = None
        rotulo_pai = self.var_pai.get()
        for rot, i in self.pai_opcoes:
            if rot == rotulo_pai:
                pai_id = i
                break

        dados = {
            "patrimonio": self.vars["patrimonio"].get().strip() or None,
            "id_curto": self.vars["id_curto"].get().strip() or None,
            "categoria": categoria,
            "marca": self.vars["marca"].get().strip() or None,
            "modelo": self.vars["modelo"].get().strip() or None,
            "numero_serie": self.vars["numero_serie"].get().strip() or None,
            "status": status,
            "local": self.vars["local"].get().strip() or None,
            "responsavel": self.vars["responsavel"].get().strip() or None,
            "data_compra": self.vars["data_compra"].get().strip() or None,
            "garantia_ate": self.vars["garantia_ate"].get().strip() or None,
            "valor": parse_valor(self.vars["valor"].get()),
            "pai_id": pai_id,
            "foto_path": self.foto_path,
            "observacoes": self.txt_obs.get("1.0", "end").strip() or None,
        }
        if self.disp:
            db.atualizar_dispositivo(self.conn, self.disp["id"], dados)
            self.salvou_id = self.disp["id"]
        else:
            self.salvou_id = db.adicionar_dispositivo(self.conn, dados)
        self.salvou = True
        self.destroy()


# --- Janela de manutenções de um dispositivo ----------------------------------

class JanelaManutencoes(tk.Toplevel):
    def __init__(self, master, conn, disp):
        super().__init__(master)
        self.conn = conn
        self.disp = disp
        self.anexo_novo = None            # caminho escolhido para a próxima manut.

        self.withdraw()
        titulo = f"Manutenções — {disp['categoria']} {disp['marca'] or ''} {disp['modelo'] or ''}".strip()
        self.title(titulo)
        self.transient(master)
        self.geometry("720x460")

        self._montar()
        self._recarregar()
        _barra_titulo(self)
        self.deiconify()
        self.grab_set()

    def _montar(self):
        quadro = ttk.Frame(self, padding=10)
        quadro.pack(fill="both", expand=True)

        # Lista de manutenções
        cols = ("data", "empresa", "descricao", "custo", "anexo")
        self.tree = ttk.Treeview(quadro, columns=cols, show="headings", height=8)
        for c, t, w in [
            ("data", "Data", 90), ("empresa", "Empresa/Técnico", 150),
            ("descricao", "Descrição", 240), ("custo", "Custo", 90),
            ("anexo", "Nota/OS", 80),
        ]:
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self._abrir_anexo())

        barra = ttk.Frame(quadro)
        barra.pack(fill="x", pady=(6, 10))
        ttk.Button(barra, text="Abrir nota/OS", command=self._abrir_anexo).pack(side="left")
        ttk.Button(barra, text="Excluir", command=self._excluir).pack(side="left", padx=6)

        # Formulário de nova manutenção
        form = ttk.LabelFrame(quadro, text="Registrar serviço", padding=8)
        form.pack(fill="x")

        ttk.Label(form, text="Data:").grid(row=0, column=0, sticky="e", padx=4, pady=3)
        self.var_data = tk.StringVar(value=datetime.now().strftime("%d/%m/%Y"))
        ttk.Entry(form, textvariable=self.var_data, width=14).grid(row=0, column=1, sticky="w")

        ttk.Label(form, text="Empresa/Técnico:").grid(row=0, column=2, sticky="e", padx=4)
        self.var_empresa = tk.StringVar()
        ttk.Entry(form, textvariable=self.var_empresa, width=24).grid(row=0, column=3, sticky="w")

        ttk.Label(form, text="Custo (R$):").grid(row=0, column=4, sticky="e", padx=4)
        self.var_custo = tk.StringVar()
        ttk.Entry(form, textvariable=self.var_custo, width=12).grid(row=0, column=5, sticky="w")

        ttk.Label(form, text="Descrição:").grid(row=1, column=0, sticky="e", padx=4, pady=3)
        self.var_desc = tk.StringVar()
        ttk.Entry(form, textvariable=self.var_desc, width=60).grid(
            row=1, column=1, columnspan=4, sticky="w"
        )

        ttk.Label(form, text="Nota/OS:").grid(row=2, column=0, sticky="e", padx=4, pady=3)
        self.lbl_anexo = ttk.Label(form, text="(nenhum arquivo)")
        self.lbl_anexo.grid(row=2, column=1, columnspan=2, sticky="w")
        ttk.Button(form, text="Anexar arquivo…", command=self._escolher_anexo).grid(row=2, column=3, sticky="w")
        ttk.Button(form, text="Adicionar serviço", command=self._adicionar).grid(row=2, column=5, sticky="e")

    def _escolher_anexo(self):
        caminho = filedialog.askopenfilename(
            title="Selecionar nota/OS digitalizada",
            filetypes=[("PDF/Imagem", "*.pdf *.jpg *.jpeg *.png"), ("Todos", "*.*")],
        )
        if caminho:
            self.anexo_novo = caminho
            self.lbl_anexo.configure(text=os.path.basename(caminho))

    def _adicionar(self):
        if not self.var_desc.get().strip() and not self.var_empresa.get().strip():
            messagebox.showwarning("Faltou dado", "Informe ao menos a empresa ou a descrição.")
            return
        anexo_rel = copiar_anexo(self.anexo_novo) if self.anexo_novo else None
        db.adicionar_manutencao(self.conn, {
            "dispositivo_id": self.disp["id"],
            "data": self.var_data.get().strip() or None,
            "empresa": self.var_empresa.get().strip() or None,
            "descricao": self.var_desc.get().strip() or None,
            "custo": parse_valor(self.var_custo.get()),
            "anexo_path": anexo_rel,
        })
        # limpa o formulário
        self.var_empresa.set(""); self.var_desc.set(""); self.var_custo.set("")
        self.anexo_novo = None
        self.lbl_anexo.configure(text="(nenhum arquivo)")
        self._recarregar()

    def _recarregar(self):
        self.tree.delete(*self.tree.get_children())
        for m in db.listar_manutencoes(self.conn, self.disp["id"]):
            self.tree.insert(
                "", "end", iid=str(m["id"]),
                values=(
                    m["data"] or "", m["empresa"] or "", m["descricao"] or "",
                    fmt_valor(m["custo"]), "📎 sim" if m["anexo_path"] else "—",
                ),
            )

    def _selecionado(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _abrir_anexo(self):
        mid = self._selecionado()
        if not mid:
            return
        for m in db.listar_manutencoes(self.conn, self.disp["id"]):
            if m["id"] == mid:
                if m["anexo_path"]:
                    abrir_arquivo(os.path.join(BASE_DIR, m["anexo_path"]))
                else:
                    messagebox.showinfo("Nota/OS", "Este serviço não tem arquivo anexado.")
                return

    def _excluir(self):
        mid = self._selecionado()
        if not mid:
            return
        if messagebox.askyesno("Excluir", "Excluir este registro de manutenção?"):
            db.excluir_manutencao(self.conn, mid)
            self._recarregar()


# --- Janela: gerenciar apps de um aparelho Android ----------------------------

class JanelaAppsAndroid(tk.Toplevel):
    """Lista os apps de um aparelho Android e permite desinstalar / forçar parada."""

    def __init__(self, master, serial, conn):
        super().__init__(master)
        self.withdraw()
        self.serial = serial
        self.conn = conn
        self.pacotes = []
        self.var_sistema = tk.BooleanVar(value=False)

        self.title("Apps do aparelho Android")
        self.transient(master)
        self.geometry("560x520")

        self._montar()
        self._recarregar()
        _barra_titulo(self)
        self.deiconify()
        self.grab_set()

    def _montar(self):
        quadro = ttk.Frame(self, padding=10)
        quadro.pack(fill="both", expand=True)

        topo = ttk.Frame(quadro)
        topo.pack(fill="x")
        ttk.Label(topo, text="Apps instalados no aparelho:").pack(side="left")
        ttk.Checkbutton(topo, text="incluir apps do sistema",
                        variable=self.var_sistema, command=self._recarregar).pack(side="right")

        meio = ttk.Frame(quadro)
        meio.pack(fill="both", expand=True, pady=(6, 6))
        self.lista = tk.Listbox(meio, selectmode="extended", activestyle="none")
        vsb = ttk.Scrollbar(meio, orient="vertical", command=self.lista.yview)
        self.lista.configure(yscrollcommand=vsb.set)
        self.lista.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.lbl_info = ttk.Label(quadro, text="")
        self.lbl_info.pack(fill="x")

        barra = ttk.Frame(quadro)
        barra.pack(fill="x", pady=(6, 2))
        ttk.Button(barra, text="Atualizar", command=self._recarregar).pack(side="left")
        ttk.Button(barra, text="Forçar parada", command=self._forcar_parada).pack(side="left", padx=6)
        ttk.Button(barra, text="Desinstalar selecionado(s)",
                   command=self._desinstalar).pack(side="right")

        barra2 = ttk.Frame(quadro)
        barra2.pack(fill="x")
        ttk.Label(barra2, text="Adicionar seleção à:").pack(side="left")
        ttk.Button(barra2, text="lista de remoção",
                   command=lambda: self._adicionar_lista("remocao")).pack(side="left", padx=4)
        ttk.Button(barra2, text="lista de limpeza",
                   command=lambda: self._adicionar_lista("limpeza")).pack(side="left")

    def _adicionar_lista(self, tipo):
        alvos = self._selecionados()
        if not alvos:
            messagebox.showinfo("Apps", "Selecione um ou mais apps na lista.")
            return
        if tipo == "remocao":
            db.set_lista_remocao(self.conn, db.get_lista_remocao(self.conn) + alvos)
            nome = "remoção (o Preparar tablet desinstala)"
        else:
            db.set_lista_limpeza(self.conn, db.get_lista_limpeza(self.conn) + alvos)
            nome = "limpeza (o Preparar tablet reseta)"
        messagebox.showinfo("Listas", f"{len(alvos)} app(s) adicionado(s) à lista de {nome}.")

    def _recarregar(self):
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            self.pacotes = adb.listar_apps(self.serial, incluir_sistema=self.var_sistema.get())
        finally:
            self.config(cursor="")
        self.lista.delete(0, "end")
        for p in self.pacotes:
            self.lista.insert("end", p)
        self.lbl_info.configure(text=f"{len(self.pacotes)} app(s). Selecione um ou mais.")

    def _selecionados(self):
        return [self.lista.get(i) for i in self.lista.curselection()]

    def _desinstalar(self):
        alvos = self._selecionados()
        if not alvos:
            messagebox.showinfo("Apps", "Selecione um ou mais apps na lista.")
            return
        amostra = "\n".join("• " + a for a in alvos[:15])
        extra = "" if len(alvos) <= 15 else f"\n… e mais {len(alvos) - 15}"
        if not messagebox.askyesno(
            "Desinstalar",
            f"Desinstalar {len(alvos)} app(s) DO APARELHO?\n\n{amostra}{extra}\n\n"
            "Isso remove o app do tablet/celular. Confirmar?",
        ):
            return
        falhas = []
        for p in alvos:
            ok, msg = adb.desinstalar_app(self.serial, p)
            if not ok:
                falhas.append(f"{p}: {msg}")
        self._recarregar()
        if falhas:
            messagebox.showwarning(
                "Desinstalar",
                f"{len(alvos) - len(falhas)} ok, {len(falhas)} falharam:\n\n"
                + "\n".join(falhas[:10]),
            )
        else:
            messagebox.showinfo("Desinstalar", f"{len(alvos)} app(s) desinstalado(s). ✅")

    def _forcar_parada(self):
        alvos = self._selecionados()
        if not alvos:
            messagebox.showinfo("Apps", "Selecione um ou mais apps na lista.")
            return
        for p in alvos:
            adb.parar_app(self.serial, p)
        messagebox.showinfo("Forçar parada", f"Parada forçada em {len(alvos)} app(s).")


# --- Janela: listas de apps (remoção / limpeza) usadas pelo "Preparar tablet" -

class JanelaListaApps(tk.Toplevel):
    """Edita uma lista de pacotes: 'remocao' (desinstalar) ou 'limpeza' (reset)."""

    _CONFIG = {
        "remocao": ("Lista de remoção de apps",
                    "Apps que o 'Preparar tablet' vai REMOVER (desinstalar) de cada aparelho:"),
        "limpeza": ("Lista de limpeza (reset) de apps",
                    "Apps que o 'Preparar tablet' vai RESETAR (pm clear). Ex: com.android.chrome "
                    "fecha todas as abas e limpa o Chrome:"),
    }

    def __init__(self, master, conn, tipo):
        super().__init__(master)
        self.withdraw()
        self.conn = conn
        self.tipo = tipo
        titulo, self.descricao = self._CONFIG[tipo]
        self.title(titulo)
        self.transient(master)
        self.geometry("500x460")
        self._montar()
        self._recarregar()
        _barra_titulo(self)
        self.deiconify()
        self.grab_set()

    def _get(self):
        f = db.get_lista_remocao if self.tipo == "remocao" else db.get_lista_limpeza
        return f(self.conn)

    def _set(self, pacotes):
        f = db.set_lista_remocao if self.tipo == "remocao" else db.set_lista_limpeza
        f(self.conn, pacotes)

    def _montar(self):
        q = ttk.Frame(self, padding=10)
        q.pack(fill="both", expand=True)
        ttk.Label(q, text=self.descricao, wraplength=460, justify="left").pack(anchor="w")

        meio = ttk.Frame(q)
        meio.pack(fill="both", expand=True, pady=6)
        self.lista = tk.Listbox(meio, selectmode="extended", activestyle="none")
        vsb = ttk.Scrollbar(meio, orient="vertical", command=self.lista.yview)
        self.lista.configure(yscrollcommand=vsb.set)
        self.lista.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        add = ttk.Frame(q)
        add.pack(fill="x")
        self.var_novo = tk.StringVar()
        e = ttk.Entry(add, textvariable=self.var_novo)
        e.pack(side="left", fill="x", expand=True)
        e.bind("<Return>", lambda ev: self._adicionar())
        ttk.Button(add, text="Adicionar", command=self._adicionar).pack(side="left", padx=4)

        barra = ttk.Frame(q)
        barra.pack(fill="x", pady=(8, 0))
        ttk.Label(barra, text="(nome do pacote, ex: com.android.chrome)",
                  foreground="gray").pack(side="left")
        ttk.Button(barra, text="Remover da lista", command=self._remover).pack(side="right")

    def _recarregar(self):
        self.lista.delete(0, "end")
        for p in self._get():
            self.lista.insert("end", p)

    def _adicionar(self):
        p = self.var_novo.get().strip()
        if p:
            self._set(self._get() + [p])
            self.var_novo.set("")
            self._recarregar()

    def _remover(self):
        sel = {self.lista.get(i) for i in self.lista.curselection()}
        if not sel:
            return
        self._set([p for p in self._get() if p not in sel])
        self._recarregar()


# --- Janela principal ---------------------------------------------------------

class App(tk.Tk):
    def __init__(self, conn, cifrado=False, senha_cripto=None):
        super().__init__()
        self.conn = conn                 # conexão já aberta (arquivo ou memória)
        self.cifrado = cifrado           # True = banco criptografado (fica na RAM)
        self.senha_cripto = senha_cripto # senha do banco, guardada só nesta sessão
        self._ordem_reversa = {}         # estado de ordenação por coluna
        self.geometry("1040x620")
        self.minsize(900, 520)
        self.title(self._titulo())

        self.var_limpar_chrome = tk.BooleanVar(
            value=db.get_config(self.conn, "limpar_chrome_preparar", "0") == "1")

        self._aplicar_tema(db.get_config(self.conn, "tema", "light"))
        self._definir_icone_janela()
        self._montar()
        self._recarregar()
        _barra_titulo(self)

        self.protocol("WM_DELETE_WINDOW", self._ao_fechar)
        # Verifica atualização sozinho, pouco depois de abrir (silencioso se offline)
        self.after(1200, lambda: self._verificar_atualizacao(manual=False))

    def _titulo(self):
        base = "Inventário — Sala de Informática"
        return base + ("   🔒 (banco criptografado)" if self.cifrado else "")

    def _aplicar_tema(self, tema):
        """Aplica o tema visual (claro/escuro). Se o sv-ttk não estiver
        instalado, não faz nada (mantém o tema padrão do Tkinter)."""
        if not _TEMA_DISPONIVEL:
            return
        try:
            sv_ttk.set_theme("dark" if tema == "dark" else "light")
            ttk.Style().configure("Treeview", rowheight=28)   # linhas mais arejadas
        except Exception:
            pass

    def _alternar_tema(self):
        if not _TEMA_DISPONIVEL:
            messagebox.showinfo("Aparência", "O tema moderno não está disponível nesta instalação.")
            return
        novo = "light" if sv_ttk.get_theme() == "dark" else "dark"
        sv_ttk.set_theme(novo)
        ttk.Style().configure("Treeview", rowheight=28)
        _barra_titulo(self)               # atualiza a barra de título junto
        db.set_config(self.conn, "tema", novo)
        self._persistir()

    def _definir_icone_janela(self):
        """Coloca a logo JQ como ícone da janela (no lugar da peninha padrão)."""
        # No Windows, iconbitmap(.ico) é o jeito CONFIÁVEL para a barra de título.
        try:
            if sys.platform.startswith("win"):
                ico = _recurso("logo_jq.ico")
                if os.path.exists(ico):
                    self.iconbitmap(default=ico)   # vale p/ esta e as próximas janelas
        except Exception:  # noqa: BLE001
            pass
        # iconphoto (PNG) cobre a barra de tarefas / outros sistemas
        try:
            self._icone_janela = tk.PhotoImage(file=_recurso("logo_jq.png"))
            self.iconphoto(True, self._icone_janela)
        except Exception:  # noqa: BLE001
            pass

    def _montar(self):
        # Menu superior
        menubar = tk.Menu(self)
        m_rel = tk.Menu(menubar, tearoff=0)
        m_rel.add_command(label="Exportar para Excel (CSV)", command=self._exportar)
        m_rel.add_command(label="Relatório / PDF (navegador)", command=self._relatorio)
        m_rel.add_command(label="Gerar etiquetas de código de barras", command=self._etiquetas)
        menubar.add_cascade(label="Relatórios", menu=m_rel)
        m_seg = tk.Menu(menubar, tearoff=0)
        m_seg.add_command(label="Definir / alterar senha…", command=self._definir_senha)
        m_seg.add_separator()
        m_seg.add_command(label="Ativar criptografia do banco…", command=self._ativar_cripto)
        m_seg.add_command(label="Desativar criptografia…", command=self._desativar_cripto)
        menubar.add_cascade(label="Segurança", menu=m_seg)
        m_fer = tk.Menu(menubar, tearoff=0)
        m_fer.add_command(label="⚡ Preparar tablet (provisionar)…",
                          command=self._preparar_tablet)
        m_fer.add_separator()
        m_fer.add_command(label="Detectar por cabo — MTP (sem depuração)…",
                          command=self._detectar_mtp)
        m_fer.add_command(label="Detectar via depuração — ADB (avançado)…",
                          command=self._detectar_android)
        m_fer.add_command(label="Gerenciar apps do aparelho Android…",
                          command=self._gerenciar_apps)
        m_fer.add_command(label="Lista de remoção de apps…",
                          command=self._editar_lista_remocao)
        m_fer.add_command(label="Lista de limpeza (reset) de apps…",
                          command=self._editar_lista_limpeza)
        m_fer.add_separator()
        m_fer.add_command(label="Limpar Chrome do aparelho (abas + cache/cookies)…",
                          command=self._limpar_chrome_agora)
        m_fer.add_checkbutton(label="Limpar Chrome no Preparar tablet",
                              variable=self.var_limpar_chrome,
                              command=self._salvar_toggle_chrome)
        menubar.add_cascade(label="Ferramentas", menu=m_fer)
        m_ap = tk.Menu(menubar, tearoff=0)
        m_ap.add_command(label="Alternar tema claro / escuro", command=self._alternar_tema)
        menubar.add_cascade(label="Aparência", menu=m_ap)
        m_aj = tk.Menu(menubar, tearoff=0)
        m_aj.add_command(label="Verificar atualização agora",
                         command=lambda: self._verificar_atualizacao(manual=True))
        m_aj.add_command(label="Sobre", command=self._sobre)
        menubar.add_cascade(label="Ajuda", menu=m_aj)
        self.config(menu=menubar)

        # Barra de filtros
        topo = ttk.Frame(self, padding=(10, 8))
        topo.pack(fill="x")

        ttk.Label(topo, text="Buscar:").pack(side="left")
        self.var_busca = tk.StringVar()
        e = ttk.Entry(topo, textvariable=self.var_busca, width=28)
        e.pack(side="left", padx=(4, 10))
        e.bind("<Return>", lambda ev: self._recarregar())

        ttk.Label(topo, text="Categoria:").pack(side="left")
        self.var_cat = tk.StringVar()
        ttk.Combobox(topo, textvariable=self.var_cat, values=[""] + db.CATEGORIAS,
                     width=18, state="readonly").pack(side="left", padx=(4, 10))

        ttk.Label(topo, text="Status:").pack(side="left")
        self.var_stat = tk.StringVar()
        ttk.Combobox(topo, textvariable=self.var_stat, values=[""] + db.STATUS,
                     width=14, state="readonly").pack(side="left", padx=(4, 10))

        ttk.Button(topo, text="Filtrar", command=self._recarregar).pack(side="left")
        ttk.Button(topo, text="Limpar", command=self._limpar_filtros).pack(side="left", padx=4)

        # Botões de ação
        acoes = ttk.Frame(self, padding=(10, 0))
        acoes.pack(fill="x")
        ttk.Button(acoes, text="＋ Novo", command=self._novo).pack(side="left")
        ttk.Button(acoes, text="Editar", command=self._editar).pack(side="left", padx=4)
        ttk.Button(acoes, text="Excluir", command=self._excluir).pack(side="left")
        ttk.Button(acoes, text="Manutenções…", command=self._manutencoes).pack(side="left", padx=4)
        ttk.Button(acoes, text="🔄 Atualizar", command=self._recarregar).pack(side="left")
        ttk.Button(acoes, text="🏷️ Etiquetas", command=self._etiquetas).pack(side="right")
        ttk.Button(acoes, text="📄 Relatório/PDF", command=self._relatorio).pack(side="right", padx=4)
        ttk.Button(acoes, text="Exportar CSV", command=self._exportar).pack(side="right")

        # Tabela
        quadro = ttk.Frame(self, padding=10)
        quadro.pack(fill="both", expand=True)

        cols = ("id_curto", "patrimonio", "categoria", "marca", "modelo",
                "status", "local", "responsavel")
        self.tree = ttk.Treeview(quadro, columns=cols, show="headings")
        larguras = {
            "id_curto": 55, "patrimonio": 120, "categoria": 140, "marca": 110,
            "modelo": 150, "status": 110, "local": 130, "responsavel": 120,
        }
        titulos = {
            "id_curto": "ID", "patrimonio": "Patrimônio", "categoria": "Categoria",
            "marca": "Marca", "modelo": "Modelo", "status": "Status",
            "local": "Local", "responsavel": "Responsável",
        }
        for c in cols:
            # cabeçalho clicável: ordena por aquela coluna
            self.tree.heading(c, text=titulos[c], command=lambda col=c: self._ordenar(col))
            self.tree.column(c, width=larguras[c], anchor="w")
        vsb = ttk.Scrollbar(quadro, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda e: self._editar())

        # Menu de clique com o botão direito na tabela
        self.menu_tabela = tk.Menu(self, tearoff=0)
        self.menu_tabela.add_command(label="Editar", command=self._editar)
        self.menu_tabela.add_command(label="Manutenções…", command=self._manutencoes)
        self.menu_tabela.add_command(label="Gerar etiqueta", command=self._etiquetas)
        self.menu_tabela.add_separator()
        self.menu_tabela.add_command(label="Excluir", command=self._excluir)
        self.tree.bind("<Button-3>", self._menu_botao_direito)

        # cor de fundo diferente por status "problema"
        self.tree.tag_configure("quebrado", background="#ffe0e0")
        self.tree.tag_configure("manutencao", background="#fff3cd")

        # Dica no meio da tabela quando não há nada cadastrado (some ao cadastrar)
        self.lbl_vazio = ttk.Label(
            quadro, justify="center", foreground="gray",
            text="Nenhum dispositivo cadastrado.\nClique em  ➕ Novo  para começar.",
        )

        # Rodapé: contagens à esquerda, crédito à direita
        rodape = ttk.Frame(self)
        rodape.pack(fill="x", side="bottom")
        self.lbl_status = ttk.Label(rodape, text="", anchor="w", padding=(10, 4))
        self.lbl_status.pack(side="left")
        ttk.Label(rodape, text=f"JQSoluçõesTI · v{atualizacao.VERSAO}",
                  anchor="e", padding=(10, 4)).pack(side="right")

    # ---- ações ----

    def _limpar_filtros(self):
        self.var_busca.set("")
        self.var_cat.set("")
        self.var_stat.set("")
        self._recarregar()

    def _recarregar(self):
        self.tree.delete(*self.tree.get_children())
        linhas = db.listar_dispositivos(
            self.conn, self.var_busca.get(), self.var_cat.get(), self.var_stat.get()
        )
        for d in linhas:
            tag = ""
            if d["status"] == "Quebrado":
                tag = "quebrado"
            elif d["status"] == "Em manutenção":
                tag = "manutencao"
            self.tree.insert(
                "", "end", iid=str(d["id"]),
                values=(
                    d["id_curto"] or "", d["patrimonio"] or "", d["categoria"],
                    d["marca"] or "", d["modelo"] or "", d["status"], d["local"] or "",
                    d["responsavel"] or "",
                ),
                tags=(tag,) if tag else (),
            )
        est = db.estatisticas(self.conn)
        partes = [f"Total: {est['total']}"]
        for s in db.STATUS:
            n = est["por_status"].get(s, 0)
            if n:
                partes.append(f"{s}: {n}")
        self.lbl_status.configure(text="   |   ".join(partes))

        # mostra/esconde a dica de lista vazia
        if not linhas:
            self.lbl_vazio.place(relx=0.5, rely=0.45, anchor="center")
        else:
            self.lbl_vazio.place_forget()

        # força o redesenho imediato da tabela (evita "só aparece após reiniciar")
        self.tree.update_idletasks()

    def _ordenar(self, col):
        """Ordena a tabela pela coluna clicada (alterna crescente/decrescente)."""
        reverso = self._ordem_reversa.get(col, False)
        itens = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]

        def chave(par):
            v = (par[0] or "").strip()
            try:
                return (0, float(v.replace(",", ".")))   # números (ex: ID) na ordem certa
            except ValueError:
                return (1, v.lower())                    # texto, sem diferenciar maiúscula

        itens.sort(key=chave, reverse=reverso)
        for i, (_v, k) in enumerate(itens):
            self.tree.move(k, "", i)
        self._ordem_reversa[col] = not reverso

    def _id_selecionado(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _selecionar_id(self, did):
        """Seleciona, foca e rola até o item na lista (ex: recém-salvo)."""
        iid = str(did)
        if did and self.tree.exists(iid):
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.tree.see(iid)

    def _mostrar_novo(self, novo_id):
        """Após ADICIONAR um item, limpa os filtros e mostra/seleciona ele —
        garante que o recém-salvo apareça na hora, mesmo com busca/filtro ativo."""
        self.var_busca.set("")
        self.var_cat.set("")
        self.var_stat.set("")
        self._recarregar()
        self._selecionar_id(novo_id)

    def _menu_botao_direito(self, evento):
        linha = self.tree.identify_row(evento.y)
        if linha:
            self.tree.selection_set(linha)
            self.tree.focus(linha)
            self.menu_tabela.tk_popup(evento.x_root, evento.y_root)

    def _novo(self):
        f = FormularioDispositivo(self, self.conn)
        self.wait_window(f)
        if f.salvou:
            self._persistir()
            self._mostrar_novo(f.salvou_id)

    def _editar(self):
        did = self._id_selecionado()
        if not did:
            messagebox.showinfo("Editar", "Selecione um dispositivo na lista.")
            return
        disp = db.obter_dispositivo(self.conn, did)
        f = FormularioDispositivo(self, self.conn, disp)
        self.wait_window(f)
        if f.salvou:
            self._recarregar()
            self._persistir()
            self._selecionar_id(f.salvou_id)

    def _excluir(self):
        did = self._id_selecionado()
        if not did:
            messagebox.showinfo("Excluir", "Selecione um dispositivo na lista.")
            return
        disp = db.obter_dispositivo(self.conn, did)
        rotulo = f"{disp['categoria']} {disp['marca'] or ''} {disp['modelo'] or ''}".strip()
        if messagebox.askyesno(
            "Excluir",
            f"Excluir '{rotulo}'?\n\nO histórico de manutenções dele também será apagado.",
        ):
            db.excluir_dispositivo(self.conn, did)
            self._recarregar()
            self._persistir()

    def _manutencoes(self):
        did = self._id_selecionado()
        if not did:
            messagebox.showinfo("Manutenções", "Selecione um dispositivo na lista.")
            return
        disp = db.obter_dispositivo(self.conn, did)
        j = JanelaManutencoes(self, self.conn, disp)
        self.wait_window(j)
        self._persistir()

    def _exportar(self):
        caminho = filedialog.asksaveasfilename(
            title="Exportar inventário",
            defaultextension=".csv",
            initialfile="inventario.csv",
            filetypes=[("CSV (Excel)", "*.csv")],
        )
        if not caminho:
            return
        n = db.exportar_csv(self.conn, caminho)
        messagebox.showinfo("Exportado", f"{n} dispositivos exportados para:\n{caminho}")

    def _filtrados(self):
        """Lista de dispositivos conforme os filtros atuais da tela."""
        return db.listar_dispositivos(
            self.conn, self.var_busca.get(), self.var_cat.get(), self.var_stat.get()
        )

    def _descricao_filtro(self):
        partes = []
        if self.var_busca.get().strip():
            partes.append(f"busca '{self.var_busca.get().strip()}'")
        if self.var_cat.get():
            partes.append(self.var_cat.get())
        if self.var_stat.get():
            partes.append(self.var_stat.get())
        return ", ".join(partes)

    def _relatorio(self):
        disps = self._filtrados()
        if not disps:
            messagebox.showinfo("Relatório", "Nenhum dispositivo para o relatório.")
            return
        relatorio.gerar_e_abrir(disps, self._descricao_filtro())

    def _etiquetas(self):
        # Etiquetas dos itens SELECIONADOS; se nada selecionado, dos filtrados.
        ids = [int(i) for i in self.tree.selection()]
        if ids:
            disps = [db.obter_dispositivo(self.conn, i) for i in ids]
        else:
            disps = self._filtrados()
            if disps and not messagebox.askyesno(
                "Etiquetas",
                f"Nenhum item selecionado. Gerar etiquetas para os {len(disps)} "
                "itens da lista atual?",
            ):
                return
        if not disps:
            messagebox.showinfo("Etiquetas", "Nada para gerar.")
            return
        etiquetas.gerar_e_abrir(disps)

    def _definir_senha(self):
        nova = simpledialog.askstring(
            "Senha", "Nova senha (deixe em branco para REMOVER a senha):",
            show="*", parent=self,
        )
        if nova is None:
            return
        if nova == "":
            db.set_config(self.conn, "senha_hash", None)
            db.set_config(self.conn, "senha_salt", None)
            self._persistir()
            messagebox.showinfo("Senha", "Senha removida. O programa abrirá sem pedir senha.")
            return
        conf = simpledialog.askstring("Senha", "Repita a nova senha:", show="*", parent=self)
        if conf != nova:
            messagebox.showwarning("Senha", "As senhas não conferem. Nada foi alterado.")
            return
        auth.definir_senha(self.conn, nova)
        self._persistir()
        messagebox.showinfo("Senha", "Senha definida. Ela será pedida na próxima vez que abrir.")


    def _sobre(self):
        win = tk.Toplevel(self)
        win.withdraw()
        win.title("Sobre")
        win.transient(self)
        win.resizable(False, False)
        frm = ttk.Frame(win, padding=24)
        frm.pack()
        try:
            win._logo = tk.PhotoImage(file=_recurso("logo_jq.png"))
            ttk.Label(frm, image=win._logo).pack(pady=(0, 12))
        except Exception:
            pass
        ttk.Label(frm, text="Inventário da Sala de Informática",
                  font=("Segoe UI", 13, "bold")).pack()
        ttk.Label(frm, text=f"Versão {atualizacao.VERSAO}").pack(pady=(2, 14))
        ttk.Label(frm, text="Criação: JQSoluçõesTI",
                  font=("Segoe UI", 11, "bold")).pack()
        ttk.Label(frm, text="Os dados e a senha ficam somente neste computador.",
                  foreground="#888").pack(pady=(12, 0))
        ttk.Button(frm, text="Fechar", command=win.destroy).pack(pady=(18, 0))
        win.bind("<Escape>", lambda e: win.destroy())
        _barra_titulo(win)
        win.deiconify()
        win.grab_set()

    # ---- criptografia do banco (em repouso) ----

    def _persistir(self):
        """No modo cifrado, regrava o banco (que fica na RAM) criptografado no
        disco. No modo normal, o SQLite já salvou sozinho — não faz nada."""
        if not self.cifrado:
            return
        try:
            blob = self.conn.serialize()
            dados = cripto.criptografar(blob, self.senha_cripto)
            tmp = DB_PATH + ".tmp"
            with open(tmp, "wb") as f:
                f.write(dados)
            os.replace(tmp, DB_PATH)          # troca atômica (não corrompe se faltar luz)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Salvar", f"Não consegui salvar o banco cifrado:\n{e}")

    def _ativar_cripto(self):
        if self.cifrado:
            messagebox.showinfo("Criptografia", "O banco já está criptografado.")
            return
        if not messagebox.askyesno(
            "Ativar criptografia",
            "O banco será protegido por uma senha e ficará ilegível fora do programa.\n\n"
            "⚠️ ATENÇÃO: se você ESQUECER a senha, os dados NÃO poderão ser "
            "recuperados. Guarde a senha em local seguro e mantenha backup do arquivo.\n\n"
            "Deseja continuar?",
        ):
            return
        s1 = simpledialog.askstring("Criptografia", "Crie a senha do banco:", show="*", parent=self)
        if not s1:
            return
        s2 = simpledialog.askstring("Criptografia", "Repita a senha:", show="*", parent=self)
        if s1 != s2:
            messagebox.showwarning("Criptografia", "As senhas não conferem. Nada foi feito.")
            return
        # passa a operar em memória e grava o arquivo já cifrado
        blob = self.conn.serialize()
        conn_mem = sqlite3.connect(":memory:")
        conn_mem.deserialize(blob)
        conn_mem.row_factory = sqlite3.Row
        conn_mem.execute("PRAGMA foreign_keys = ON")
        try:
            self.conn.close()                 # libera o arquivo plaintext
        except Exception:
            pass
        self.conn = conn_mem
        self.cifrado = True
        self.senha_cripto = s1
        self._persistir()                     # grava inventario.db já cifrado
        self.title(self._titulo())
        messagebox.showinfo(
            "Criptografia",
            "Banco criptografado com sucesso!\nA senha será pedida ao abrir o programa.\n"
            "Lembre: sem ela, não há recuperação.",
        )

    def _desativar_cripto(self):
        if not self.cifrado:
            messagebox.showinfo("Criptografia", "O banco não está criptografado.")
            return
        if not messagebox.askyesno(
            "Desativar criptografia",
            "O banco voltará a ficar SEM criptografia — qualquer um com acesso ao "
            "arquivo poderá ler os dados. Tem certeza?",
        ):
            return
        blob = self.conn.serialize()          # esses bytes são um arquivo SQLite normal
        tmp = DB_PATH + ".tmp"
        try:
            with open(tmp, "wb") as f:
                f.write(blob)
            os.replace(tmp, DB_PATH)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Criptografia", f"Falha ao gravar:\n{e}")
            return
        try:
            self.conn.close()
        except Exception:
            pass
        self.conn = db.conectar(DB_PATH)      # reabre como arquivo normal
        self.cifrado = False
        self.senha_cripto = None
        self.title(self._titulo())
        messagebox.showinfo("Criptografia", "Criptografia desativada.")

    def _ao_fechar(self):
        self._persistir()
        try:
            self.conn.close()
        except Exception:
            pass
        self.destroy()

    # ---- ferramentas: aparelhos Android via USB ----

    def _obter_serial_android(self):
        """Retorna o serial de UM aparelho Android pronto, ou None (mostrando o
        aviso adequado). Usado pela detecção e pelo gerenciador de apps."""
        if not adb.disponivel():
            messagebox.showwarning("Android", "O ADB não está disponível nesta versão do programa.")
            return None
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            aparelhos = adb.listar_dispositivos()
        finally:
            self.config(cursor="")

        prontos = [a for a in aparelhos if a["estado"] == "device"]
        nao_autorizados = [a for a in aparelhos if a["estado"] == "unauthorized"]

        if not aparelhos:
            messagebox.showinfo(
                "Android",
                "Nenhum aparelho detectado.\n\n"
                "1) Conecte o tablet/celular por USB\n"
                "2) Ative a 'Depuração USB' (Opções do desenvolvedor)\n"
                "3) Tente de novo",
            )
            return None
        if not prontos and nao_autorizados:
            messagebox.showinfo(
                "Android",
                "Aparelho conectado, mas falta AUTORIZAR o computador.\n\n"
                "Na tela do aparelho, toque em 'Permitir' na janela de depuração USB "
                "(marque 'Sempre permitir deste computador') e tente de novo.",
            )
            return None
        if not prontos:
            estados = ", ".join(a["estado"] for a in aparelhos)
            messagebox.showwarning(
                "Android", f"Aparelho detectado, mas não está pronto (estado: {estados})."
            )
            return None
        if len(prontos) > 1:
            messagebox.showinfo(
                "Android",
                f"{len(prontos)} aparelhos conectados. Vou usar o primeiro. "
                "Faça um de cada vez.",
            )
        return prontos[0]["serial"]

    def _obs_android(self, info, verbo="detectado"):
        """Monta o texto de observações do cadastro com os identificadores."""
        v = info.get("versao_android")
        obs = f"Android {v} — {verbo} via USB" if v else f"{verbo.capitalize()} via USB"
        if info.get("id_tipo") and info["id_tipo"] != "série":
            obs += f" · id por {info['id_tipo']}"
        if info.get("detalhe_ids"):
            obs += f"\n{info['detalhe_ids']}"
        return obs

    def _detectar_mtp(self):
        """Lê o aparelho plugado pelo Windows (modo MTP/câmera), SEM depuração,
        e abre o cadastro preenchido com modelo e nº de série."""
        if not sys.platform.startswith("win"):
            messagebox.showinfo("Detectar (MTP)", "Este recurso só funciona no Windows.")
            return
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            aparelhos = mtp.listar_portateis()
        finally:
            self.config(cursor="")

        if not aparelhos:
            messagebox.showinfo(
                "Detectar (MTP)",
                "Nenhum aparelho portátil detectado.\n\n"
                "1) Conecte o tablet por USB\n"
                "2) Na tela do aparelho, escolha o modo "
                "'Transferência de arquivos (MTP)'\n"
                "3) Tente de novo",
            )
            return

        a = aparelhos[0]
        if len(aparelhos) > 1:
            messagebox.showinfo(
                "Detectar (MTP)",
                f"{len(aparelhos)} aparelhos conectados. Vou usar o primeiro "
                f"({a['nome']}). Faça um de cada vez.",
            )
        obs = "Detectado por cabo (MTP)"
        if not a["serie"]:
            obs += " · nº de série não veio limpo (confira/preencha)"
        preset = {
            "categoria": "Tablet",
            "modelo": a["nome"],
            "numero_serie": a["serie"],
            "status": "Em uso",
            "observacoes": obs,
        }
        f = FormularioDispositivo(self, self.conn, preset=preset)
        self.wait_window(f)
        if f.salvou:
            self._persistir()
            self._mostrar_novo(f.salvou_id)

    def _detectar_android(self):
        """Lê um tablet/celular Android plugado (via ADB) e abre o cadastro
        já preenchido com marca, modelo, nº de série e versão."""
        serial = self._obter_serial_android()
        if not serial:
            return
        info = adb.info_dispositivo(serial)
        preset = {
            "categoria": "Tablet",
            "marca": info["marca"],
            "modelo": info["modelo"],
            "numero_serie": info["numero_serie"],
            "status": "Em uso",
            "observacoes": self._obs_android(info, "detectado"),
        }
        f = FormularioDispositivo(self, self.conn, preset=preset)
        self.wait_window(f)
        if f.salvou:
            self._persistir()
            self._mostrar_novo(f.salvou_id)

    def _gerenciar_apps(self):
        """Abre a janela para listar / desinstalar / parar apps do aparelho."""
        serial = self._obter_serial_android()
        if not serial:
            return
        j = JanelaAppsAndroid(self, serial, self.conn)
        self.wait_window(j)
        self._persistir()          # pode ter mudado a lista de remoção

    def _editar_lista_remocao(self):
        self.wait_window(JanelaListaApps(self, self.conn, "remocao"))
        self._persistir()

    def _editar_lista_limpeza(self):
        self.wait_window(JanelaListaApps(self, self.conn, "limpeza"))
        self._persistir()

    def _salvar_toggle_chrome(self):
        db.set_config(self.conn, "limpar_chrome_preparar",
                      "1" if self.var_limpar_chrome.get() else "0")
        self._persistir()

    def _limpar_chrome_agora(self):
        serial = self._obter_serial_android()
        if not serial:
            return
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            ok, msg = adb.limpar_chrome(serial)
        finally:
            self.config(cursor="")
        if ok:
            messagebox.showinfo("Limpar Chrome", f"✅ {msg}\n(a conta continua logada)")
        else:
            messagebox.showwarning(
                "Limpar Chrome",
                f"{msg}\n\nDica: o Chrome precisa estar ABERTO no aparelho.")

    def _preparar_tablet(self):
        """Fluxo de 1 clique: detecta > cadastra/atualiza > remove apps da lista
        > mostra resumo. Ideal para preparar vários tablets em sequência."""
        serial = self._obter_serial_android()
        if not serial:
            return
        lista = db.get_lista_remocao(self.conn)
        lista_limpeza = db.get_lista_limpeza(self.conn)
        info = adb.info_dispositivo(serial)
        rotulo = f"{info['marca']} {info['modelo']}".strip() or serial

        passos = (
            "• Cadastrar/atualizar no inventário\n"
            f"• Resetar {len(lista_limpeza)} app(s) da lista de limpeza\n"
            f"• Remover {len(lista)} app(s) da lista de remoção\n"
        )
        if self.var_limpar_chrome.get():
            passos += "• Fechar abas + limpar cache/cookies do Chrome (mantém a conta)\n"

        if not messagebox.askyesno(
            "Preparar tablet",
            f"Preparar este aparelho?\n\n{rotulo}\n\n{passos}\nContinuar?",
        ):
            return

        self.config(cursor="watch")
        self.update_idletasks()
        removidos, resetados, falhas = 0, 0, []
        chrome_resultado = ""
        try:
            # 1) cadastrar OU atualizar (pelo nº de série, evita duplicar)
            dados = {
                "categoria": "Tablet",
                "marca": info["marca"],
                "modelo": info["modelo"],
                "numero_serie": info["numero_serie"],
                "status": "Em uso",
                "observacoes": self._obs_android(info, "preparado"),
            }
            existente = db.buscar_por_serie(self.conn, info["numero_serie"])
            if existente:
                base = {c: existente[c] for c in db.CAMPOS_DISPOSITIVO}
                base.update(dados)     # atualiza infos do aparelho, preserva patrimônio/local/etc.
                db.atualizar_dispositivo(self.conn, existente["id"], base)
                acao = "atualizado"
            else:
                db.adicionar_dispositivo(self.conn, dados)
                acao = "cadastrado"

            # 2) resetar (pm clear) e desinstalar os apps das listas
            if lista or lista_limpeza:
                instalados = set(adb.listar_apps(serial, incluir_sistema=True))
                for pac in lista_limpeza:
                    if pac in instalados:
                        ok, _msg = adb.limpar_dados_app(serial, pac)
                        if ok:
                            resetados += 1
                        else:
                            falhas.append(f"reset {pac}")
                for pac in lista:
                    if pac in instalados:
                        adb.parar_app(serial, pac)
                        ok, _msg = adb.desinstalar_app(serial, pac)
                        if ok:
                            removidos += 1
                        else:
                            falhas.append(f"remover {pac}")

            # 3) Chrome: fechar abas + limpar cache/cookies (mantém a conta)
            if self.var_limpar_chrome.get():
                ok_c, msg_c = adb.limpar_chrome(serial)
                chrome_resultado = f"Chrome: {msg_c}" if ok_c else f"Chrome falhou: {msg_c}"
        finally:
            self.config(cursor="")

        self.var_busca.set(""); self.var_cat.set(""); self.var_stat.set("")
        self._recarregar()
        self._persistir()

        resumo = (
            "✅ Processo concluído!\n\n"
            f"Aparelho {acao}: {rotulo}\n"
            f"Apps resetados: {resetados} de {len(lista_limpeza)}\n"
            f"Apps removidos: {removidos} de {len(lista)}\n"
        )
        if chrome_resultado:
            resumo += chrome_resultado + "\n"
        if falhas:
            resumo += f"Falhas: {len(falhas)} ({', '.join(falhas[:5])})\n"
        resumo += "\nPode desconectar e plugar o PRÓXIMO tablet."
        messagebox.showinfo("Preparar tablet", resumo)

    # ---- atualização automática (via GitHub Releases) ----

    def _verificar_atualizacao(self, manual):
        """Checa o GitHub em segundo plano. manual=True mostra avisos mesmo
        quando já está atualizado ou quando falha; manual=False é silencioso."""
        if not atualizacao.esta_configurado():
            if manual:
                messagebox.showinfo(
                    "Atualização",
                    "Ainda não configurado. Preencha GITHUB_USUARIO em atualizacao.py.",
                )
            return

        def trabalho():
            try:
                res = atualizacao.checar_online()
            except Exception as exc:  # noqa: BLE001
                msg = str(exc) or "falha"     # guarda o texto (evita o 'del e' do except)
                self.after(0, lambda: self._tratar_atualizacao(None, msg, manual))
                return
            self.after(0, lambda: self._tratar_atualizacao(res, None, manual))

        threading.Thread(target=trabalho, daemon=True).start()

    def _tratar_atualizacao(self, res, erro, manual):
        if erro is not None or res is None:
            if manual:
                messagebox.showwarning(
                    "Atualização",
                    "Não consegui verificar agora (sem internet ou bloqueado pela rede).",
                )
            return
        if not res["tem_nova"]:
            if manual:
                messagebox.showinfo(
                    "Atualização",
                    f"Você já está na versão mais recente ({atualizacao.VERSAO}).",
                )
            return

        # Há versão nova.
        if not getattr(sys, "frozen", False):
            # Rodando pelo código (desenvolvimento): não troca .exe, só avisa.
            if messagebox.askyesno(
                "Atualização",
                f"Nova versão {res['versao_nova']} disponível.\n"
                "(No modo desenvolvimento a troca automática não se aplica.)\n\n"
                "Abrir a página?",
            ):
                webbrowser.open(res["pagina"] or res["exe_url"])
            return
        if not res["exe_url"]:
            messagebox.showinfo(
                "Atualização",
                f"Nova versão {res['versao_nova']} disponível, mas a release não tem "
                "um arquivo .exe. Vou abrir a página de download.",
            )
            webbrowser.open(res["pagina"])
            return
        if not messagebox.askyesno(
            "Atualização disponível",
            f"Nova versão {res['versao_nova']} disponível!\n"
            f"(você tem a {atualizacao.VERSAO})\n\n"
            "Baixar e instalar agora? O programa vai fechar e reabrir sozinho.",
        ):
            return
        self._baixar_e_instalar(res["exe_url"])

    def _baixar_e_instalar(self, url):
        janela = tk.Toplevel(self)
        janela.withdraw()
        janela.title("Atualizando")
        janela.transient(self)
        janela.resizable(False, False)
        ttk.Label(janela, text="Baixando a nova versão…", padding=12).pack()
        barra = ttk.Progressbar(janela, length=300, mode="determinate")
        barra.pack(padx=12, pady=(0, 12))
        _barra_titulo(janela)
        janela.deiconify()
        janela.grab_set()

        destino = os.path.join(BASE_DIR, "Inventario_novo.exe")

        def progresso(baixado, total):
            self.after(0, lambda: barra.configure(
                maximum=max(total, 1), value=baixado, mode="determinate"))

        def trabalho():
            try:
                atualizacao.baixar(url, destino, progresso)
            except Exception as e:  # noqa: BLE001
                msg = str(e)
                self.after(0, lambda: (janela.destroy(), messagebox.showerror(
                    "Atualização", f"Falha ao baixar:\n{msg}")))
                return
            self.after(0, lambda: self._aplicar_atualizacao(destino, janela))

        threading.Thread(target=trabalho, daemon=True).start()

    def _aplicar_atualizacao(self, destino, janela):
        janela.destroy()
        try:
            atualizacao.instalar_e_reiniciar(destino)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Atualização", f"Não consegui aplicar a atualização:\n{e}")
            return
        # fecha o programa; o .bat troca o .exe e reabre sozinho
        self.conn.close()
        self.destroy()
        sys.exit(0)


def _abrir_sessao_banco(parent):
    """Abre o banco ANTES da janela principal. Retorna (conn, cifrado, senha)
    ou None se o usuário cancelar / errar a senha.

    - Arquivo CIFRADO: pede a senha e decifra para a memória (RAM).
    - Arquivo normal (ou primeiro uso): abre o arquivo e, se houver senha de
      acesso cadastrada, pede o login."""
    dados = b""
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f:
            dados = f.read()

    # --- Banco criptografado: pedir senha e carregar na memória ---
    if dados and cripto.esta_criptografado(dados):
        for _ in range(3):
            senha = simpledialog.askstring(
                "Banco protegido", "Digite a senha do banco:", show="*", parent=parent
            )
            if senha is None:
                return None
            try:
                blob = cripto.descriptografar(dados, senha)
            except ValueError:
                messagebox.showerror(
                    "Banco protegido", "Senha incorreta ou arquivo corrompido.",
                    parent=parent,
                )
                continue
            conn = sqlite3.connect(":memory:")
            conn.deserialize(blob)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            db.criar_tabelas(conn)
            return (conn, True, senha)
        return None

    # --- Banco normal (ou primeiro uso) ---
    conn = db.conectar(DB_PATH)
    db.criar_tabelas(conn)
    if auth.tem_senha(conn):
        for _ in range(3):
            senha = simpledialog.askstring("Acesso", "Digite a senha:", show="*", parent=parent)
            if senha is None:
                conn.close()
                return None
            if auth.verificar_senha(conn, senha):
                return (conn, False, None)
            messagebox.showerror("Acesso", "Senha incorreta.", parent=parent)
        conn.close()
        return None
    return (conn, False, None)


def main():
    raiz = tk.Tk()
    raiz.withdraw()                       # janela invisível só para os diálogos iniciais
    sessao = _abrir_sessao_banco(raiz)
    raiz.destroy()
    if sessao is None:
        return                            # cancelou ou errou a senha 3x
    conn, cifrado, senha = sessao
    app = App(conn, cifrado, senha)
    app.mainloop()


if __name__ == "__main__":
    main()
