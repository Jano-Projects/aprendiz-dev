"""Testes da API HTTP (o mesmo caminho que a interface usa)."""

import pytest
from fastapi.testclient import TestClient

from aprendiz.api import criar_app


@pytest.fixture
def cliente(tmp_path):
    with TestClient(criar_app(tmp_path / "api.db")) as c:
        yield c


def test_interface_e_status(cliente):
    assert cliente.get("/").status_code == 200
    assert cliente.get("/static/app.js").status_code == 200
    assert cliente.get("/api/status").json()["conhecimentos"] == 0


def test_algoritmos(cliente):
    dados = cliente.get("/api/algoritmos").json()
    assert dados["busca"][0]["nome"] == "bm25"
    assert {a["nome"] for a in dados["resposta"]} == {"direta", "extrativa"}


def test_fluxo_completo(cliente):
    cliente.post("/api/conhecimentos", json={"pergunta": "dia do lixo", "conteudo": "Terças e sextas."})

    r = cliente.post("/api/chat", json={"mensagem": "qual o dia do lixo?"}).json()
    assert r["mensagem"]["texto"] == "Terças e sextas."
    conversa = r["conversa_id"]

    # Segunda mensagem na mesma conversa
    r2 = cliente.post("/api/chat", json={"mensagem": "oi", "conversa_id": conversa}).json()
    assert r2["conversa_id"] == conversa
    assert len(cliente.get(f"/api/conversas/{conversa}/mensagens").json()) == 4

    # Correção
    cliente.post("/api/corrigir", json={"mensagem_id": r["mensagem"]["id"],
                                        "resposta_correta": "Só às sextas."})
    r3 = cliente.post("/api/chat", json={"mensagem": "qual o dia do lixo?"}).json()
    assert r3["mensagem"]["texto"] == "Só às sextas."

    # Apagar conversa
    cliente.delete(f"/api/conversas/{conversa}")
    assert all(c["id"] != conversa for c in cliente.get("/api/conversas").json())


def test_algoritmo_invalido(cliente):
    r = cliente.post("/api/chat", json={"mensagem": "oi", "busca": "nao-existe"})
    assert r.status_code == 400


def test_linguagem(cliente):
    r = cliente.post("/api/linguagem/sinonimos", json={"termo": "Bike", "valor": "Bicicleta"})
    assert r.status_code == 200
    termos = {s["termo"] for s in cliente.get("/api/linguagem").json()["sinonimos"]}
    assert "bike" in termos
    cliente.delete("/api/linguagem/sinonimos/bike")
    termos = {s["termo"] for s in cliente.get("/api/linguagem").json()["sinonimos"]}
    assert "bike" not in termos


def test_importar(cliente):
    r = cliente.post("/api/importar", json={"nome": "a.md", "texto": "Um.\n\nDois."})
    assert r.json()["trechos"] == 1
    assert cliente.post("/api/importar", json={"nome": "a.pdf", "texto": "x"}).status_code == 400


def test_resetar_volta_ao_estado_inicial(cliente, tmp_path):
    padrao = cliente.get("/api/linguagem").json()
    cliente.post("/api/conhecimentos", json={"pergunta": "segredo", "conteudo": "42"})
    cliente.post("/api/chat", json={"mensagem": "qual o segredo?"})
    cliente.post("/api/linguagem/sinonimos", json={"termo": "bike", "valor": "bicicleta"})

    # Sem a palavra de confirmação, nada acontece.
    assert cliente.post("/api/resetar", json={"confirmacao": "sim"}).status_code == 400
    assert cliente.get("/api/status").json()["conhecimentos"] == 1

    r = cliente.post("/api/resetar", json={"confirmacao": "RESETAR"}).json()
    assert r["apagados"]["conhecimentos"] == 1

    status = cliente.get("/api/status").json()
    assert status["conhecimentos"] == 0 and status["conversas"] == 0
    def sem_ids(ling):
        ling["intencoes"] = [(i["termo"], i["valor"]) for i in ling["intencoes"]]
        return ling
    assert sem_ids(cliente.get("/api/linguagem").json()) == sem_ids(padrao)  # "bike" sumiu

    # O backup existe e guarda o que foi apagado.
    import sqlite3
    copia = sqlite3.connect(r["backup"])
    assert copia.execute("SELECT conteudo FROM conhecimentos").fetchone()[0] == "42"
    copia.close()

    # Depois do reset, o assistente volta a funcionar normalmente.
    assert cliente.post("/api/chat", json={"mensagem": "oi"}).json()["mensagem"]["meta"]["tipo"] == "social"
    assert cliente.post("/api/chat", json={"mensagem": "qual o segredo?"}).json()["mensagem"]["meta"]["tipo"] == "desconhecido"


def test_resetar_parcial_mantem_conversas(cliente):
    cliente.post("/api/conhecimentos", json={"pergunta": "a", "conteudo": "b"})
    cliente.post("/api/chat", json={"mensagem": "oi"})
    cliente.post("/api/resetar", json={"confirmacao": "RESETAR", "conversas": False, "linguagem": False})
    status = cliente.get("/api/status").json()
    assert status["conhecimentos"] == 0 and status["conversas"] == 1
