@echo off
REM ===========================================================================
REM Gera o executavel do Windows com o PyInstaller.
REM Resultado: dist\Aprendiz\Aprendiz.exe (compacte a pasta para distribuir).
REM --windowed: abre sem a janela preta do console.
REM ===========================================================================
setlocal
cd /d "%~dp0.."
REM (roda a partir da raiz do projeto)
if not exist .venv\Scripts\python.exe (
  echo Ambiente nao encontrado. Rode primeiro instalar.bat
  if not defined CI pause
  exit /b 1
)

echo - Instalando o PyInstaller
.venv\Scripts\python -m pip install "pyinstaller>=6.0" --quiet

echo - Gerando o executavel (pode levar alguns minutos)
.venv\Scripts\python -m PyInstaller --noconfirm --clean --windowed ^
  --name Aprendiz ^
  --add-data "aprendiz/web;aprendiz/web" ^
  --collect-submodules uvicorn ^
  --paths . ^
  distribuicao\iniciar.py

echo.
echo [OK] Executavel em dist\Aprendiz\Aprendiz.exe
if not defined CI pause
