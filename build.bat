@echo off
REM ============================================================
REM  Gera o Inventario.exe (Windows)
REM  Precisa ter o Python instalado no Windows (python.org).
REM  Rode este arquivo DANDO DUPLO CLIQUE nele.
REM ============================================================
chcp 65001 >nul
echo.
echo === Inventario da Sala de Informatica - Gerador do .exe ===
echo.

REM 1) Confere se o Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado.
    echo Instale em https://www.python.org/downloads/  e marque
    echo a opcao "Add Python to PATH" durante a instalacao.
    echo.
    pause
    exit /b 1
)

REM 2) Instala o empacotador e o tema visual (sv-ttk)
echo Instalando/atualizando PyInstaller e o tema (sv-ttk)...
python -m pip install --upgrade pip >nul
python -m pip install --upgrade pyinstaller sv-ttk
if errorlevel 1 (
    echo [ERRO] Nao foi possivel instalar as dependencias.
    pause
    exit /b 1
)

REM 3) Gera o icone (logo_jq.ico) a partir da logo
echo Gerando o icone a partir da logo...
python png_para_ico.py logo_jq.png logo_jq.ico

REM 4) Gera o executavel (uma janela so, sem tela preta de console)
echo.
echo Gerando o executavel... (pode demorar 1-2 minutos)
python -m PyInstaller --onefile --windowed --icon logo_jq.ico --add-data "logo_jq.png;." --collect-all sv_ttk --name Inventario app.py

if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao gerar o .exe.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  PRONTO! O seu programa esta em:   dist\Inventario.exe
echo  Copie esse arquivo para onde quiser (pendrive, etc).
echo ============================================================
echo.
pause
