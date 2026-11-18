"""Testes dos algoritmos de busca e de resposta, e do pipeline completo."""

import pytest

from aprendiz.algoritmos import BUSCAS, RESPOSTAS

TODAS_AS_BUSCAS = list(BUSCAS)


def test_seletor_registra_algoritmos():
    assert {"bm25", "tfidf", "fuzzy", "hibrido"} <= set(BUSCAS)
    assert {"direta", "extrativa"} <= set(RESPOSTAS)


@pytest.mark.parametrize("busca", TODAS_AS_BUSCAS)
def test_todas_as_buscas_encontram_pergunta_ensinada(assistente_ensinado, busca):
    r = assistente_ensinado.responder("qual a senha do wifi?", busca=busca)
    assert r["mensagem"]["meta"]["tipo"] == "conhecimento"
    assert "casa123" in r["mensagem"]["texto"]


@pytest.mark.parametrize("busca", TODAS_AS_BUSCAS)
def test_modo_estrito_nao_inventa(assistente_ensinado, busca):
    r = assistente_ensinado.responder("qual a capital da frança?", busca=busca)
    assert r["mensagem"]["meta"]["tipo"] == "desconhecido"


def test_sinonimo_encontra_conhecimento(assistente_ensinado):
    r = assistente_ensinado.responder("quando levo o veículo na revisão?")
    assert "março" in r["mensagem"]["texto"]


def test_resposta_extrativa_escolhe_a_frase_certa(assistente_ensinado):
    r = assistente_ensinado.responder("qual a calibragem dos pneus?", resposta="extrativa")
    assert r["mensagem"]["texto"] == "A calibragem dos pneus é 35 psi na frente e 33 atrás."


def test_explicacao_registra_etapas(assistente_ensinado):
    meta = assistente_ensinado.responder("horário da farmácia")["mensagem"]["meta"]
    nomes = [e["nome"] for e in meta["explicacao"]["etapas"]]
    assert nomes[0] == "Normalização"
    assert any(n.startswith("Busca") for n in nomes)
    assert meta["explicacao"]["total_ms"] >= 0


@pytest.mark.parametrize("mensagem, tipo", [
    ("oi", "social"), ("obrigado!", "social"), ("tchau", "social"), ("como te ensino?", "social"),
])
def test_intencoes_sociais(assistente, mensagem, tipo):
    assert assistente.responder(mensagem)["mensagem"]["meta"]["tipo"] == tipo


@pytest.mark.parametrize("mensagem, pergunta_esperada", [
    ("aprenda que a senha do alarme é 4321", "a senha do alarme"),
    ("pergunta: dia do lixo resposta: terças e sextas", "dia do lixo"),
])
def test_ensino_pelo_chat(assistente, mensagem, pergunta_esperada):
    r = assistente.responder(mensagem)
    assert r["mensagem"]["meta"]["tipo"] == "ensino"
    itens = assistente.banco.listar_conhecimentos()
    assert itens[0]["pergunta"] == pergunta_esperada


def test_nota_pelo_chat(assistente):
    assistente.responder("anote: comprar ração do cachorro")
    assert assistente.banco.listar_conhecimentos()[0]["tipo"] == "nota"


def test_correcao_vira_ensinamento(assistente_ensinado):
    r = assistente_ensinado.responder("horário da farmácia")
    assistente_ensinado.corrigir(r["mensagem"]["id"], "Agora abre às 7h.")
    r2 = assistente_ensinado.responder("horário da farmácia")
    assert r2["mensagem"]["texto"] == "Agora abre às 7h."


def test_importar_texto_divide_em_trechos(assistente):
    texto = "\n\n".join(f"Parágrafo número {i}. " + "texto " * 60 for i in range(5))
    n = assistente.importar_texto("notas.md", texto)
    assert n >= 2
    assert assistente.banco.contar_conhecimentos() == n


def test_novo_sinonimo_reindexa(assistente):
    assistente.ensinar("Fica na garagem.", pergunta="onde está a bicicleta")
    assert assistente.responder("onde está a bike")["mensagem"]["meta"]["tipo"] == "desconhecido"
    assistente.banco.salvar_sinonimo("bike", "bicicleta")
    assistente.reindexar()
    assert "garagem" in assistente.responder("onde está a bike")["mensagem"]["texto"]


def test_hibrido_exige_consenso(assistente):
    """Uma palavra solta num texto longo não basta (print: "você tem nome?" → regra do trema)."""
    assistente.ensinar("O trema foi abolido: linguiça, frequente; fica só em nomes estrangeiros, "
                       "como Müller.", pergunta="o que mudou com o acordo ortográfico")
    for i in range(6):  # base maior, para o TF-IDF ter com o que comparar
        assistente.ensinar(f"Conteúdo de exemplo número {i} sobre outro assunto qualquer.",
                           pergunta=f"assunto de exemplo {i}")
    r = assistente.responder("nome de cachorro", busca="hibrido")["mensagem"]
    assert r["meta"]["tipo"] == "desconhecido"
    # ...mas o assunto do conhecimento continua sendo encontrado
    r = assistente.responder("o que mudou no acordo ortográfico?", busca="hibrido")["mensagem"]
    assert r["meta"]["tipo"] == "conhecimento"
    # palavra escrita exatamente como no texto ("trema") ainda é aceita
    r = assistente.responder("o que é trema?", busca="hibrido")["mensagem"]
    assert r["meta"]["tipo"] == "conhecimento"


def test_sugestoes_tem_palavra_em_comum(assistente):
    """ "o que é um animal?" não sugere "me empresta ou empresta-me"."""
    assistente.ensinar("Diga 'me empresta' no Brasil.", pergunta="me empresta ou empresta-me")
    r = assistente.responder("o que é um animal?", busca="hibrido")["mensagem"]
    assert "empresta" not in r["texto"]
