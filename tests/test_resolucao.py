"""Testes da junção de abreviações e sinônimos de vários addons (1.0)."""

import base64

from fastapi.testclient import TestClient

from aprendiz import addons as pacotes
from aprendiz.api import criar_app
from aprendiz.linguagem.resolucao import resolver


def test_conflito_entre_addons_nao_troca():
    mapa, conflitos = resolver([("banco", "assento", "A"), ("banco", "instituicao", "B")], {})
    assert "banco" not in mapa
    assert conflitos[0]["termo"] == "banco" and len(conflitos[0]["opcoes"]) == 2


def test_dono_resolve_conflito():
    mapa, conflitos = resolver([("banco", "assento", "A"), ("banco", "instituicao", "B")],
                               {"banco": "assento"})
    assert mapa["banco"] == "assento" and not conflitos


def test_mesmo_valor_em_dois_addons_nao_e_conflito():
    mapa, conflitos = resolver([("vc", "voce", "A"), ("vc", "voce", "B")], {})
    assert mapa == {"vc": "voce"} and not conflitos


def test_cadeia_e_ciclo():
    mapa, _ = resolver([("automovel", "carro", "A"), ("carro", "veiculo", "B")], {}, encadear=True)
    assert mapa == {"automovel": "veiculo", "carro": "veiculo"}
    mapa, _ = resolver([("a", "b", "A"), ("b", "a", "B")], {}, encadear=True)
    assert mapa == {"b": "a"}  # ciclo vira o menor termo; "a → a" é descartado


def _addon(id_, sinonimos):
    return pacotes.criar_pacote({"id": id_, "nome": id_, "versao": "1.0.0"},
                                linguagem={"sinonimos": sinonimos})


def test_addons_em_conflito_ficam_sem_troca(assistente):
    assistente.instalar_addon(_addon("addon-a", {"banco": "assento"}))
    assistente.instalar_addon(_addon("addon-b", {"banco": "instituicao"}))
    assert assistente.linguagem.processar("banco").tokens == ["banco"]
    assistente.banco.salvar_sinonimo("banco", "assento")  # o dono escolhe → passa a valer
    assert assistente.linguagem.processar("banco").tokens == ["assento"]


def test_api_mostra_conflitos_e_origem(tmp_path):
    with TestClient(criar_app(tmp_path / "api.db")) as cliente:
        for id_, valor in (("addon-a", "assento"), ("addon-b", "instituicao")):
            corpo = {"nome_arquivo": "x.aprendiz",
                     "conteudo_base64": base64.b64encode(_addon(id_, {"banco": valor})).decode()}
            assert cliente.post("/api/addons", json=corpo).status_code == 200
        dados = cliente.get("/api/linguagem").json()
        assert dados["conflitos"]["sinonimos"][0]["termo"] == "banco"
        assert {l["addon"] for l in dados["de_addons"]["sinonimos"]} == {"addon-a", "addon-b"}


def test_cadeia_entre_addons_encontra_conhecimento(assistente):
    assistente.instalar_addon(_addon("addon-a", {"automovel": "carro"}))
    assistente.instalar_addon(_addon("addon-b", {"carro": "veiculo"}))
    assistente.ensinar("Revisão a cada 10 mil km.", pergunta="manutenção do veículo")
    r = assistente.responder("manutenção do automóvel")["mensagem"]
    assert r["meta"]["tipo"] == "conhecimento"
