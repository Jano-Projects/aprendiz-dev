"""Testes do Monitor (2.4): etapas ao vivo, rota de fluxo e ficha do modelo."""

import json

from fastapi.testclient import TestClient

from aprendiz.api import criar_app
from aprendiz.core import monitor
from aprendiz.core.assistente import Etapas


def test_etapas_avisam_o_ouvinte_na_ordem():
    recebidas = []
    etapas = Etapas(recebidas.append)
    etapas.marcar("A", {"x": 1})
    etapas.marcar("B", {})
    assert [e["nome"] for e in recebidas] == ["A", "B"]
    assert [e["indice"] for e in recebidas] == [0, 1]
    assert recebidas[1]["inicio_ms"] >= recebidas[0]["inicio_ms"]
    assert etapas.lista[0]["dados"] == {"x": 1}


def test_responder_com_ouvinte_entrega_todas_as_etapas(assistente_ensinado):
    recebidas = []
    r = assistente_ensinado.responder("qual a senha do wifi?", ouvinte=recebidas.append)
    etapas = r["mensagem"]["meta"]["explicacao"]["etapas"]
    assert [e["nome"] for e in recebidas] == [e["nome"] for e in etapas]
    assert "memoria_mb" in r["mensagem"]["meta"]["explicacao"]


def test_rota_de_fluxo_envia_etapas_e_depois_o_fim(tmp_path):
    cliente = TestClient(criar_app(tmp_path / "fluxo.db"))
    cliente.post("/api/chat", json={"mensagem": "pergunta: senha do wifi resposta: casa123"})
    with cliente.stream("POST", "/api/chat/fluxo",
                        json={"mensagem": "qual a senha do wifi?", "busca": "calibrado"}) as r:
        assert r.headers["content-type"].startswith("application/x-ndjson")
        eventos = [json.loads(linha) for linha in r.iter_lines() if linha]
    assert eventos[-1]["evento"] == "fim"
    assert all(e["evento"] == "etapa" for e in eventos[:-1])
    assert any(e["nome"].startswith("Busca") for e in eventos[:-1])
    assert "casa123" in eventos[-1]["resposta"]["mensagem"]["texto"]


def test_rota_de_fluxo_avisa_erro(tmp_path):
    cliente = TestClient(criar_app(tmp_path / "fluxo.db"))
    with cliente.stream("POST", "/api/chat/fluxo",
                        json={"mensagem": "oi", "busca": "nao-existe"}) as r:
        eventos = [json.loads(linha) for linha in r.iter_lines() if linha]
    assert eventos == [{"evento": "erro", "mensagem": "Algoritmo de busca desconhecido: nao-existe"}]


def test_calibrado_entrega_a_conta_inteira_ao_monitor(assistente_ensinado):
    r = assistente_ensinado.responder("qual a senha do wifi?", busca="calibrado")
    busca = next(e for e in r["mensagem"]["meta"]["explicacao"]["etapas"]
                 if e["nome"].startswith("Busca"))
    d = busca["dados"]["candidatos"][0]["detalhes"]
    # z = viés + soma das contribuições (a mesma conta que o Monitor mostra)
    assert abs(d["z"] - (d["vies"] + sum(d["contribuicoes"].values()))) < 0.01
    assert set(d["contribuicoes"]) <= set(d["sinais"])
    assert set(d["decisao"]) == {"nota_do_primeiro", "distancia_do_segundo"}


def test_ficha_conta_os_parametros_por_tipo(assistente_ensinado):
    ficha = monitor.ficha_do_modelo(assistente_ensinado)
    nomes = {c["nome"] for c in ficha["componentes"]}
    assert {"Busca Calibrada · 1ª etapa", "Intenções", "TF-IDF", "BM25"} <= nomes
    assert ficha["total_parametros"] == sum(ficha["por_tipo"].values())
    assert ficha["total_parametros"] == sum(c["parametros"] for c in ficha["componentes"])
    assert {c["tipo"] for c in ficha["componentes"]} <= {
        "aprendido", "estatística", "pré-treinado", "hiperparâmetro"}
    calibrado = next(c for c in ficha["componentes"] if c["nome"] == "Busca Calibrada · 1ª etapa")
    assert calibrado["parametros"] == calibrado["detalhes"]["sinais"] + 1
    assert ficha["ambiente"]["aprendiz"]


def test_rota_do_modelo(tmp_path):
    cliente = TestClient(criar_app(tmp_path / "modelo.db"))
    dados = cliente.get("/api/modelo").json()
    assert dados["total_parametros"] > 0 and dados["componentes"]


def test_memoria_e_um_numero_ou_nada():
    m = monitor.memoria_mb()
    assert m is None or m > 0
