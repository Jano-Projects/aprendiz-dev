"""
Inicializador do app de desktop.

O Aprendiz é um servidor web local + uma interface HTML. Este módulo:

    1. sobe o servidor numa thread, em 127.0.0.1 (só este computador acessa);
    2. abre a interface como uma JANELA, tentando nesta ordem:

       a) janela nativa (pywebview), se estiver instalada:
          no Windows usa o Edge WebView2, que já vem com o sistema;
       b) "modo aplicativo" de um navegador Chromium (Chrome, Chromium, Edge,
          Brave): uma janela sem barra de endereço, parecida com um app.
          Usamos um perfil separado, então fechar a janela encerra o Aprendiz;
       c) o navegador padrão, numa aba comum (sempre funciona).

    3. encerra sozinho quando a interface é fechada. A página envia um
       "sinal de vida" a cada 10 s (POST /api/sinal); se os sinais param por
       90 s, o servidor sai. Isso evita processos esquecidos em segundo plano,
       principalmente no Windows, onde o executável não tem console.

Uso:
    python -m aprendiz                      # escolhe o melhor modo sozinho
    python -m aprendiz --modo navegador     # força abrir no navegador padrão
    python -m aprendiz --modo servidor      # só o servidor (acesse pelo navegador)
    python -m aprendiz --porta 9000
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from aprendiz import config
from aprendiz.api import criar_app

NAVEGADORES_CHROMIUM = [
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
    "microsoft-edge", "microsoft-edge-stable", "msedge", "brave-browser", "brave",
]

CAMINHOS_WINDOWS = [
    r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
]

CAMINHOS_MAC = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]


TEMPO_SEM_SINAL = 90       # segundos sem sinal da interface até encerrar
TEMPO_HANDOFF = 5          # janela "fechou" rápido demais? o navegador repassou o pedido


def preparar_saidas() -> None:
    """
    No executável do Windows gerado com --windowed não há console:
    sys.stdout e sys.stderr valem None, e qualquer biblioteca que tente
    escrever neles (o uvicorn, por exemplo) quebra. Apontamos para o "nada".
    """
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")


def log(mensagem: str) -> None:
    """print() seguro: no executável sem console, sys.stdout pode ser None."""
    if sys.stdout:
        print(f"[Aprendiz] {mensagem}", flush=True)


def escolher_porta(preferida: int) -> int:
    """Usa a porta preferida se estiver livre; senão, pede uma ao sistema."""
    for porta in (preferida, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # Mesma opção que o uvicorn usa: sem ela, conexões recém-fechadas
            # (estado TIME_WAIT) fariam a porta parecer ocupada no Linux/macOS.
            # No Windows a opção tem outro significado, então não a usamos lá.
            if not sys.platform.startswith("win"):
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", porta))
                return s.getsockname()[1]
            except OSError:
                continue
    raise RuntimeError("Nenhuma porta livre encontrada.")


def iniciar_servidor(porta: int):
    """Sobe o uvicorn numa thread e espera ele ficar pronto. Devolve (servidor, app)."""
    app = criar_app()
    cfg = uvicorn.Config(app, host="127.0.0.1", port=porta,
                         log_level="warning", access_log=False)
    servidor = uvicorn.Server(cfg)
    threading.Thread(target=servidor.run, daemon=True).start()

    limite = time.time() + 20
    while not servidor.started:
        if time.time() > limite:
            raise RuntimeError("O servidor demorou demais para iniciar.")
        time.sleep(0.05)
    return servidor, app


# ------------------------------------------------------------------ modos de janela
def abrir_janela_nativa(url: str) -> bool:
    """pywebview: bloqueia até a janela ser fechada. False se não estiver disponível."""
    try:
        import webview  # type: ignore
    except ImportError:
        return False
    try:
        webview.create_window(config.NOME_APP, url, width=1120, height=780, min_size=(380, 500))
        webview.start()
        return True
    except Exception as erro:  # sem backend gráfico, por exemplo
        log(f"Janela nativa indisponível ({erro}).")
        return False


def encontrar_chromium() -> str | None:
    for nome in NAVEGADORES_CHROMIUM:
        caminho = shutil.which(nome)
        if caminho:
            return caminho
    candidatos = CAMINHOS_WINDOWS if sys.platform.startswith("win") else (
        CAMINHOS_MAC if sys.platform == "darwin" else [])
    for c in candidatos:
        caminho = os.path.expandvars(c)
        if Path(caminho).exists():
            return caminho
    return None


def abrir_modo_app(url: str) -> bool | None:
    """
    Janela de navegador Chromium sem barras. Bloqueia até ser fechada.
    Retorna False (nenhum Chromium), True (janela fechada pelo usuário) ou
    None (o navegador repassou a janela a um processo já aberto).
    """
    exe = encontrar_chromium()
    if not exe:
        return False
    perfil = config.pasta_dados() / "perfil-janela"
    try:
        processo = subprocess.Popen(
            [exe, f"--app={url}", f"--user-data-dir={perfil}",
             "--window-size=1120,780", "--no-first-run", "--no-default-browser-check"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    log("Janela aberta. Feche a janela para encerrar o Aprendiz.")
    inicio = time.monotonic()
    processo.wait()
    # Se o navegador já estava aberto com esse perfil, o processo que lançamos
    # só repassa o pedido e termina na hora. Nesse caso, a janela continua
    # aberta e quem decide o encerramento é o sinal de vida.
    return time.monotonic() - inicio >= TEMPO_HANDOFF or None  # None = "repassou"


def esperar_ctrl_c() -> None:
    log("Pressione Ctrl+C para encerrar.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def esperar_interface(app) -> None:
    """
    Mantém o servidor vivo enquanto a interface estiver aberta.
    Sai com Ctrl+C ou quando os sinais de vida param por TEMPO_SEM_SINAL.
    """
    log("Feche a janela/aba (ou pressione Ctrl+C) para encerrar.")
    anterior = time.monotonic()
    try:
        while True:
            time.sleep(1)
            agora = time.monotonic()
            if agora - anterior > 10:
                # O computador provavelmente hibernou: não conta esse tempo.
                app.state.ultimo_sinal = agora if app.state.ultimo_sinal else None
            anterior = agora
            ultimo = app.state.ultimo_sinal
            if ultimo is not None and agora - ultimo > TEMPO_SEM_SINAL:
                log("Interface fechada.")
                return
    except KeyboardInterrupt:
        pass


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="aprendiz", description="Assistente pessoal local.")
    parser.add_argument("--porta", type=int, default=config.PORTA_PADRAO)
    parser.add_argument("--modo", choices=["auto", "janela", "app", "navegador", "servidor"],
                        default="auto", help="como abrir a interface (padrão: auto)")
    args = parser.parse_args(argv)

    preparar_saidas()
    porta = escolher_porta(args.porta)
    servidor, app = iniciar_servidor(porta)
    url = f"http://127.0.0.1:{porta}/"
    log(f"Servidor em {url}  ·  dados em {config.pasta_dados()}")

    try:
        if args.modo == "servidor":
            esperar_ctrl_c()
        elif args.modo == "navegador":
            webbrowser.open(url)
            esperar_interface(app)
        elif args.modo == "janela":
            if not abrir_janela_nativa(url):
                log("pywebview não instalado. Rode o instalador com --janela-nativa.")
        elif args.modo == "app":
            resultado = abrir_modo_app(url)
            if resultado is False:
                log("Nenhum navegador Chromium encontrado.")
            elif resultado is None:
                esperar_interface(app)
        else:  # auto
            if abrir_janela_nativa(url):
                pass
            else:
                resultado = abrir_modo_app(url)
                if resultado is None:
                    esperar_interface(app)
                elif resultado is False:
                    webbrowser.open(url)
                    esperar_interface(app)
    finally:
        servidor.should_exit = True
        log("Até logo!")


if __name__ == "__main__":
    main()
