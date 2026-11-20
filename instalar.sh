#!/usr/bin/env bash
# =============================================================================
# Instalador do Aprendiz para Linux (e macOS).
#
# Basta rodar:   bash instalar.sh
#
# O que ele faz, sozinho:
#   1. confere se há Python 3.10+ capaz de criar ambientes virtuais;
#   2. se faltar algo, AVISA que precisa de permissão de administrador e
#      instala pelo gerenciador de pacotes da distribuição
#      (apt, dnf, zypper, pacman ou apk), pedindo a senha certa:
#        • sudo  → se o seu usuário for administrador (grupo sudo/wheel/admin)
#        • su    → senha do root (ex.: usuário fora do sudoers)
#        • pkexec→ janela gráfica de senha, como último recurso
#   3. cria um ambiente virtual isolado em .venv (não mexe no Python do sistema);
#   4. baixa e instala as dependências (FastAPI, Uvicorn, RapidFuzz).
#
# NÃO rode com sudo: o instalador pede a senha só para o passo que precisa.
#
# Opções:
#   bash instalar.sh --janela-nativa   também instala o pywebview (janela nativa)
#   bash instalar.sh --dev             também instala pytest e PyInstaller
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")" || exit 1

PYTHON="${PYTHON:-python3}"
PACOTES=""
VERSAO_MINIMA="3.10"

# --------------------------------------------------------------------- saída
if [ -t 1 ]; then
  AMARELO=$'\e[33m'; VERMELHO=$'\e[31m'; VERDE=$'\e[32m'; NEGRITO=$'\e[1m'; FIM=$'\e[0m'
else
  AMARELO=""; VERMELHO=""; VERDE=""; NEGRITO=""; FIM=""
fi
info()  { echo "→ $*"; }
aviso() { echo "${AMARELO}⚠ $*${FIM}"; }
erro()  { echo "${VERMELHO}✖ $*${FIM}" >&2; exit 1; }

# --------------------------------------------------------------------- Python ok?
python_pronto() {
  # Python existe, é 3.10+, tem SQLite com FTS5 e consegue criar um venv?
  # (O teste do venv é real: em Debian/Ubuntu o módulo pode estar ausente.)
  command -v "$PYTHON" >/dev/null 2>&1 || return 1
  "$PYTHON" -c "
import sys, sqlite3
assert sys.version_info >= (3, 10)
sqlite3.connect(':memory:').execute('create virtual table t using fts5(x)')
" >/dev/null 2>&1 || return 1
  local tmp
  tmp="$(mktemp -d)"
  "$PYTHON" -m venv "$tmp/teste" >/dev/null 2>&1
  local r=$?
  rm -rf "$tmp"
  return $r
}

# --------------------------------------------------------------------- administrador
eh_administrador_sudo() {
  # O usuário pertence a um grupo que costuma ter sudo?
  command -v sudo >/dev/null 2>&1 || return 1
  id -nG 2>/dev/null | tr ' ' '\n' | grep -qxE 'sudo|wheel|admin'
}

como_admin() {
  # Executa um comando com permissão de administrador, escolhendo o melhor jeito.
  local comando="$1"
  if [ "$(id -u)" -eq 0 ]; then
    sh -c "$comando"
    return
  fi

  echo
  echo "${AMARELO}${NEGRITO}┌──────────────────────────────────────────────────────────────┐${FIM}"
  echo "${AMARELO}${NEGRITO}│  É PRECISO PERMISSÃO DE ADMINISTRADOR                        │${FIM}"
  echo "${AMARELO}${NEGRITO}└──────────────────────────────────────────────────────────────┘${FIM}"
  echo "  Para instalar: ${NEGRITO}${PACOTES}${FIM}"
  echo "  Comando: $comando"
  echo

  if eh_administrador_sudo; then
    echo "  Digite a SUA senha (sudo):"
    sudo sh -c "$comando" && return 0
    aviso "O sudo não funcionou. Tentando com a senha do root…"
  fi

  if command -v su >/dev/null 2>&1 && [ -t 0 ]; then
    echo "  Seu usuário não é administrador. Digite a senha do ${NEGRITO}root${FIM}:"
    su root -c "$comando" && return 0
    aviso "A senha do root não funcionou (ou o root está bloqueado)."
  fi

  if command -v pkexec >/dev/null 2>&1 && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
    echo "  Uma janela do sistema vai pedir a senha de administrador…"
    pkexec sh -c "$comando" && return 0
  fi

  return 1
}

COMANDO_INSTALACAO=""
instalar_python_do_sistema() {
  local comando
  if command -v apt-get >/dev/null 2>&1; then          # Debian, Ubuntu, Mint…
    PACOTES="python3 python3-venv"
    comando="apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y $PACOTES"
  elif command -v dnf >/dev/null 2>&1; then            # Fedora, RHEL…
    PACOTES="python3"
    comando="dnf install -y $PACOTES"
  elif command -v zypper >/dev/null 2>&1; then         # openSUSE
    PACOTES="python3"
    comando="zypper --non-interactive install $PACOTES"
  elif command -v pacman >/dev/null 2>&1; then         # Arch, Manjaro
    PACOTES="python"
    comando="pacman -Sy --noconfirm --needed $PACOTES"
  elif command -v apk >/dev/null 2>&1; then            # Alpine
    PACOTES="python3"
    comando="apk add --no-cache $PACOTES"
  elif command -v brew >/dev/null 2>&1; then           # macOS (Homebrew, sem admin)
    PACOTES="python"
    brew install python && return 0
    return 1
  else
    erro "Não reconheci o gerenciador de pacotes. Instale o Python ${VERSAO_MINIMA}+ manualmente."
  fi

  COMANDO_INSTALACAO="$comando"
  aviso "Python ${VERSAO_MINIMA}+ (com venv) não encontrado. Vou instalar: ${PACOTES}"
  como_admin "$comando"
}

# ===================================================================== início
echo "${NEGRITO}Instalador do Aprendiz${FIM}"

if [ "$(id -u)" -eq 0 ] && [ -n "${SUDO_USER:-}" ]; then
  aviso "Não é preciso usar sudo: o instalador pede a senha só quando precisa."
fi

info "Conferindo o Python"
if ! python_pronto; then
  if ! instalar_python_do_sistema; then
    erro "Não consegui permissão de administrador para instalar o Python.
  Peça a quem administra este computador para rodar:  ${COMANDO_INSTALACAO:-a instalação do python3 e python3-venv}"
  fi
  hash -r
  python_pronto || erro "O Python instalado não atende aos requisitos (precisa de ${VERSAO_MINIMA}+ com venv e SQLite/FTS5).
  Esta distribuição pode ser antiga demais."
fi
info "Usando $("$PYTHON" --version 2>&1) em $(command -v "$PYTHON")"

info "Criando ambiente virtual em .venv"
rm -rf .venv
"$PYTHON" -m venv .venv || erro "Não consegui criar o ambiente virtual."
VPY=".venv/bin/python"

info "Atualizando o pip"
"$VPY" -m pip install --upgrade pip --quiet --disable-pip-version-check || true

info "Baixando e instalando dependências"
"$VPY" -m pip install -r requirements.txt --quiet --disable-pip-version-check \
  || erro "Falha ao instalar as dependências. Verifique a conexão com a internet."

for opcao in "$@"; do
  case "$opcao" in
    --janela-nativa)
      info "Instalando suporte a janela nativa (pywebview)"
      "$VPY" -m pip install -r requirements/janela.txt --quiet --disable-pip-version-check ;;
    --dev)
      info "Instalando ferramentas de desenvolvimento"
      "$VPY" -m pip install -r requirements/dev.txt --quiet --disable-pip-version-check ;;
    *)
      aviso "Opção desconhecida ignorada: $opcao" ;;
  esac
done

info "Conferindo a instalação"
"$VPY" -c "import fastapi, uvicorn, rapidfuzz, aprendiz.core" \
  || erro "Algo deu errado na instalação das dependências."

# Se o instalador foi rodado como root (sudo ou su), devolve o .venv ao dono
# da pasta, para o usuário comum conseguir usar e atualizar.
if [ "$(id -u)" -eq 0 ]; then
  dono="$(stat -c %U . 2>/dev/null || echo root)"
  if [ "$dono" != "root" ]; then
    chown -R "$dono": .venv && info "Permissões do .venv devolvidas a $dono"
  fi
fi

chmod +x executar.sh distribuicao/empacotar.sh 2>/dev/null || true
echo
echo "${VERDE}✔ Instalação concluída!${FIM}"
echo "  Para abrir o Aprendiz:  bash executar.sh"
