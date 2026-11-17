"""
Configurações globais do Aprendiz.

Aqui ficam apenas valores que mudam pouco: nome do app, porta padrão e,
principalmente, ONDE os dados do usuário são guardados.

Os dados nunca ficam dentro da pasta do programa. Assim, ao atualizar ou
reinstalar o Aprendiz, o conhecimento ensinado continua intacto.
Cada sistema operacional tem uma pasta "oficial" para dados de aplicativos:

    Linux   → ~/.local/share/aprendiz          (padrão XDG)
    Windows → %APPDATA%\\Aprendiz
    macOS   → ~/Library/Application Support/Aprendiz

Para testes ou para usar um "perfil" diferente, defina a variável de
ambiente APRENDIZ_DADOS apontando para outra pasta.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from aprendiz import __version__

NOME_APP = "Aprendiz"
VERSAO = __version__

# Porta preferida do servidor local. Se estiver ocupada, outra é escolhida.
PORTA_PADRAO = 8765

# Pasta com os arquivos da interface (index.html, estilo.css, app.js...).
# Usamos o caminho relativo a este arquivo para funcionar tanto rodando o
# código-fonte quanto dentro do executável gerado pelo PyInstaller.
PASTA_WEB = Path(__file__).resolve().parent / "web"


def pasta_dados() -> Path:
    """Retorna (e cria, se preciso) a pasta onde os dados do usuário ficam."""
    personalizada = os.environ.get("APRENDIZ_DADOS")
    if personalizada:
        pasta = Path(personalizada)
    elif sys.platform.startswith("win"):
        pasta = Path(os.environ.get("APPDATA", Path.home())) / NOME_APP
    elif sys.platform == "darwin":
        pasta = Path.home() / "Library" / "Application Support" / NOME_APP
    else:
        base = os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
        pasta = Path(base) / "aprendiz"

    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def caminho_banco() -> Path:
    """Caminho do arquivo SQLite que guarda TODA a memória do assistente."""
    return pasta_dados() / "aprendiz.db"
