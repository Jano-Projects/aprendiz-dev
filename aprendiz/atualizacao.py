"""
Atualização sob pedido (2.2): o app e os addons da loja oficial.

É um GATILHO: nada acontece sozinho. Só quando o dono pede ("verifique e
atualize", ou o botão em Configurações) o app acessa a internet, e só os
endereços oficiais (config.URL_LOJA_OFICIAL e a API de releases do GitHub do
aprendiz-dev). Nenhum endereço vem da requisição.

    verificar()            → o que há de novo: addons instalados com versão
                             maior no catálogo e a última versão do app
    atualizar_addons(ids)  → baixa cada .aprendiz, confere o SHA-256 do
                             catálogo e instala pelo caminho de sempre
                             (Assistente.instalar_addon valida tudo)
    atualizar_app()        → instalação pelo código (pasta com .git): git pull
                             + dependências, e pede para reiniciar. Executável:
                             devolve a página da release para baixar.

Os dados ficam fora da pasta do programa (config.py), então atualizar o app
não mexe na memória.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any, Callable

from aprendiz import __version__, config
from aprendiz.addons import comparar_versoes

URL_RELEASE = "https://api.github.com/repos/Jano-Projects/aprendiz-dev/releases/latest"
PAGINA_RELEASES = "https://github.com/Jano-Projects/aprendiz-dev/releases/latest"
TEMPO_LIMITE = 20
PASTA_APP = Path(__file__).resolve().parent.parent

Baixar = Callable[[str], bytes]


def baixar(url: str) -> bytes:
    pedido = urllib.request.Request(url, headers={"User-Agent": f"Aprendiz/{__version__}"})
    with urllib.request.urlopen(pedido, timeout=TEMPO_LIMITE) as resposta:  # noqa: S310
        return resposta.read()


class ErroAtualizacao(Exception):
    pass


class Atualizador:
    def __init__(self, assistente, baixar: Baixar = baixar) -> None:
        self.assistente = assistente
        self._baixar = baixar
        self._catalogo: dict[str, dict] = {}

    # ------------------------------------------------------------ verificar
    def verificar(self) -> dict[str, Any]:
        try:
            catalogo = json.loads(self._baixar(config.URL_LOJA_OFICIAL + "catalogo.json"))
        except Exception as erro:  # rede, JSON
            raise ErroAtualizacao(f"Não consegui ler o catálogo da loja oficial ({erro}).") from erro
        self._catalogo = {a["id"]: a for a in catalogo.get("addons", []) if a.get("id")}
        addons = []
        for instalado in self.assistente.banco.listar_addons():
            novo = self._catalogo.get(instalado["id"])
            if novo and comparar_versoes(novo["versao"], instalado["versao"]) > 0:
                addons.append({"id": instalado["id"], "nome": instalado.get("nome") or novo.get("nome"),
                               "de": instalado["versao"], "para": novo["versao"]})
        return {"addons": addons, "app": self._versao_app()}

    def _versao_app(self) -> dict[str, Any]:
        app = {"atual": __version__, "ultima": None, "nova": False, "como": self.como_atualizar(),
               "pagina": PAGINA_RELEASES}
        try:
            ultima = json.loads(self._baixar(URL_RELEASE)).get("tag_name", "").lstrip("v")
        except Exception:
            return app   # sem release publicada ou sem rede: os addons ainda valem
        if ultima:
            app["ultima"] = ultima
            app["nova"] = comparar_versoes(ultima, __version__) > 0
        return app

    @staticmethod
    def como_atualizar() -> str:
        """'codigo' (pasta com .git e git instalado) ou 'executavel' (baixar a release)."""
        if getattr(sys, "frozen", False):
            return "executavel"
        return "codigo" if (PASTA_APP / ".git").exists() and shutil.which("git") else "executavel"

    # ------------------------------------------------------------ addons
    def atualizar_addons(self, ids: list[str] | None = None) -> list[dict[str, Any]]:
        pendentes = self.verificar()["addons"]
        resultado = []
        for item in pendentes:
            if ids is not None and item["id"] not in ids:
                continue
            novo = self._catalogo[item["id"]]
            try:
                dados = self._baixar(config.URL_LOJA_OFICIAL + novo["arquivo"])
                if hashlib.sha256(dados).hexdigest() != novo.get("sha256"):
                    raise ErroAtualizacao("o arquivo baixado não confere com o SHA-256 da loja")
                self.assistente.instalar_addon(dados)
                resultado.append({**item, "ok": True})
            except Exception as erro:  # um addon com problema não impede os outros
                resultado.append({**item, "ok": False, "erro": str(erro)})
        return resultado

    # ------------------------------------------------------------ app
    def atualizar_app(self) -> dict[str, Any]:
        if self.como_atualizar() != "codigo":
            return {"ok": False, "reiniciar": False, "pagina": PAGINA_RELEASES,
                    "mensagem": "Este Aprendiz é um executável: baixe a versão nova na página "
                                "de releases e instale por cima (seus dados ficam onde estão)."}
        passos = [["git", "-C", str(PASTA_APP), "pull", "--ff-only"]]
        requisitos = PASTA_APP / "requirements.txt"
        if requisitos.exists():
            passos.append([sys.executable, "-m", "pip", "install", "-q", "-r", str(requisitos)])
        for passo in passos:
            r = subprocess.run(passo, capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                return {"ok": False, "reiniciar": False,
                        "mensagem": f"Falhou em `{' '.join(passo[:4])}`: {(r.stderr or r.stdout).strip()[:300]}"}
        return {"ok": True, "reiniciar": True,
                "mensagem": "Código atualizado. Feche e abra o Aprendiz para usar a versão nova."}
