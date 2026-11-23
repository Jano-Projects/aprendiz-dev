"""
Classificador de intenções — Naive Bayes Multinomial, escrito do zero.

O que é uma "intenção"?
    É o OBJETIVO da mensagem: cumprimentar, agradecer, pedir ajuda,
    perguntar algo, ensinar algo... Saber a intenção permite responder
    "Oi!" sem ir procurar "oi" na base de conhecimento.

Por que Naive Bayes?
    • Treina em milissegundos, mesmo em máquinas fracas.
    • Funciona bem com poucos exemplos (dezenas por intenção).
    • A matemática é simples de entender e de explicar — ótimo para estudo.

Como funciona (em uma frase):
    Para cada intenção, calculamos a probabilidade de ela "gerar" as palavras
    da mensagem, e escolhemos a intenção mais provável.

A fórmula (Teorema de Bayes, com a hipótese "ingênua" de que as palavras
são independentes entre si):

    P(intenção | palavras) ∝ P(intenção) × Π P(palavra | intenção)

    P(intenção)           = exemplos da intenção / total de exemplos
    P(palavra | intenção) = (ocorrências da palavra na intenção + 1)
                            / (total de palavras da intenção + tamanho do vocabulário)

O "+1" é a suavização de Laplace: evita probabilidade zero para palavras
que nunca apareceram em certa intenção.

Multiplicar muitas probabilidades pequenas gera números minúsculos
(underflow), então somamos LOGARITMOS em vez de multiplicar.
No final, convertemos de volta com softmax para obter porcentagens.
"""

from __future__ import annotations

# Erro de escrita (2.6) ----------------------------------------------------
# "obrigadoo" e "valew" não estão em nenhum exemplo, então o classificador
# não tinha como opinar. Uma palavra DESCONHECIDA é trocada pela palavra mais
# parecida dos exemplos de intenção, mas só se for muito parecida (letra a
# letra, ver rapidfuzz): "valew" → "valeu". Uma palavra que não lembra
# nenhuma ("astronomia") fica como está e é ignorada, como antes.
# (Pedaços de letras de toda palavra desconhecida foram testados e
# descartados: qualquer assunto novo acabava parecendo conversa social.)
SEMELHANCA_MINIMA = 80     # 0 a 100
TAMANHO_MINIMO = 4         # palavras curtas ("oi", "vc") não são corrigidas


def corrigir_para_exemplos(tokens: list[str], radicais: list[str],
                           vocabulario: dict[str, str],
                           gramaticais: set[str] | frozenset[str] = frozenset()) -> list[str]:
    """
    Os radicais da frase com as palavras desconhecidas trocadas pela mais
    parecida dos exemplos. `vocabulario`: palavra dos exemplos → radical.

    Palavras gramaticais (`gramaticais`, as stopwords) não entram nem como
    erro nem como correção: "numa" → "uma" não diz nada sobre a intenção e
    só mexe na conta.
    """
    vocabulario = {p: r for p, r in vocabulario.items() if p not in gramaticais}
    if len(tokens) != len(radicais) or not vocabulario:
        return list(radicais)
    from rapidfuzz import fuzz, process
    conhecidos = set(vocabulario.values())
    saida = []
    for token, rad in zip(tokens, radicais):
        if rad not in conhecidos and len(token) >= TAMANHO_MINIMO and token not in gramaticais:
            achado = process.extractOne(token, list(vocabulario), scorer=fuzz.ratio,
                                        score_cutoff=SEMELHANCA_MINIMA)
            if achado:
                rad = vocabulario[achado[0]]
        saida.append(rad)
    return saida

import math
from collections import Counter, defaultdict


class ClassificadorIntencoes:
    def __init__(self) -> None:
        self.log_prior: dict[str, float] = {}
        self.log_verossimilhanca: dict[str, dict[str, float]] = {}
        self.log_desconhecida: dict[str, float] = {}
        self.vocabulario: set[str] = set()
        self.treinado = False

    def treinar(self, exemplos: list[tuple[str, list[str]]]) -> None:
        """
        exemplos: lista de (intenção, lista de termos da frase).
        Os termos já vêm processados (radicais) pelo normalizador.
        """
        self.vocabulario = set()  # recomeça do zero a cada treino
        contagem_intencao: Counter[str] = Counter()
        contagem_palavras: dict[str, Counter[str]] = defaultdict(Counter)

        for intencao, termos in exemplos:
            contagem_intencao[intencao] += 1
            contagem_palavras[intencao].update(termos)
            self.vocabulario.update(termos)

        total = sum(contagem_intencao.values())
        v = len(self.vocabulario) or 1

        self.log_prior = {i: math.log(n / total) for i, n in contagem_intencao.items()}
        self.log_verossimilhanca = {}
        self.log_desconhecida = {}
        for intencao, contagem in contagem_palavras.items():
            denominador = sum(contagem.values()) + v
            self.log_verossimilhanca[intencao] = {
                p: math.log((n + 1) / denominador) for p, n in contagem.items()
            }
            # Palavra do vocabulário que nunca apareceu nesta intenção:
            self.log_desconhecida[intencao] = math.log(1 / denominador)

        self.treinado = bool(self.log_prior)

    def classificar(self, termos: list[str]) -> list[dict]:
        """
        Devolve todas as intenções com sua probabilidade, da mais provável
        para a menos provável. Palavras fora do vocabulário são ignoradas
        (não dizem nada sobre nenhuma intenção).
        """
        if not self.treinado:
            return []

        conhecidos = [t for t in termos if t in self.vocabulario]
        if not conhecidos:
            # Nenhuma palavra conhecida → não dá para opinar.
            return [{"intencao": "desconhecida", "probabilidade": 1.0}]

        pontuacoes = {}
        for intencao, prior in self.log_prior.items():
            tabela = self.log_verossimilhanca[intencao]
            padrao = self.log_desconhecida[intencao]
            pontuacoes[intencao] = prior + sum(tabela.get(t, padrao) for t in conhecidos)

        # Softmax: transforma log-pontuações em probabilidades que somam 1.
        maior = max(pontuacoes.values())
        exps = {i: math.exp(p - maior) for i, p in pontuacoes.items()}
        soma = sum(exps.values())
        resultado = [
            {"intencao": i, "probabilidade": round(e / soma, 4)} for i, e in exps.items()
        ]
        return sorted(resultado, key=lambda r: r["probabilidade"], reverse=True)
