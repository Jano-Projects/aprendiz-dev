"""Testes da exportação: prévia com avisos de privacidade, escolha de itens e ida e volta."""

import pytest
from fastapi.testclient import TestClient

from aprendiz.addons.pacote import ErroAddon, criar_pacote, ler_pacote
from aprendiz.api import criar_app
from aprendiz.addons import exportacao

DEP = {"id": "conversoes", "nome": "Conversões", "versao": "1.2.0"}


def ids(previa, marcados=True):
    return [k["id"] for k in previa["conhecimentos"] if k["marcado"] == marcados]


@pytest.mark.parametrize("texto, motivo", [
    ("A senha do wifi é casa123.", "senha"),
    ("Meu e-mail é fulano@exemplo.org", "email"),
    ("Ligar para (11) 98765-4321", "telefone"),
    ("CPF 123.456.789-00", "cpf"),
    ("Protocolo 9876543210", "número longo"),
])
def test_avisos_de_privacidade(texto, motivo):
    assert motivo in exportacao.avisos_privacidade(texto)


def test_texto_comum_nao_gera_aviso():
    assert exportacao.avisos_privacidade("A farmácia abre às 8h, de segunda a sábado.") == []


def test_previa_desmarca_o_que_parece_pessoal(assistente_ensinado):
    previa = exportacao.previa(assistente_ensinado.banco)
    assert len(previa["conhecimentos"]) == 4          # só o que o dono ensinou
    desmarcados = [k for k in previa["conhecimentos"] if not k["marcado"]]
    assert [k["pergunta"] for k in desmarcados] == ["senha do wifi"]


def test_previa_lista_so_a_linguagem_e_configuracoes_do_dono(assistente):
    previa = exportacao.previa(assistente.banco)
    assert previa["linguagem"] == {"abreviacoes": [], "sinonimos": []}  # sementes ficam fora
    assert previa["parametros"] == [] and previa["personalizacao"] == []

    assistente.banco.salvar_sinonimo("geladeira", "refrigerador")
    assistente.configuracoes.definir("personalizacao.nome", "Jarbas")
    previa = exportacao.previa(assistente.banco)
    assert previa["linguagem"]["sinonimos"] == [{"termo": "geladeira", "valor": "refrigerador"}]
    assert previa["personalizacao"][0]["valor"] == "Jarbas"


def test_exportar_e_importar_em_outro_aprendiz(assistente_ensinado, tmp_path):
    a = assistente_ensinado
    a.instalar_addon(criar_pacote(DEP, [{"pergunta": "1 pol", "conteudo": "2,54 cm"}]))
    a.banco.salvar_sinonimo("geladeira", "refrigerador")
    a.configuracoes.definir("limiar.bm25", 0.6)
    previa = exportacao.previa(a.banco)

    nome, dados = exportacao.exportar(a.banco, {
        "manifesto": {"nome": "Minha Casa", "autor": "Dono", "descricao": "Coisas de casa"},
        "conhecimentos": ids(previa),
        "sinonimos": ["geladeira"],
        "parametros": ["limiar.bm25"],
        "dependencias": ["conversoes"],
    })
    assert nome == "minha-casa.aprendiz"
    p = ler_pacote(dados)
    m = p.manifesto
    assert m["origem"] == "terceiros" and m["versao"] == "1.0.0"
    assert m["classificacao"] == ["memoria", "linguagem", "parametros"]
    assert m["dependencias"] == [DEP | {"versao": "1.2.0"}]
    assert m["app"]["criado_com"] == m["app"]["versao_minima"]
    assert len(p.conhecimentos) == 3                     # a senha ficou de fora
    assert not any("casa123" in k["conteudo"] for k in p.conhecimentos)
    assert "2,54 cm" not in str(p.conhecimentos)        # conteúdo do addon NÃO é copiado
    assert p.parametros == {"limiar.bm25": 0.6}


def test_exportacao_nunca_se_declara_oficial(assistente_ensinado):
    previa = exportacao.previa(assistente_ensinado.banco)
    _, dados = exportacao.exportar(assistente_ensinado.banco, {
        "manifesto": {"id": "x-oficial", "nome": "X", "origem": "oficial",
                      "editor": "Jano Projects"},
        "conhecimentos": ids(previa)})
    m = ler_pacote(dados).manifesto
    assert m["origem"] == "terceiros" and m["editor"] is None


def test_exportar_sem_itens_e_recusado(assistente):
    with pytest.raises(ErroAddon, match="pelo menos um item"):
        exportacao.exportar(assistente.banco, {"manifesto": {"nome": "Vazio"}})


def test_api_de_exportacao_e_configuracoes(tmp_path):
    with TestClient(criar_app(tmp_path / "api.db")) as c:
        c.post("/api/conhecimentos", json={"pergunta": "horário da feira",
                                           "conteudo": "Domingo, das 7h às 13h."})
        previa = c.get("/api/exportar").json()
        r = c.post("/api/exportar", json={"manifesto": {"nome": "Feira"},
                                          "conhecimentos": ids(previa)})
        assert r.status_code == 200
        assert r.headers["content-disposition"].endswith('"feira.aprendiz"')
        assert ler_pacote(r.content).manifesto["nome"] == "Feira"
        assert c.post("/api/exportar", json={"manifesto": {"nome": "Feira"}}).status_code == 400

        assert c.put("/api/configuracoes/limiar.bm25", json={"valor": 0.7}).status_code == 200
        lista = {i["chave"]: i for i in c.get("/api/configuracoes").json()}
        assert lista["limiar.bm25"]["valor"] == 0.7 and lista["limiar.bm25"]["origem"] == "dono"
        bm25 = next(a for a in c.get("/api/algoritmos").json()["busca"] if a["nome"] == "bm25")
        assert bm25["limiar"] == 0.7 and bm25["limiar_padrao"] == 0.5
        assert c.put("/api/configuracoes/limiar.bm25", json={"valor": "x"}).status_code == 400
        assert c.put("/api/configuracoes/nao.existe", json={"valor": 1}).status_code == 400
        assert c.delete("/api/configuracoes/limiar.bm25").status_code == 200
        assert c.delete("/api/configuracoes/nao.existe").status_code == 404
