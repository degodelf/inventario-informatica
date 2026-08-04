# Inventário da Sala de Informática

Programa de desktop (Windows) para cadastrar e controlar os equipamentos de uma
sala de informática: PCs, monitores, periféricos, cabos, celulares, tablets etc.

Feito em **Python + Tkinter + SQLite**. A única dependência externa é o tema
visual **sv-ttk** (Python puro, empacotado dentro do próprio `.exe`).

**Criação: JQSoluçõesTI**

## Recursos

- 🖥️ Cadastro com **código de patrimônio / código de barras** (leitor USB)
- 🔗 **Vincular acessórios a um PC** (teclado, mouse, cabos "dentro" do PC)
- 🛠️ **Manutenções** de terceiros com **anexo da nota/OS** digitalizada
- 🔎 Busca e filtros por categoria e status
- 🏷️ **Etiquetas** com código de barras (Code 39) para imprimir e colar
- 📄 **Relatório em PDF** e exportação para Excel (CSV)
- 🔒 **Senha de acesso** e **criptografia do banco** (proteção LGPD dos dados)
- ⬆️ **Atualização automática** via GitHub Releases
- 🎨 **Visual moderno** (tema Windows 11, claro/escuro) e ícone próprio

## Privacidade e segurança

Os **dados e a senha ficam somente no computador** onde o programa roda
(`inventario.db` + pasta `anexos`). Eles **nunca** são enviados para lugar
nenhum — o `.gitignore` garante que não subam para o GitHub.

- Senha: guardada como hash **PBKDF2-HMAC-SHA256** (nunca em texto puro).
- Criptografia do banco: **em repouso**, com chave derivada da senha e
  integridade autenticada (encrypt-then-MAC). Descriptografado só na memória.

> ⚠️ Se a criptografia estiver ativa e a senha for esquecida, os dados **não
> podem ser recuperados**. Mantenha backup do arquivo e guarde a senha.

## Como gerar o `.exe`

Precisa do **Python 3.11+** no Windows. Depois é só dar duplo clique em
`build.bat` — o executável sai em `dist\Inventario.exe`.

Passo a passo completo em [`LEIAME.txt`](LEIAME.txt).
Como publicar versões e a atualização automática: [`PUBLICAR-GITHUB.txt`](PUBLICAR-GITHUB.txt).
