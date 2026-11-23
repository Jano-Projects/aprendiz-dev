"""Testes do formato 2: origem, classificação, versão do app, dependências e configurações."""

import io
import json
import zipfile

import pytest

from aprendiz import __version__
from aprendiz.addons.pacote import ErroAddon, comparar_versoes, criar_pacote, ler_pacote

BASE = {"id": "pacote-teste", "nome": "Pacote", "versao": "1.0.0"}
CONHECIMENTOS = [{"pergunta": "quantos ml tem uma xícara", "conteudo": "Cerca de 240 ml."}]


def zip_manual(arquivos: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for nome, conteudo in arquivos.items():
            z.writestr(nome, conteudo if isinstance(conteudo, str) else json.dumps(conteudo))
    return buffer.getvalue()


def manifesto2(**mudancas) -> dict:
    return {"formato": 2, **BASE, "origem": "terceiros", "classificacao": ["memoria"],
            "app": {"criado_com": "0.4.0", "versao_minima": "0.4.0"}, **mudancas}


# ------------------------------------------------------------------ formato
def test_criar_pacote_preenche_o_manifesto_v2():
    p = ler_pacote(criar_pacote(BASE, CONHECIMENTOS, parametros={"limiar.bm25": 0.6}))
    m = p.manifesto
    assert m["formato"] == 2 and m["origem"] == "terceiros"
    assert m["classificacao"] == ["memoria", "parametros"]
    assert m["app"] == {"criado_com": __version__, "versao_minima": __version__}
    assert p.parametros == {"limiar.bm25": 0.6}


def test_formato_1_continua_sendo_lido():
    dados = zip_manual({"manifesto.json": {"formato": 1, **BASE},
                        "conhecimentos.json": CONHECIMENTOS,
                        "linguagem.json": {"sinonimos": {"chicara": "xicara"}}})
    m = ler_pacote(dados).manifesto
    assert m["origem"] == "terceiros" and m["classificacao"] == ["memoria", "linguagem"]
    assert m["dependencias"] == []


def test_addon_so_de_personalizacao_nao_precisa_de_conhecimentos():
    p = ler_pacote(criar_pacote(BASE, personalizacao={"personalizacao.cor": "#0f766e"}))
    assert p.conhecimentos == [] and p.manifesto["classificacao"] == ["personalizacao"]


@pytest.mark.parametrize("arquivos, trecho", [
    ({"manifesto.json": manifesto2(classificacao=["algoritmo"])}, "só aceita addons de dados"),
    ({"manifesto.json": manifesto2(classificacao=["aplicacao"])}, "só aceita addons de dados"),
    ({"manifesto.json": manifesto2(classificacao=["magia"])}, "desconhecida"),
    ({"manifesto.json": manifesto2(classificacao=[])}, "pelo menos um tipo"),
    ({"manifesto.json": manifesto2(origem="jano")}, "oficial"),
    ({"manifesto.json": manifesto2(app={"versao_minima": "99.0"}),
      "conhecimentos.json": CONHECIMENTOS}, "precisa do Aprendiz 99.0"),
    ({"manifesto.json": manifesto2(classificacao=["memoria", "linguagem"]),
      "conhecimentos.json": CONHECIMENTOS}, "falta linguagem.json"),
    ({"manifesto.json": manifesto2(), "conhecimentos.json": CONHECIMENTOS,
      "parametros.json": {"limiar.bm25": 0.6}}, "não declara: parametros"),
    ({"manifesto.json": manifesto2(classificacao=["parametros"]),
      "parametros.json": {"limiar.bm25": 7}}, "entre"),
    ({"manifesto.json": manifesto2(classificacao=["parametros"]),
      "parametros.json": {"rodar.comando": "rm -rf /"}}, "não é uma configuração"),
    ({"manifesto.json": manifesto2(classificacao=["parametros"]),
      "parametros.json": {"personalizacao.cor": "#000000"}}, "não é uma configuração"),
    ({"manifesto.json": manifesto2(classificacao=["personalizacao"]),
      "personalizacao.json": {"personalizacao.cor": "red; background:url(x)"}}, "#RRGGBB"),
    ({"manifesto.json": manifesto2(dependencias=[{"id": "pacote-teste", "versao": "1"}]),
      "conhecimentos.json": CONHECIMENTOS}, "si mesmo"),
    ({"manifesto.json": manifesto2(dependencias=[{"id": "../x", "versao": "1"}]),
      "conhecimentos.json": CONHECIMENTOS}, "'id' inválido"),
])
def test_manifesto_v2_invalido_e_recusado(arquivos, trecho):
    with pytest.raises(ErroAddon, match=trecho):
        ler_pacote(zip_manual(arquivos))


def test_comparar_versoes():
    assert comparar_versoes("0.4", "0.4.0") == 0
    assert comparar_versoes("0.10.0", "0.9.9") == 1
    assert comparar_versoes("1.0.0", "1.0.1") == -1


# ------------------------------------------------------------------ instalação
def test_parametros_do_addon_valem_ate_o_dono_decidir(assistente):
    cfg = assistente.configuracoes
    assistente.instalar_addon(criar_pacote(
        {**BASE, "nome": "Exigente"}, CONHECIMENTOS,
        parametros={"limiar.bm25": 0.8}, personalizacao={"personalizacao.nome": "Jarbas"}))
    assert cfg.efetivas()["limiar.bm25"] == {
        "valor": 0.8, "origem": "addon", "addon_id": "pacote-teste", "addon_nome": "Exigente"}
    assert cfg.valor("personalizacao.nome") == "Jarbas"

    cfg.definir("limiar.bm25", 0.4)                 # o dono vence
    assert cfg.efetivas()["limiar.bm25"]["origem"] == "dono"
    cfg.remover("limiar.bm25")                      # e pode devolver ao addon
    assert cfg.valor("limiar.bm25") == 0.8

    assistente.definir_addon_ativo("pacote-teste", False)  # desativado não vale
    assert cfg.efetivas()["limiar.bm25"]["origem"] == "padrao"
    assistente.definir_addon_ativo("pacote-teste", True)
    assistente.remover_addon("pacote-teste")
    assert cfg.valor("personalizacao.nome") == "Aprendiz"


def test_limiar_configurado_muda_o_modo_estrito(assistente_ensinado):
    a = assistente_ensinado
    pergunta = "que horas abre a farmácia no sábado de manhã"
    a.configuracoes.definir("busca.padrao", "bm25")   # o limiar testado é o da BM25
    assert a.responder(pergunta)["mensagem"]["meta"]["tipo"] == "conhecimento"
    a.configuracoes.definir("limiar.bm25", 1.0)
    assert a.responder(pergunta)["mensagem"]["meta"]["tipo"] == "desconhecido"


def test_algoritmo_padrao_vem_das_configuracoes(assistente_ensinado):
    a = assistente_ensinado
    a.configuracoes.definir("busca.padrao", "tfidf")
    r = a.responder("senha do wifi")
    assert r["mensagem"]["meta"]["explicacao"]["algoritmo_busca"] == "tfidf"


def test_inspecionar_mostra_dependencias_e_nao_instala(assistente):
    assistente.instalar_addon(criar_pacote({**BASE, "id": "base-a", "versao": "1.0.0"},
                                           CONHECIMENTOS))
    dados = criar_pacote({**BASE, "dependencias": [
        {"id": "base-a", "versao": "2.0.0", "nome": "A"},
        {"id": "base-b", "versao": "1.0.0", "nome": "B"}]}, CONHECIMENTOS,
        parametros={"limiar.bm25": 0.6})
    assistente.configuracoes.definir("limiar.bm25", 0.5)
    info = assistente.inspecionar_addon(dados)
    assert [d["situacao"] for d in info["dependencias"]] == ["desatualizado", "ausente"]
    assert info["configuracoes"][0]["dono_ja_definiu"] is True
    assert info["origem_titulo"] == "Terceiros"
    assert assistente.banco.obter_addon("pacote-teste") is None


def test_reset_de_configuracoes(assistente):
    assistente.configuracoes.definir("personalizacao.nome", "Jarbas")
    assistente.banco.resetar(conhecimentos=False, linguagem=False, conversas=False,
                             addons=False, configuracoes=True)
    assert assistente.configuracoes.valor("personalizacao.nome") == "Aprendiz"


def test_addons_de_exemplo_sao_oficiais_e_v2(assistente):
    from pathlib import Path
    pasta = Path(__file__).resolve().parent.parent / "exemplos/addons"
    for nome in ("conversoes-medidas", "modo-exigente"):
        p = ler_pacote((pasta / f"{nome}.aprendiz").read_bytes())
        assert p.manifesto["origem"] == "oficial" and p.manifesto["editor"] == "Jano Projects"
    assistente.instalar_addon((pasta / "modo-exigente.aprendiz").read_bytes())
    assert assistente.configuracoes.efetivas()["limiar.bm25"]["origem"] == "addon"


def test_api_inspecionar(tmp_path):
    import base64
    from fastapi.testclient import TestClient
    from aprendiz.api import criar_app
    with TestClient(criar_app(tmp_path / "api.db")) as c:
        corpo = {"nome_arquivo": "x.aprendiz",
                 "conteudo_base64": base64.b64encode(criar_pacote(BASE, CONHECIMENTOS)).decode()}
        r = c.post("/api/addons/inspecionar", json=corpo)
        assert r.status_code == 200 and r.json()["totais"]["conhecimentos"] == 1
        assert c.get("/api/addons").json() == []          # inspecionar não instala
        corpo["conteudo_base64"] = base64.b64encode(b"lixo").decode()
        assert c.post("/api/addons/inspecionar", json=corpo).status_code == 400
