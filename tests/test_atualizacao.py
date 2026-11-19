"""Atualização sob pedido (2.2): só com o gatilho, com SHA-256 conferido. Sem rede: baixar falso."""

import hashlib
import json

import pytest

from aprendiz import config
from aprendiz.addons import criar_pacote
from aprendiz.atualizacao import Atualizador
from aprendiz.core.assistente import _pedido_atualizacao

MANIFESTO = {"id": "teste-loja", "nome": "Teste da loja", "autor": "Teste"}
ITENS = [{"pergunta": "qual a cor do ceu", "conteudo": "Azul.", "tipo": "pergunta"}]


@pytest.mark.parametrize("frase, esperado", [
    ("verifique e atualize", "aplicar"), ("atualize", "aplicar"), ("atualize tudo", "aplicar"),
    ("Verifique atualizações", "verificar"), ("verificar se há atualizações", "verificar"),
    ("como atualizar o ubuntu pelo terminal", None), ("atualizar dados em sql", None),
])
def test_gatilho(frase, esperado):
    assert _pedido_atualizacao(frase) == esperado


def loja(versao, sha=None):
    novo = criar_pacote({**MANIFESTO, "versao": versao}, ITENS, {})
    catalogo = {"addons": [{"id": "teste-loja", "nome": "Teste da loja", "versao": versao,
                            "arquivo": "addons/teste-loja.aprendiz",
                            "sha256": sha or hashlib.sha256(novo).hexdigest()}]}
    arquivos = {config.URL_LOJA_OFICIAL + "catalogo.json": json.dumps(catalogo).encode(),
                config.URL_LOJA_OFICIAL + "addons/teste-loja.aprendiz": novo}

    def baixar(url):
        if url not in arquivos:
            raise OSError("sem rede")
        return arquivos[url]
    return baixar


@pytest.fixture
def com_addon(assistente):
    assistente.instalar_addon(criar_pacote({**MANIFESTO, "versao": "1.0.0"}, ITENS, {}))
    return assistente


def versao(assistente):
    return next(a["versao"] for a in assistente.banco.listar_addons() if a["id"] == "teste-loja")


def test_verificar_nao_instala(com_addon):
    com_addon.atualizador = Atualizador(com_addon, loja("1.1.0"))
    texto = com_addon.responder("verifique atualizações")["mensagem"]["texto"]
    assert "1.0.0 → 1.1.0" in texto and "atualize" in texto
    assert versao(com_addon) == "1.0.0"


def test_atualize_instala_o_addon_novo(com_addon):
    com_addon.atualizador = Atualizador(com_addon, loja("1.1.0"))
    texto = com_addon.responder("verifique e atualize")["mensagem"]["texto"]
    assert "atualizado" in texto and versao(com_addon) == "1.1.0"


def test_sha256_diferente_nao_instala(com_addon):
    com_addon.atualizador = Atualizador(com_addon, loja("1.1.0", sha="0" * 64))
    texto = com_addon.responder("atualize")["mensagem"]["texto"]
    assert "SHA-256" in texto and versao(com_addon) == "1.0.0"
