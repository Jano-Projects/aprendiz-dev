"""
Robustez (2.5.1): entradas estranhas nunca derrubam o assistente.

Fuzz com semente fixa: cada combinação de busca × resposta recebe textos
gerados (emojis, só pontuação, números gigantes, SQL, HTML, escrita de trás
para frente, textos longos...). O teste não confere o CONTEÚDO da resposta,
só que ela sai inteira, com tipo, texto e confiança válidos.
"""

import random
import time

import pytest

from aprendiz.algoritmos import BUSCAS, RESPOSTAS

ESTRANHOS = [
    "?", "???", "...", "!!!", "-", "a", "é", "ç", "0", "00000000000000000000000",
    "9" * 400, "😀", "😀😀😀 🚀", "‮invertido", "\u200b\u200b", "\t\n\t", "\\", "%s %d {0}",
    "'; DROP TABLE conhecimentos; --", "<script>alert(1)</script>", "SELECT * FROM x",
    "NULL", "None", "undefined", "{}", "[]", "C:\\Windows\\System32", "../../etc/passwd",
    "ááááááááá", "ÃÕÇÉÍ", "mil mil mil mil", "um dois três quatro cinco",
    "2+", "+2", "2 ++ 2", "1/0", "dividido por zero", "3 milhões de bilhões",
    "por favor", "obrigado", "me explica", "me fala", "o que é", "por que",
    "qual a senha do wifi " * 30, "x" * 2000, "palavra " * 500,
    "31/02/2026 25:99 R$ -5", "CEP 00000-000", "senha", "SENHA DO WIFI???",
    "oi", "tchau", "lembre que", "esqueça", "aprenda: ", "P: R:",
]


def gerar(rnd: random.Random, n: int) -> list[str]:
    alfabeto = "abcdefghijklmnopqrstuvwxyzáéíóúãõç0123456789 ?!.,;:-+*/%$@#()"
    saida = []
    for _ in range(n):
        tam = rnd.randint(1, 80)
        saida.append("".join(rnd.choice(alfabeto) for _ in range(tam)))
    return saida


def confere_resposta(r):
    m = r["mensagem"]
    assert isinstance(m["texto"], str) and m["texto"].strip()
    assert m["meta"]["tipo"]
    for etapa in m["meta"]["explicacao"]["etapas"]:
        for c in (etapa.get("dados") or {}).get("candidatos", []) or []:
            if isinstance(c, dict) and "confianca" in c:
                assert 0.0 <= c["confianca"] <= 1.0 + 1e-9


@pytest.mark.parametrize("busca", sorted(BUSCAS))
def test_entradas_estranhas_em_todas_as_buscas(assistente_ensinado, busca):
    for texto in ESTRANHOS:
        if not texto.strip():
            continue
        confere_resposta(assistente_ensinado.responder(texto, busca=busca))


@pytest.mark.parametrize("resposta", sorted(RESPOSTAS))
def test_entradas_aleatorias_em_todas_as_respostas(assistente_ensinado, resposta):
    rnd = random.Random(sorted(RESPOSTAS).index(resposta))
    for texto in gerar(rnd, 60):
        if texto.strip():
            confere_resposta(assistente_ensinado.responder(texto, resposta=resposta))


@pytest.mark.parametrize("vazia", ["", " ", "\n\t  "])
def test_mensagem_vazia_e_recusada(assistente, vazia):
    with pytest.raises(ValueError):
        assistente.responder(vazia)


def test_algoritmo_desconhecido_e_recusado(assistente):
    with pytest.raises(ValueError):
        assistente.responder("oi", busca="nao-existe")
    with pytest.raises(ValueError):
        assistente.responder("oi", resposta="nao-existe")


def test_base_vazia_responde_sem_erro(assistente):
    for busca in BUSCAS:
        confere_resposta(assistente.responder("qual a senha do wifi?", busca=busca))


def test_texto_longo_responde_em_tempo_razoavel(assistente_ensinado):
    """Máquinas fracas: 5 mil palavras não podem travar o app."""
    texto = " ".join(random.Random(1).choice(["senha", "wifi", "carro", "óleo", "xpto"])
                     for _ in range(5000))
    inicio = time.perf_counter()
    confere_resposta(assistente_ensinado.responder(texto))
    assert time.perf_counter() - inicio < 20


def test_ensinar_conteudo_estranho_nao_quebra_a_busca(assistente):
    for i, texto in enumerate(ESTRANHOS[:25]):
        if texto.strip():
            assistente.ensinar(f"conteúdo {i}: {texto}", pergunta=texto[:60])
    assistente.ensinar("A senha do wifi é casa123.", pergunta="senha do wifi")
    for busca in BUSCAS:
        r = assistente.responder("qual a senha do wifi?", busca=busca)
        assert "casa123" in r["mensagem"]["texto"]
