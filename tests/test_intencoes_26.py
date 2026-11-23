"""
Intenções com erro de escrita (2.6): uma palavra desconhecida vira a mais
parecida dos exemplos de intenção, se for MUITO parecida.
"""

from __future__ import annotations

import pytest

from aprendiz.linguagem.intencoes import corrigir_para_exemplos

VOCAB = {"obrigado": "obrig", "valeu": "val", "tchau": "tchau", "oi": "oi"}


def test_corrige_so_o_que_e_muito_parecido():
    assert corrigir_para_exemplos(["obrigadoo", "valew"], ["obrigado", "valew"], VOCAB) \
        == ["obrig", "val"]
    assert corrigir_para_exemplos(["astronomia"], ["astronom"], VOCAB) == ["astronom"]


def test_palavra_curta_e_palavra_conhecida_ficam():
    assert corrigir_para_exemplos(["oii"], ["oii"], VOCAB) == ["oii"]       # curta demais
    assert corrigir_para_exemplos(["tchau"], ["tchau"], VOCAB) == ["tchau"]


def test_palavra_gramatical_nao_e_corrigida():
    vocab = {**VOCAB, "uma": "uma"}
    assert corrigir_para_exemplos(["numa"], ["num"], vocab, {"numa", "uma"}) == ["num"]
    assert corrigir_para_exemplos(["numa"], ["num"], vocab) == ["uma"]   # sem a lista, corrigiria


def test_listas_desalinhadas_nao_mudam_nada():
    assert corrigir_para_exemplos(["a", "b"], ["a"], VOCAB) == ["a"]


# Sem addons: as sementes têm poucos exemplos de "valeu", então "valew" fica
# com chance baixa demais para virar resposta social. Com a Compreensão do
# português ativa (mais exemplos), ele passa. Aqui ficam os casos que as
# sementes sozinhas já cobrem.
@pytest.mark.parametrize("mensagem, intencao", [
    ("obrigadoo", "agradecimento"),
    ("tchauu", "despedida"),
])
def test_no_assistente(assistente, mensagem, intencao):
    r = assistente.responder(mensagem)["mensagem"]
    assert r["meta"]["tipo"] == "social"
    etapa = [e for e in r["meta"]["explicacao"]["etapas"] if e["nome"] == "Interpretação"][0]
    assert etapa["dados"]["intencoes"][0]["intencao"] == intencao


def test_assunto_novo_continua_desconhecido(assistente):
    assistente.ensinar("A senha do wifi é casa123.", pergunta="senha do wifi")
    assert assistente.responder("tem algo sobre astronomia?")["mensagem"]["meta"]["tipo"] \
        == "desconhecido"
