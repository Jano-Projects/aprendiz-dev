"""
Especificador que falta (2.7): "senha do BANCO" com só "senha do wifi" na
base vira resposta "incerto", com aviso, em vez de responder como se fosse
a mesma coisa.
"""

from __future__ import annotations

import pytest

from aprendiz.addons.pacote import criar_pacote


@pytest.fixture
def base(assistente):
    assistente.ensinar("A senha do wifi é girassol42.", pergunta="senha do wifi")
    assistente.ensinar("A conta de luz vence todo dia 10.", pergunta="vencimento da conta de luz")
    return assistente


def _msg(a, pergunta):
    return a.responder(pergunta, busca="bm25")["mensagem"]


def test_especificador_que_falta_vira_aviso(base):
    m = _msg(base, "qual a senha do banco?")
    assert m["meta"]["tipo"] == "incerto"
    assert m["texto"].startswith("Não tenho nada sobre **banco**")
    assert "girassol42" in m["texto"] and m["meta"]["fontes"]   # mostra o mais perto


def test_com_o_especificador_certo_responde_normal(base):
    m = _msg(base, "qual a senha do wifi?")
    assert m["meta"]["tipo"] == "conhecimento" and "girassol42" in m["texto"]


def test_aviso_usa_a_palavra_como_foi_escrita(base):
    assert "**água**" in _msg(base, "quando vence a conta de água?")["texto"]


def test_palavra_que_nao_especifica_e_ignorada(base):
    assert _msg(base, "a senha de cada wifi")["meta"]["tipo"] == "conhecimento"


def test_expressao_de_tempo_nao_especifica(assistente):
    assistente.ensinar("A farmácia abre às 8h de segunda a sábado.", pergunta="horário da farmácia")
    assert _msg(assistente, "que horas abre a farmácia no sábado de manhã")["meta"]["tipo"] \
        == "conhecimento"


def test_da_para_avaliar_resposta_incerta(base):
    m = _msg(base, "qual a senha do banco?")
    assert base.avaliar(m["id"], False)["avaliacao"] == "nao_util"


def test_em_addon_so_avisa_se_o_nucleo_esta_no_titulo(assistente):
    assistente.instalar_addon(criar_pacote(
        {"id": "bd", "nome": "BD", "versao": "1.0.0", "autor": "t"},
        [{"pergunta": "o que é join", "conteudo": "O JOIN junta duas tabelas pela chave."},
         {"pergunta": "o que é código limpo", "conteudo": "Código limpo é código fácil de ler."}],
        {}))
    # exemplo da pergunta ("produtos") não precisa estar no texto didático
    assert _msg(assistente, "juntar a tabela de produtos com join")["meta"]["tipo"] == "conhecimento"
    # "código" é o assunto do item, "alarme" não está nele
    assert _msg(assistente, "qual o código do alarme")["meta"]["tipo"] == "incerto"
