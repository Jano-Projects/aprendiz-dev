#!/usr/bin/env bash
# Abre o Aprendiz. Se ainda não estiver instalado, instala primeiro.
# Aceita as opções de `python -m aprendiz --help`, ex.: bash executar.sh --modo navegador
set -euo pipefail
cd "$(dirname "$0")"

if [ "$(id -u)" -eq 0 ]; then
  echo "⚠ Você está executando como administrador (root)."
  echo "  O Aprendiz guarda a memória na pasta do usuário que o executa;"
  echo "  como root, ela iria para /root. Prefira rodar como seu usuário comum."
  echo
fi

if [ ! -x .venv/bin/python ]; then
  echo "Primeira execução: instalando o Aprendiz…"
  bash instalar.sh
fi

exec .venv/bin/python -m aprendiz "$@"
