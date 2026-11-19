"""Números e contas escritos de jeitos diferentes viram uma forma só (fase 1 da 2.0)."""

import pytest

from aprendiz.linguagem.normalizador import normalizar


@pytest.mark.parametrize("texto", [
    "2+2", "2 + 2", "dois mais dois", "2 mais dois", "dois + 2", "Dois mais 2?",
])
def test_mesma_conta_de_varios_jeitos(texto):
    assert normalizar(texto) == "2 soma 2"


@pytest.mark.parametrize("texto, esperado", [
    ("vinte e cinco", "25"),
    ("mil e duzentos", "1200"),
    ("cento e três", "103"),
    ("três vezes três", "3 multiplicacao 3"),
    ("3x4", "3 multiplicacao 4"),
    ("oito dividido por quatro", "8 divisao 4"),
    ("8 / 4", "8 divisao 4"),
    ("dez menos 2", "10 subtracao 2"),
    ("um mais um", "1 soma 1"),
    ("2 + 2 = 4", "2 soma 2 igual 4"),
])
def test_numeros_e_operacoes(texto, esperado):
    assert normalizar(texto) == esperado


@pytest.mark.parametrize("texto, esperado", [
    ("o que é um ponteiro", "o que e um ponteiro"),   # "um" artigo fica
    ("16/11/2026", "16 11 2026"),                     # data não vira divisão
    ("2026-11-16", "2026 11 16"),                     # data não vira subtração
    ("0x10", "0x10"),                                 # hexadecimal
    ("c++ e c#", "cpp e csharp"),
    ("p->nome", "p seta nome"),
    ("where id = 1", "where id 1"),                   # "=" fora de conta some
])
def test_nao_muda_o_que_nao_e_conta(texto, esperado):
    assert normalizar(texto) == esperado


@pytest.mark.parametrize("pergunta", [
    "quanto é 2+2?", "quanto é dois mais dois?", "quanto é 2 mais dois?", "dois + 2 dá quanto?",
])
def test_ensinado_de_um_jeito_achado_de_outro(assistente, pergunta):
    assistente.ensinar("4", pergunta="quanto é 2 + 2")
    r = assistente.responder(pergunta)
    assert r["mensagem"]["texto"] == "4"
