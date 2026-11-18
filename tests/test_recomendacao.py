"""Testes da 0.5: recomendação de algoritmos, grupos de addons e as opções ao instalar."""

import base64

import pytest
from fastapi.testclient import TestClient

from aprendiz.addons import ErroAddon, chave_de_grupo, criar_pacote, ler_pacote
from aprendiz.api import criar_app
from aprendiz.core import exportacao
from aprendiz.core.recomendacao import perguntas_de_teste, recomendar, resposta_recomendada

PARES = [{"pergunta": f"horário da loja {n}", "conteudo": f"Abre às {n}h."} for n in range(6, 12)]


def addon(id_, recomendado=None, parametros=None, conhecimentos=PARES):
    manifesto = {"id": id_, "nome": id_.title(), "versao": "1.0.0"}
    if recomendado:
        manifesto["recomendado"] = recomendado
    return criar_pacote(manifesto, conhecimentos, parametros=parametros)


# ------------------------------------------------------------------ recomendação
def test_recomendar_testa_todos_os_algoritmos():
    r = recomendar(PARES)
    assert set(r["acertos"]) == {"bm25", "tfidf", "fuzzy", "hibrido"}
    assert r["busca"] in r["acertos"] and r["resposta"] == "direta"
    assert r["acerto"] == r["acertos"][r["busca"]] and r["perguntas"] >= len(PARES)


def test_empate_fica_com_o_mais_leve():
    r = recomendar([{"tipo": "verbete", "pergunta": "bué", "conteudo": "muito"}],
                   {"stopwords": ["significa"]})
    assert r["acertos"]["bm25"] == 1.0 and r["busca"] == "bm25"


def test_textos_longos_pedem_a_extrativa():
    longos = [{"tipo": "trecho", "conteudo": "Frase sobre o assunto. " * 30}] * 3
    assert resposta_recomendada(longos) == "extrativa"
    assert resposta_recomendada(PARES) == "direta"


def test_perguntas_de_teste():
    assert perguntas_de_teste({"tipo": "verbete", "pergunta": "kota", "conteudo": "x"}) == [
        "kota", "o que significa kota"]
    perguntas = perguntas_de_teste({"pergunta": "horário da farmácia", "conteudo": "8h"})
    assert perguntas[0] == "horário da farmácia" and len(perguntas) == 2  # + erro de digitação


def test_recomendar_sem_conhecimentos():
    assert recomendar([]) is None


# ------------------------------------------------------------------ formato
def test_manifesto_guarda_a_recomendacao():
    m = ler_pacote(addon("loja", {"busca": "tfidf", "resposta": "direta", "acerto": 0.9})).manifesto
    assert m["recomendado"] == {"busca": "tfidf", "resposta": "direta", "acerto": 0.9}


@pytest.mark.parametrize("recomendado, trecho", [
    ({"busca": "BM25!", "resposta": "direta"}, "nome de um algoritmo"),
    ({"busca": "bm25"}, "recomendado.resposta"),
    ({"busca": "bm25", "resposta": "direta", "acerto": 2}, "de 0 a 1"),
])
def test_recomendacao_invalida(recomendado, trecho):
    with pytest.raises(ErroAddon, match=trecho):
        addon("loja", recomendado)


def test_algoritmo_desconhecido_e_aceito_mas_marcado(assistente):
    info = assistente.inspecionar_addon(addon("loja", {"busca": "neural", "resposta": "direta"}))
    assert info["recomendado"]["disponivel"] is False
    assert "não existe nesta versão" in info["recomendado"]["titulo_busca"]


def test_chave_de_grupo():
    assert chave_de_grupo({"recomendado": {"busca": "bm25", "resposta": "direta"}}) == "bm25+direta"
    assert chave_de_grupo({}, {"busca.padrao": "fuzzy"}) == "fuzzy+direta"
    assert chave_de_grupo({}) is None


# ------------------------------------------------------------------ grupos
def test_grupos_e_ativacao_em_lote(assistente):
    bm25 = {"busca": "bm25", "resposta": "direta"}
    assistente.instalar_addon(addon("a-um", bm25))
    assistente.instalar_addon(addon("a-dois", bm25))
    assistente.instalar_addon(addon("b-um", {"busca": "tfidf", "resposta": "direta"}))
    assistente.instalar_addon(criar_pacote({"id": "tema", "nome": "Tema", "versao": "1.0.0"},
                                           personalizacao={"personalizacao.cor": "#0f766e"}))
    grupos = {g["chave"]: g for g in assistente.grupos_de_addons()}
    assert [a["id"] for a in grupos["bm25+direta"]["addons"]] == ["a-dois", "a-um"]
    assert grupos["bm25+direta"]["em_uso"] is True          # é o padrão de fábrica
    assert grupos[None]["titulo"] == "Sem recomendação"
    assert list(grupos)[-1] is None                          # "sem recomendação" por último

    assert assistente.definir_addons_ativos(["a-um", "a-dois", "nao-existe"], False) == 2
    assert assistente.definir_addons_ativos(["a-um", "a-dois"], False) == 0   # já estavam
    info = assistente.inspecionar_addon(addon("a-tres", bm25))
    assert {a["id"] for a in info["grupo"]["inativos"]} == {"a-um", "a-dois"}


def test_inspecionar_avisa_de_outros_padroes_ativos(assistente):
    assistente.instalar_addon(addon("b-um", {"busca": "tfidf", "resposta": "direta"}))
    info = assistente.inspecionar_addon(addon("a-um", {"busca": "bm25", "resposta": "direta"}))
    assert info["recomendado"]["ja_em_uso"] is True
    assert info["recomendado"]["outros_padroes_ativos"] == ["TF-IDF + cosseno · Direta"]


# ------------------------------------------------------------------ exportação
def test_exportacao_grava_a_recomendacao(assistente_ensinado):
    banco = assistente_ensinado.banco
    previa = exportacao.previa(banco)
    assert previa["recomendacao"]["busca"] in ("bm25", "tfidf", "fuzzy", "hibrido")
    ids = [k["id"] for k in previa["conhecimentos"] if k["marcado"]]

    _, dados = exportacao.exportar(banco, {"manifesto": {"nome": "Casa"}, "conhecimentos": ids})
    assert ler_pacote(dados).manifesto["recomendado"]["busca"] == previa["recomendacao"]["busca"]

    _, dados = exportacao.exportar(banco, {"manifesto": {"nome": "Casa"}, "conhecimentos": ids,
                                           "recomendado": {"busca": "hibrido", "resposta": "extrativa"}})
    rec = ler_pacote(dados).manifesto["recomendado"]
    assert rec["busca"] == "hibrido" and rec["resposta"] == "extrativa" and 0 <= rec["acerto"] <= 1

    with pytest.raises(ErroAddon, match="desconhecido"):
        exportacao.exportar(banco, {"manifesto": {"nome": "Casa"}, "conhecimentos": ids,
                                    "recomendado": {"busca": "magia"}})


# ------------------------------------------------------------------ API
def test_api_instalar_com_recomendacao_e_grupo(tmp_path):
    def corpo(dados, **opcoes):
        return {"nome_arquivo": "x.aprendiz", "conteudo_base64": base64.b64encode(dados).decode(),
                **opcoes}
    tfidf = {"busca": "tfidf", "resposta": "direta"}
    with TestClient(criar_app(tmp_path / "api.db")) as c:
        c.post("/api/addons", json=corpo(addon("t-um", tfidf)))
        c.post("/api/addons/grupo", json={"ids": ["t-um"], "ativo": False})
        r = c.post("/api/addons", json=corpo(addon("t-dois", tfidf),
                                              usar_recomendacao=True, ativar_grupo=True))
        assert r.status_code == 200
        config = {i["chave"]: i for i in c.get("/api/configuracoes").json()}
        assert config["busca.padrao"]["valor"] == "tfidf" and config["busca.padrao"]["origem"] == "dono"
        assert all(a["ativo"] for a in c.get("/api/addons").json())
        assert c.get("/api/addons/grupos").json()[0]["em_uso"] is True

        assert c.put("/api/padrao", json={"busca": "bm25", "resposta": "direta"}).status_code == 200
        assert c.put("/api/padrao", json={"busca": "x", "resposta": "direta"}).status_code == 400

        c.post("/api/conhecimentos", json={"pergunta": "horário da feira", "conteudo": "Domingo."})
        previa = c.get("/api/exportar").json()
        ids = [k["id"] for k in previa["conhecimentos"]]
        rec = c.post("/api/exportar/recomendar", json={"conhecimentos": ids}).json()
        assert rec["busca"] in rec["acertos"] and rec["titulo_busca"]


def test_algoritmos_padrao_vao_como_recomendacao_e_nao_como_parametro(assistente_ensinado):
    assistente_ensinado.usar_padrao("tfidf", "direta")
    assistente_ensinado.configuracoes.definir("limiar.bm25", 0.6)
    chaves = [c["chave"] for c in exportacao.previa(assistente_ensinado.banco)["parametros"]]
    assert chaves == ["limiar.bm25"]
