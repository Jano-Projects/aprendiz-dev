@echo off
REM Abre o Aprendiz. Na primeira vez, instala tudo antes.
REM Ex.: executar.bat --modo navegador
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Primeira execucao: instalando o Aprendiz...
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ferramentas\instalar-windows.ps1"
  if errorlevel 1 (
    if not defined CI pause
    exit /b 1
  )
)
.venv\Scripts\python -m aprendiz %*
