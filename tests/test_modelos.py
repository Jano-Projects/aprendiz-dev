"""
Propriedades matemáticas dos modelos (2.5.1).

Não testam "a resposta certa" de uma pergunta: testam o que TEM de valer para
qualquer entrada — probabilidades somam 1, a sigmoide é monótona, o cosseno
não passa de 1, o RRF segue a fórmula, o TextRank é estável. Cada teste roda
sobre dados gerados com semente fixa, então é determinístico.
"""

import math
import random

import pytest

from aprendiz.algoritmos.busca import calibrado, calibrado_pesos
from aprendiz.algoritmos.busca.hibrido import K_RRF
from aprendiz.algoritmos.busca.tfidf import _normalizar_vetor
from aprendiz.algoritmos.resposta.extrativa import textrank
from aprendiz.linguagem.intencoes import ClassificadorIntencoes

VOCAB = [f"p{i}" for i in range(40)]


def frases_aleatorias(rnd, n, intencoes=("a", "b", "c", "d")):
    return [(rnd.choice(intencoes), rnd.sample(VOCAB, rnd.randint(1, 6))) for _ in range(n)]


# ------------------------------------------------------------ Naive Bayes
@pytest.mark.parametrize("semente", range(20))
def test_naive_bayes_probabilidades_somam_1(semente):
    rnd = random.Random(semente)
    nb = ClassificadorIntencoes()
    nb.treinar(frases_aleatorias(rnd, 60))
    for _ in range(20):
        saida = nb.classificar(rnd.sample(VOCAB + ["fora1", "fora2"], rnd.randint(1, 8)))
        probs = [s["probabilidade"] for s in saida]
        assert math.isclose(sum(probs), 1.0, abs_tol=1e-3)   # cada uma é arredondada a 4 casas
        assert all(0.0 <= p <= 1.0 for p in probs)
        assert probs == sorted(probs, reverse=True)       # da mais para a menos provável


def test_naive_bayes_sem_treino_e_palavras_desconhecidas():
    nb = ClassificadorIntencoes()
    assert nb.classificar(["x"]) == []
    nb.treinar([("saudacao", ["oi"]), ("despedida", ["tchau"])])
    assert nb.classificar(["xyz"]) == [{"intencao": "desconhecida", "probabilidade": 1.0}]


def test_naive_bayes_retreino_esquece_o_vocabulario_antigo():
    nb = ClassificadorIntencoes()
    nb.treinar([("a", ["velho"])])
    nb.treinar([("b", ["novo"])])
    assert "velho" not in nb.vocabulario
    assert nb.classificar(["novo"])[0]["intencao"] == "b"


def test_naive_bayes_ordem_das_palavras_nao_importa():
    rnd = random.Random(7)
    nb = ClassificadorIntencoes()
    nb.treinar(frases_aleatorias(rnd, 80))
    termos = rnd.sample(VOCAB, 5)
    a = nb.classificar(termos)
    b = nb.classificar(list(reversed(termos)))
    assert [x["intencao"] for x in a] == [x["intencao"] for x in b]
    for x, y in zip(a, b):
        assert math.isclose(x["probabilidade"], y["probabilidade"], rel_tol=1e-9)


def test_naive_bayes_nao_estoura_com_frase_enorme():
    nb = ClassificadorIntencoes()
    nb.treinar([("a", ["x"]), ("b", ["y"])])
    saida = nb.classificar(["x"] * 5000)              # log-soma: sem underflow
    assert saida[0]["intencao"] == "a" and saida[0]["probabilidade"] > 0.99


# ------------------------------------------------------------ Calibrado
@pytest.mark.parametrize("z", [-1000, -50, -1, 0, 1, 50, 1000])
def test_sigmoide_estavel_e_limitada(z):
    s = calibrado.sigmoide(z)
    assert 0.0 <= s <= 1.0 and not math.isnan(s)


def test_sigmoide_monotona_e_simetrica():
    xs = [x / 10 for x in range(-100, 101)]
    ys = [calibrado.sigmoide(x) for x in xs]
    assert ys == sorted(ys)
    for x in xs:
        assert math.isclose(calibrado.sigmoide(x) + calibrado.sigmoide(-x), 1.0, abs_tol=1e-12)


def test_modelo_calibrado_tem_formato_consistente():
    m = calibrado_pesos.MODELO
    n = len(m["sinais"])
    assert len(m["media"]) == len(m["desvio"]) == len(m["pesos"]) == n
    assert all(d > 0 for d in m["desvio"])
    assert all(math.isfinite(p) for p in m["pesos"] + [m["vies"]])


@pytest.mark.parametrize("indice", range(len(calibrado_pesos.MODELO["sinais"])))
def test_calibrado_e_monotono_em_cada_sinal(indice):
    """Aumentar um sinal move a probabilidade no sentido do sinal do seu peso."""
    m = calibrado_pesos.MODELO
    nome, peso = m["sinais"][indice], m["pesos"][indice]
    base = dict(zip(m["sinais"], m["media"]))
    anterior = None
    for passo in range(-5, 6):
        sinais = {**base, nome: base[nome] + passo * m["desvio"][indice]}
        p, contrib = calibrado.prever(sinais)
        assert 0.0 <= p <= 1.0
        if anterior is not None:
            if peso > 0:
                assert p >= anterior - 1e-12
            elif peso < 0:
                assert p <= anterior + 1e-12
        anterior = p


def test_contribuicoes_explicam_a_probabilidade():
    """vies + Σ contribuições = logito da probabilidade (o Monitor mostra isso)."""
    m = calibrado_pesos.MODELO
    rnd = random.Random(3)
    for _ in range(50):
        sinais = {s: rnd.uniform(-2, 3) for s in m["sinais"]}
        p, contrib = calibrado.prever(sinais)
        z = m["vies"] + sum(contrib.values())
        assert math.isclose(calibrado.sigmoide(z), p, abs_tol=5e-3)   # contribuições são arredondadas


def test_segunda_etapa_prefere_primeiro_destacado():
    destacado = calibrado.chance_de_responder_certo([0.9, 0.1])
    empatado = calibrado.chance_de_responder_certo([0.9, 0.89])
    assert destacado > empatado
    assert calibrado.chance_de_responder_certo([]) == 0.0
    assert 0.0 <= calibrado.chance_de_responder_certo([1.0]) <= 1.0     # logito limitado


def test_cobertura_idf_entre_0_e_1():
    rnd = random.Random(11)
    idf = {p: rnd.uniform(0.1, 5) for p in VOCAB}
    for _ in range(100):
        termos = rnd.sample(VOCAB + ["ausente"], rnd.randint(1, 6))
        doc = set(rnd.sample(VOCAB, rnd.randint(0, 10)))
        c = calibrado.cobertura_idf(termos, doc, idf, 6.0)
        assert 0.0 <= c <= 1.0
    assert calibrado.cobertura_idf(["p1"], {"p1"}, idf, 6.0) == pytest.approx(1.0)


# ------------------------------------------------------------ TF-IDF
@pytest.mark.parametrize("semente", range(10))
def test_tfidf_vetor_normalizado_e_cosseno_ate_1(semente):
    rnd = random.Random(semente)
    a = _normalizar_vetor({p: rnd.uniform(0, 5) for p in rnd.sample(VOCAB, 8)})
    b = _normalizar_vetor({p: rnd.uniform(0, 5) for p in rnd.sample(VOCAB, 8)})
    assert math.isclose(math.sqrt(sum(v * v for v in a.values())), 1.0, rel_tol=1e-9)
    cos = sum(v * b.get(k, 0.0) for k, v in a.items())
    assert -1e-9 <= cos <= 1 + 1e-9
    assert math.isclose(sum(v * v for v in a.values()), 1.0, rel_tol=1e-9)   # cos(a, a) = 1


def test_tfidf_vetor_vazio_nao_divide_por_zero():
    assert _normalizar_vetor({}) == {}


# ------------------------------------------------------------ RRF (Híbrido)
def test_rrf_formula_classica():
    assert K_RRF == 60
    # 1º em dois algoritmos > 1º em um e 3º no outro > ausente de um deles
    def rrf(*posicoes):
        return sum(1 / (K_RRF + p) for p in posicoes)
    assert rrf(1, 1) > rrf(1, 3) > rrf(1)
    assert rrf(2, 2) > rrf(1, 5)          # consenso vence um 1º lugar isolado


# ------------------------------------------------------------ TextRank (Extrativa)
@pytest.mark.parametrize("semente", range(10))
def test_textrank_notas_normalizadas(semente):
    rnd = random.Random(semente)
    conjuntos = [set(rnd.sample(VOCAB, rnd.randint(1, 8))) for _ in range(rnd.randint(1, 12))]
    notas = textrank(conjuntos)
    assert len(notas) == len(conjuntos)
    assert max(notas) == pytest.approx(1.0)
    assert all(0.0 < n <= 1.0 + 1e-12 for n in notas)


def test_textrank_casos_limite():
    assert textrank([]) == []
    assert textrank([set()]) == [1.0]
    assert textrank([{"a"}, {"b"}]) == [1.0, 1.0]        # sem ligação: empate


def test_textrank_frase_central_ganha():
    centro = {"a", "b", "c", "d"}
    notas = textrank([{"a", "x"}, {"b", "y"}, centro, {"c", "z"}, {"d", "w"}])
    assert notas.index(max(notas)) == 2


def test_textrank_independe_da_ordem():
    conjuntos = [{"a", "b"}, {"b", "c"}, {"c", "d"}, {"a", "d", "e"}]
    notas = textrank(conjuntos)
    invertidas = textrank(list(reversed(conjuntos)))
    for x, y in zip(notas, reversed(invertidas)):
        assert math.isclose(x, y, rel_tol=1e-9)
