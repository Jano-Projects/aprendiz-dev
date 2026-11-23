"""
Jeitos de ensinar vindos do addon de compreensão (2.6): a seção "ensino".

"a partir de agora a senha do wifi é x" e "anota aí: ..." viram ensino, como
"aprenda que..." e "anote: ..." já eram. Pergunta ("...?") nunca é ensino, e
uma palavra que só COMEÇA igual ao jeito de ensinar ("anotações") não conta.
"""

from __future__ import annotations

import pytest

from aprendiz.addons import pacote as pacotes
from aprendiz.addons import recursos
from aprendiz.linguagem import normalizar

from tests.test_compreensao import COMPREENSAO, manifesto

ENSINO = ["a partir de agora", "fica sabendo que", "anota ai", "anota", "não esquece que"]


@pytest.fixture
def com_ensino(assistente):
    assistente.instalar_addon(pacotes.criar_pacote(
        manifesto("compreensao-teste"),
        compreensao=recursos.validar_compreensao({**COMPREENSAO, "ensino": ENSINO}, normalizar)))
    return assistente


def _tipo(assistente, mensagem):
    return assistente.responder(mensagem)["mensagem"]["meta"].get("tipo")


def test_validacao_normaliza_e_e_opcional():
    saida = recursos.validar_compreensao({**COMPREENSAO, "ensino": ["Não esquece que"]},
                                         normalizar)
    assert saida["ensino"] == ["nao esquece que"]
    assert "ensino" not in recursos.validar_compreensao(COMPREENSAO, normalizar)


def test_validacao_recusa_lista_vazia():
    with pytest.raises(recursos.ErroRecurso):
        recursos.validar_compreensao({**COMPREENSAO, "ensino": "anota ai"}, normalizar)


@pytest.mark.parametrize("mensagem, formato", [
    ("A partir de agora a senha do wifi é casa456", "fato"),
    ("fica sabendo que o portão abre às 7h", "fato"),
    ("Anota aí: levar o carro na revisão em março", "nota"),
    ("anota, aí: comprar pilhas para o controle", "nota"),
    ("Não esquece que o lixo passa na terça", "nota"),
])
def test_jeitos_de_ensinar(com_ensino, mensagem, formato):
    r = com_ensino.responder(mensagem)["mensagem"]
    assert r["meta"]["tipo"] == "ensino"
    etapa = [e for e in r["meta"]["explicacao"]["etapas"] if e["nome"] == "Ensino"][0]
    assert etapa["dados"]["formato"] == formato


def test_fato_ensinado_responde(com_ensino):
    com_ensino.responder("a partir de agora a senha do wifi é casa456")
    r = com_ensino.responder("qual a senha do wifi")["mensagem"]
    assert "casa456" in r["texto"]


@pytest.mark.parametrize("mensagem", [
    "anota aí o que eu disse?",            # pergunta
    "Anotações do curso ficam na pasta",   # só começa igual
    "anota ai",                            # nada para guardar
])
def test_nao_e_ensino(com_ensino, mensagem):
    assert _tipo(com_ensino, mensagem) != "ensino"


def test_sem_addon_nada_muda(assistente):
    assert _tipo(assistente, "a partir de agora a senha do wifi é casa456") != "ensino"
    assert _tipo(assistente, "aprenda que a senha do wifi é casa123") == "ensino"
