"""Testes da busca Calibrada (2.4): contas, pesos gravados e comportamento no pipeline."""

import math

import pytest

from aprendiz.algoritmos import BUSCAS, listar_algoritmos
from aprendiz.algoritmos.busca import calibrado_pesos
from aprendiz.algoritmos.busca.calibrado import (
    SINAIS_DA_DECISAO, chance_de_responder_certo, cobertura_idf, prever, sigmoide,
    sinais_da_decisao,
)


def test_sigmoide_e_estavel_nos_extremos():
    assert sigmoide(0) == 0.5
    assert sigmoide(800) == 1.0
    assert sigmoide(-800) == 0.0
    assert math.isclose(sigmoide(2) + sigmoide(-2), 1.0)


def test_cobertura_idf_pesa_o_termo_raro():
    idf = {"senh": 1.2, "wifi": 2.0}
    # "senha do banco": "banco" não existe na base e pesa o máximo (3,0).
    assert cobertura_idf(["senh", "banc"], {"senh", "wifi"}, idf, 3.0) == pytest.approx(1.2 / 4.2)
    # A cobertura simples daria 0,5; a ponderada é bem menor.
    assert cobertura_idf(["senh", "wifi"], {"senh", "wifi"}, idf, 3.0) == 1.0
    assert cobertura_idf([], {"senh"}, idf, 3.0) == 0.0


def test_prever_soma_os_sinais_padronizados():
    modelo = {"sinais": ["a", "b"], "media": [1.0, 0.0], "desvio": [2.0, 1.0],
              "pesos": [1.0, -2.0], "vies": 0.5}
    p, partes = prever({"a": 3.0, "b": 0.25}, modelo)
    # z = 0,5 + 1·(3 − 1)/2 − 2·(0,25 − 0)/1 = 1,0
    assert partes == {"a": 1.0, "b": -0.5}
    assert p == pytest.approx(sigmoide(1.0))


def test_decisao_cresce_com_a_distancia_para_o_segundo():
    modelo = {"decisao": {"sinais": list(SINAIS_DA_DECISAO), "pesos": [1.0, 1.0], "vies": 0.0}}
    destacado = chance_de_responder_certo([0.6, 0.05], modelo)
    empatado = chance_de_responder_certo([0.6, 0.58], modelo)
    assert destacado > empatado
    assert sinais_da_decisao([0.5]) [0] == pytest.approx(0.0)


def test_pesos_gravados_batem_com_os_sinais(assistente_ensinado):
    modelo = calibrado_pesos.MODELO
    n = len(modelo["sinais"])
    assert n and len(modelo["media"]) == len(modelo["desvio"]) == len(modelo["pesos"]) == n
    assert len(modelo["decisao"]["pesos"]) == len(SINAIS_DA_DECISAO)
    # Todo sinal que o modelo espera é medido pela busca (senão valeria a média).
    consulta = assistente_ensinado.linguagem.processar("qual a senha do wifi?")
    linhas = BUSCAS["calibrado"].sinais(consulta, assistente_ensinado.contexto)
    assert linhas and set(modelo["sinais"]) <= set(linhas[0][1])
    assert modelo["treino"]["perguntas_treino"] > 0


def test_aparece_no_seletor_e_nas_configuracoes(assistente):
    nomes = [a["nome"] for a in listar_algoritmos()["busca"]]
    assert "calibrado" in nomes
    efetivas = assistente.configuracoes.efetivas()
    assert efetivas["limiar.calibrado"]["valor"] == BUSCAS["calibrado"].limiar


def test_confianca_e_a_chance_de_o_primeiro_estar_certo(assistente_ensinado):
    consulta = assistente_ensinado.linguagem.processar("qual a senha do wifi?")
    candidatos = BUSCAS["calibrado"].buscar(consulta, assistente_ensinado.contexto)
    assert candidatos[0].conhecimento["pergunta"] == "senha do wifi"
    assert candidatos[0].confianca == candidatos[0].detalhes["chance_de_estar_certo"]
    assert all(c.confianca <= candidatos[0].confianca for c in candidatos)


def test_explicacao_mostra_os_sinais_que_mais_pesaram(assistente_ensinado):
    meta = assistente_ensinado.responder("qual a senha do wifi?", busca="calibrado")["mensagem"]["meta"]
    busca = next(e for e in meta["explicacao"]["etapas"] if e["nome"].startswith("Busca"))
    primeiro = busca["dados"]["candidatos"][0]
    assert "sinais_que_mais_pesaram" in str(primeiro)


def test_limiar_do_dono_vale(assistente_ensinado):
    assistente_ensinado.configuracoes.definir("limiar.calibrado", 1.0)
    r = assistente_ensinado.responder("qual a senha do wifi?", busca="calibrado")
    assert r["mensagem"]["meta"]["tipo"] == "desconhecido"


def test_pares_em_sequencia():
    from aprendiz.algoritmos.busca.calibrado import pares_em_sequencia
    assert pares_em_sequencia(["numer", "linh"], "us row numb numer linh rank") == 1.0
    assert pares_em_sequencia(["numer", "linh"], "numer de linh") == 0.0
    assert pares_em_sequencia(["numer", "linh", "result"], "numer linh x") == 0.5
    assert pares_em_sequencia(["numer"], "numer linh") == 0.0
