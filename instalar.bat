@echo off
REM ===========================================================================
REM Instalador do Aprendiz para Windows. De dois cliques neste arquivo.
REM
REM Se o Python nao estiver instalado, ele e baixado do python.org e o
REM Windows pede permissao de administrador (janela do UAC).
REM A logica fica em ferramentas\instalar-windows.ps1.
REM
REM Opcoes:  instalar.bat --janela-nativa   (janela nativa com pywebview)
REM          instalar.bat --dev             (pytest e PyInstaller)
REM ===========================================================================
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ferramentas\instalar-windows.ps1" %*
set "RESULTADO=%errorlevel%"
if not defined CI pause
exit /b %RESULTADO%
