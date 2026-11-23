"""
Radicalizador (stemmer) para português — versão simplificada do RSLP.

O que é radicalização?
    É reduzir palavras à sua "raiz" para que variações caiam no mesmo termo:

        ensinar, ensinei, ensinando, ensinou  →  "ensin"
        farmácia, farmácias                   →  "farmac"

    Assim, se você ensinou "horário de abertura da farmácia" e depois
    pergunta "que horas as farmácias abrem?", a busca encontra o que precisa.

O algoritmo RSLP (Removedor de Sufixos da Língua Portuguesa) foi proposto
por Viviane Orengo e Christian Huyck (2001). Ele aplica passos em ordem fixa,
cada um com uma lista de regras do tipo:

    (sufixo, tamanho mínimo do radical que sobra, substituição)

Esta implementação mantém a ESTRUTURA do RSLP, mas com regras reduzidas e
operando em texto já sem acentos (o normalizador remove os acentos antes).
Ela não é perfeita em linguística — e não precisa ser: o importante é ser
CONSISTENTE, ou seja, a mesma palavra sempre gerar o mesmo radical, tanto
quando o dono ensina quanto quando ele pergunta.

Se quiser comparar com o RSLP completo, a biblioteca NLTK tem uma versão
(nltk.stem.RSLPStemmer). Experimente trocar e rodar o benchmark!
"""

from __future__ import annotations

from functools import lru_cache

# Cada regra: (sufixo, tamanho mínimo do radical restante, substituição)
Regra = tuple[str, int, str]

# Passo 1 — plural (só se a palavra termina em "s").
# Plurais irregulares que nenhuma regra acerta sem os acentos (2.5.1). Cada
# um vai para a mesma forma do singular: "mães" e "mãe"; "países", "país",
# "pais" e "pai" (sem acento, país e pai já eram a mesma palavra).
PLURAIS_IRREGULARES = {"maes": "mae", "paises": "pai", "pais": "pai", "bois": "boi"}

PLURAL: list[Regra] = [
    ("ns", 1, "m"),      # homens → homem
    ("eses", 3, ""),     # ingleses → ingl, como inglês (2.5.1)
    ("oes", 2, "ao"),    # botoes → botao; acoes → acao (2.5.1: mínimo 2)
    ("aes", 1, "ao"),    # paes → pao, caes → cao
    ("ais", 1, "al"),    # animais → animal
    ("eis", 2, "el"),    # papeis → papel
    ("ois", 1, "ol"),    # lencois → lencol, sois → sol
    ("uis", 2, "ul"),    # azuis → azul (2.5.1)
    ("les", 3, "l"),     # males → mal
    ("res", 3, "r"),     # flores → flor
    ("is", 2, "il"),     # fuzis → fuzil (só depois de consoante: veja radical())
    ("s", 2, ""),        # casas → casa
]

# Passo 2 — feminino (só se termina em "a").
FEMININO: list[Regra] = [
    ("ona", 3, "ao"),
    ("ora", 3, "or"),
    ("inha", 3, "inho"),
    ("eira", 3, "eiro"),
    ("esa", 3, "es"),
    ("osa", 3, "oso"),
    ("ica", 3, "ico"),
    ("ada", 2, "ado"),
    ("ida", 3, "ido"),
    ("iva", 3, "ivo"),
    ("ima", 3, "imo"),
]

# Passo 3 — aumentativo/diminutivo.
GRAU: list[Regra] = [
    ("issimo", 3, ""),
    ("zinho", 2, ""),
    ("inho", 3, ""),
    ("zao", 2, ""),
    ("arrao", 4, ""),
]

# Passo 4 — sufixos de substantivos e adjetivos.
SUBSTANTIVO: list[Regra] = [
    ("amento", 3, ""),
    ("imento", 3, ""),
    ("mente", 4, ""),
    ("idade", 4, ""),
    ("acao", 3, ""),
    ("icao", 3, ""),
    ("ismo", 3, ""),
    ("ista", 4, ""),
    ("avel", 2, ""),
    ("ivel", 3, ""),
    ("encia", 3, ""),
    ("ancia", 3, ""),
    ("eiro", 3, ""),
    ("oso", 3, ""),
    ("ico", 3, ""),
]

# Passo 5 — terminações verbais (só se o passo 4 não removeu nada).
VERBO: list[Regra] = [
    ("ariamos", 2, ""), ("eriamos", 2, ""), ("iriamos", 3, ""),
    ("assemos", 2, ""), ("essemos", 2, ""), ("issemos", 3, ""),
    ("aremos", 2, ""), ("eremos", 2, ""), ("iremos", 3, ""),
    ("avamos", 2, ""), ("aramos", 2, ""), ("eramos", 2, ""),
    ("ando", 2, ""), ("endo", 3, ""), ("indo", 3, ""),
    ("aram", 2, ""), ("eram", 3, ""), ("iram", 3, ""),
    ("avam", 2, ""), ("arem", 2, ""), ("erem", 3, ""), ("irem", 3, ""),
    ("asse", 2, ""), ("esse", 3, ""), ("isse", 3, ""),
    ("aria", 2, ""), ("eria", 3, ""), ("iria", 3, ""),
    ("ado", 2, ""), ("ido", 3, ""),
    ("ava", 2, ""), ("ara", 2, ""), ("era", 3, ""),
    ("ou", 3, ""), ("ei", 3, ""), ("eu", 3, ""), ("iu", 3, ""),
    ("ar", 2, ""), ("er", 2, ""), ("ir", 3, ""),
    ("am", 2, ""), ("em", 2, ""),
    ("ia", 3, ""),
]

VOGAIS_FINAIS = ("a", "e", "o")


def _aplicar(palavra: str, regras: list[Regra]) -> tuple[str, bool]:
    """Aplica a PRIMEIRA regra que casar (as listas vêm do sufixo mais
    específico para o mais genérico). Retorna (palavra, aplicou?)."""
    for sufixo, minimo, troca in regras:
        if palavra.endswith(sufixo) and len(palavra) - len(sufixo) >= minimo:
            return palavra[: -len(sufixo)] + troca, True
    return palavra, False


@lru_cache(maxsize=50_000)
def singular(palavra: str) -> str:
    """
    Só o passo do plural ("pães" → "pao", "animais" → "animal"), sem cortar
    o resto. Serve para comparar palavras sem juntar famílias diferentes,
    como o radical faria ("ligações" e "ligada"). Palavras de até 3 letras
    ficam como estão. (2.5.1)
    """
    if len(palavra) <= 3 or palavra.isdigit():
        return palavra
    if palavra in PLURAIS_IRREGULARES:
        return PLURAIS_IRREGULARES[palavra]
    if not palavra.endswith("s"):
        return palavra
    if palavra.endswith("eis") and len(palavra) == 4:
        return palavra[:-1]                 # "leis", "reis" → "lei", "rei"
    return _aplicar(palavra, PLURAL)[0]


@lru_cache(maxsize=50_000)
def radical(palavra: str) -> str:
    """
    Devolve o radical de uma palavra (já em minúsculas e sem acento).

    O lru_cache guarda os resultados: palavras repetidas (muito comuns)
    não são processadas de novo.
    """
    # Palavras curtas e números ficam como estão.
    if len(palavra) <= 3 or palavra.isdigit():
        return palavra

    palavra = singular(palavra)
    if palavra.endswith("a"):
        palavra, _ = _aplicar(palavra, FEMININO)
    palavra, _ = _aplicar(palavra, GRAU)

    palavra, mudou = _aplicar(palavra, SUBSTANTIVO)
    if not mudou:
        palavra, mudou = _aplicar(palavra, VERBO)
    if not mudou and palavra.endswith(VOGAIS_FINAIS) and len(palavra) > 3:
        # Passo 6 — remove a vogal final ("carro" e "carros" → "carr").
        palavra = palavra[:-1]

    return palavra
