#!/usr/bin/env bash
# =============================================================================
# Gera um executável independente com o PyInstaller (Linux/macOS).
#
# Resultado: dist/Aprendiz/ — uma pasta com o programa e tudo o que ele usa,
# inclusive o próprio Python. Pode ser copiada para outra máquina com o MESMO
# sistema operacional, sem instalar nada.
#
# O PyInstaller não faz "compilação cruzada": para gerar o .exe do Windows,
# rode distribuicao\empacotar.bat dentro do Windows.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."   # roda a partir da raiz do projeto

if [ ! -x .venv/bin/python ]; then
  echo "Ambiente não encontrado. Rode primeiro: bash instalar.sh"
  exit 1
fi

echo "→ Instalando o PyInstaller"
.venv/bin/python -m pip install "pyinstaller>=6.0" --quiet

echo "→ Gerando o executável (pode levar alguns minutos)"
.venv/bin/python -m PyInstaller \
  --noconfirm --clean \
  --name Aprendiz \
  --add-data "aprendiz/web:aprendiz/web" \
  --collect-submodules uvicorn \
  --paths . \
  distribuicao/iniciar.py

echo
echo "✔ Pronto! Executável em: dist/Aprendiz/Aprendiz"
echo "  Para distribuir, compacte a pasta dist/Aprendiz inteira."
