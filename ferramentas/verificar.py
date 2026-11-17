"""
Verificador de instalação do Aprendiz.

Confere, em qualquer sistema, se tudo está pronto para funcionar:

    1. versão do Python (3.10+)
    2. SQLite com FTS5 (busca textual)
    3. dependências instaladas
    4. o servidor sobe, responde e o chat funciona de ponta a ponta

Uso (de dentro da pasta do projeto):
    Linux/macOS:  .venv/bin/python ferramentas/verificar.py
    Windows:      .venv\\Scripts\\python ferramentas\\verificar.py

Para testar o executável gerado pelo PyInstaller:
    python ferramentas/verificar.py --executavel dist/Aprendiz/Aprendiz

O teste usa uma pasta de dados temporária: não toca na sua memória real.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
falhas = 0


def ok(texto: str) -> None:
    print(f"  [ok]    {texto}")


def falha(texto: str) -> None:
    global falhas
    falhas += 1
    print(f"  [FALHA] {texto}")


def porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def requisicao(url: str, dados: dict | None = None) -> dict:
    corpo = json.dumps(dados).encode() if dados is not None else None
    pedido = urllib.request.Request(url, data=corpo, method="POST" if corpo else "GET",
                                    headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(pedido, timeout=10) as r:
        return json.loads(r.read().decode())


def verificar_ambiente() -> None:
    print("Ambiente")
    v = sys.version_info
    if v >= (3, 10):
        ok(f"Python {v.major}.{v.minor}.{v.micro} ({sys.platform})")
    else:
        falha(f"Python {v.major}.{v.minor}: é preciso 3.10 ou mais novo")

    try:
        sqlite3.connect(":memory:").execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        ok(f"SQLite {sqlite3.sqlite_version} com FTS5")
    except sqlite3.OperationalError:
        falha("o SQLite deste Python não tem FTS5")

    for modulo in ("fastapi", "uvicorn", "rapidfuzz"):
        try:
            m = __import__(modulo)
            ok(f"{modulo} {getattr(m, '__version__', '')}")
        except ImportError:
            falha(f"{modulo} não instalado (rode o instalador)")


def verificar_servidor(comando: list[str]) -> None:
    print("Servidor e chat")
    porta = porta_livre()
    base = f"http://127.0.0.1:{porta}"
    ambiente = dict(os.environ, APRENDIZ_DADOS=tempfile.mkdtemp(prefix="aprendiz-verif-"))
    processo = subprocess.Popen(comando + ["--modo", "servidor", "--porta", str(porta)],
                                cwd=RAIZ, env=ambiente,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        limite = time.time() + 60  # o executável pode demorar a descompactar
        while True:
            try:
                status = requisicao(base + "/api/status")
                break
            except OSError:
                if processo.poll() is not None:
                    falha(f"o servidor terminou sozinho (código {processo.returncode})")
                    return
                if time.time() > limite:
                    falha("o servidor não respondeu em 60 s")
                    return
                time.sleep(0.5)
        ok(f"servidor respondeu (versão {status['versao']})")

        with urllib.request.urlopen(base + "/", timeout=10) as r:
            (ok if b"Aprendiz" in r.read() else falha)("interface carregada")

        requisicao(base + "/api/chat", {"mensagem": "aprenda que a senha do wifi é casa123"})
        r = requisicao(base + "/api/chat", {"mensagem": "vc sabe a senha do wi fi?",
                                            "busca": "hibrido"})
        texto = r["mensagem"]["texto"]
        (ok if "casa123" in texto else falha)(f"chat ensinou e respondeu: {texto!r}")

        r = requisicao(base + "/api/chat", {"mensagem": "qual a capital da França?"})
        (ok if r["mensagem"]["meta"]["tipo"] == "desconhecido" else falha)(
            "modo estrito (não inventa resposta)")
    finally:
        processo.terminate()
        try:
            processo.wait(timeout=10)
        except subprocess.TimeoutExpired:
            processo.kill()


def main() -> None:
    parser = argparse.ArgumentParser(description="Verifica a instalação do Aprendiz.")
    parser.add_argument("--executavel", help="testa o executável do PyInstaller em vez do código-fonte")
    args = parser.parse_args()

    if args.executavel:
        comando = [str(Path(args.executavel).resolve())]
    else:
        verificar_ambiente()
        comando = [sys.executable, "-m", "aprendiz"]
    verificar_servidor(comando)

    print()
    if falhas:
        print(f"[X] {falhas} problema(s) encontrado(s).")
        sys.exit(1)
    print("[OK] Tudo certo! O Aprendiz está pronto para usar.")


if __name__ == "__main__":
    main()
