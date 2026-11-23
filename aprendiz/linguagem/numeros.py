"""
Números e contas escritos de jeitos diferentes viram uma forma só.

    "2+2"             → "2 soma 2"
    "dois mais dois"  → "2 soma 2"
    "2 mais dois"     → "2 soma 2"
    "vinte e cinco"   → "25"

Sem isto, cada forma era uma pergunta diferente para a busca: o "+" sumia
na limpeza da pontuação ("2+2" virava "2 2") e "dois" nunca casava com "2".

Funciona em duas etapas, chamadas por `normalizador.normalizar()`:

    1. `simbolos()`  — ANTES de apagar a pontuação: troca +, *, ×, ÷ e os "x", "=",
       "-" e "/" entre números por palavras ("mais", "vezes"…).
    2. `palavras()`  — DEPOIS, nas palavras já sem acento: número por extenso
       vira algarismo, e a palavra da operação entre dois números vira um
       nome fixo ("soma", "subtracao", "multiplicacao", "divisao").

"um"/"uma" só viram 1 perto de outro número ou de uma operação, porque na
maior parte das frases são artigos ("o que é um ponteiro").
"""

from __future__ import annotations

import re

UNIDADES = {
    "zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4,
    "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11,
    "doze": 12, "treze": 13, "catorze": 14, "quatorze": 14, "quinze": 15,
    "dezesseis": 16, "dezasseis": 16, "dezessete": 17, "dezassete": 17,
    "dezoito": 18, "dezenove": 19, "dezanove": 19,
}
DEZENAS = {"vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50, "sessenta": 60,
           "setenta": 70, "oitenta": 80, "noventa": 90}
CENTENAS = {"cem": 100, "cento": 100, "duzentos": 200, "duzentas": 200, "trezentos": 300,
            "trezentas": 300, "quatrocentos": 400, "quatrocentas": 400, "quinhentos": 500,
            "quinhentas": 500, "seiscentos": 600, "seiscentas": 600, "setecentos": 700,
            "setecentas": 700, "oitocentos": 800, "oitocentas": 800, "novecentos": 900,
            "novecentas": 900}
VALORES = {**UNIDADES, **DEZENAS, **CENTENAS}
# Multiplicadores grandes (2.5.1): "dois milhões e trezentos mil" → 2300000.
GRANDES = {"milhao": 1_000_000, "milhoes": 1_000_000,
           "bilhao": 1_000_000_000, "bilhoes": 1_000_000_000}
ARTIGOS_NUMERO = {"um", "uma"}

# Palavra da operação → nome fixo. Só vale ENTRE dois números.
OPERACOES = {"mais": "soma", "menos": "subtracao", "vezes": "multiplicacao",
             "x": "multiplicacao", "dividido": "divisao"}

# "-" e "/" só entre números soltos: "2-2" e "8 / 4" são contas, mas
# "16/11/2026" e "2026-11-16" são datas (número colado em outro "/" ou "-").
_MENOS = re.compile(r"(?<![\d-])(\d+)\s*-\s*(\d+)(?![\d-]|-\d)")
_BARRA = re.compile(r"(?<![\d/])(\d+)\s*/\s*(\d+)(?![\d/]|/\d)")
# "3x4" e "3 x 4" (mas não o hexadecimal "0x10").
_VEZES_X = re.compile(r"(?<![\d])(?!0x)(\d+)\s*x\s*(\d+)\b")
_IGUAL = re.compile(r"(\d)\s*=\s*(\d)")
# Ponto de milhar (2.5.1): "1.000" e "R$ 1.234.567" viram "1000" e "1234567",
# e não "1 000". Só um ponto seguido de exatamente três algarismos.
_MILHAR = re.compile(r"(?<=\d)\.(?=\d{3}(?!\d))")
_SIMBOLOS = {"+": " mais ", "*": " vezes ", "×": " vezes ", "÷": " dividido "}


def simbolos(texto: str) -> str:
    """Etapa 1: símbolos de conta viram palavras (antes de apagar a pontuação)."""
    texto = _MILHAR.sub("", texto)
    texto = _MENOS.sub(r"\1 menos \2", texto)
    texto = _BARRA.sub(r"\1 dividido \2", texto)
    texto = _VEZES_X.sub(r"\1 vezes \2", texto)
    texto = _IGUAL.sub(r"\1 igual \2", texto)
    for simbolo, palavra in _SIMBOLOS.items():
        texto = texto.replace(simbolo, palavra)
    return texto


def _ler_numero(tokens: list[str], i: int) -> tuple[int, int] | None:
    """
    Lê um número por extenso a partir de tokens[i]. Devolve (valor, quantos
    tokens usou) ou None. "vinte e cinco" → (25, 3); "mil e duzentos" → (1200, 3).
    """
    grande, total, atual, j, usou = 0, 0, 0, i, 0
    while j < len(tokens):
        t = tokens[j]
        if t in VALORES:
            atual += VALORES[t]
        elif t == "mil":
            total += (atual or 1) * 1000
            atual = 0
        elif t in GRANDES and (usou or t in ("milhao", "bilhao")):
            grande += ((total + atual) or 1) * GRANDES[t]
            total = atual = 0
        elif t == "e" and usou and j + 1 < len(tokens) and (
                tokens[j + 1] in VALORES or tokens[j + 1] in ("mil", *GRANDES)):
            j += 1
            continue
        else:
            break
        j += 1
        usou = j - i
    if not usou:
        return None
    return grande + total + atual, usou


def _e_numero(token: str | None) -> bool:
    return token is not None and (token.isdigit() or token in VALORES or token == "mil"
                                  or token in GRANDES)


def palavras(tokens: list[str]) -> list[str]:
    """Etapa 2: números por extenso → algarismos; operação entre números → nome fixo."""
    saida: list[str] = []
    i = 0
    while i < len(tokens):
        if (tokens[i] in GRANDES or tokens[i] == "mil") and saida and saida[-1].isdigit():
            # "3 milhões" → 3000000 e "2 mil" → 2000, como "dois mil" (2.5.1)
            saida[-1] = str(int(saida[-1]) * GRANDES.get(tokens[i], 1000))
            i += 1
            continue
        lido = _ler_numero(tokens, i)
        if lido:
            valor, usou = lido
            if usou == 1 and tokens[i] in ARTIGOS_NUMERO:
                vizinhos = [saida[-1] if saida else None,
                            tokens[i + 1] if i + 1 < len(tokens) else None]
                if not any(_e_numero(v) or v in OPERACOES or v in OPERACOES.values()
                           for v in vizinhos):
                    saida.append(tokens[i])
                    i += 1
                    continue
            saida.append(str(valor))
            i += usou
        else:
            saida.append(tokens[i])
            i += 1

    # "dividido por" → "dividido"; depois, a operação entre dois números.
    saida = [t for k, t in enumerate(saida)
             if not (t == "por" and k and saida[k - 1] == "dividido")]
    for k in range(1, len(saida) - 1):
        if saida[k] in OPERACOES and saida[k - 1].isdigit() and saida[k + 1].isdigit():
            saida[k] = OPERACOES[saida[k]]
    return saida
