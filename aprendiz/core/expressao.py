"""
Expressão (2.0): COMO dizer cada parte de uma resposta, com frases que vêm
dos addons de linguagem (seção "expressao" do compreensao.json).

A teia (core/teia.py) diz O QUE explicar: o fato e a cadeia de porquês. A
expressão diz COMO um humano falaria isso:

    "porque":       ["isso porque {x}", "o motivo é que {x}"]
    "diferente-de": ["já {x}", "a diferença é que {x}"]

"{x}" é o lugar do conteúdo. Entre frases equivalentes, uma é sorteada a
cada resposta, para o Aprendiz não repetir sempre a mesma.

Os addons ativos SOMAM frases (mais addons = mais variedade). Sem nenhum
addon com expressão, vale o conjunto mínimo PADRAO, embutido aqui: a
resposta continua saindo, só com menos variação.
"""

from __future__ import annotations

import json
import random

PADRAO: dict[str, list[str]] = {
    "abertura_addon": ["Pelo que tenho em **{x}**:"],
    "abertura_dono": ["Pelo que você me ensinou:"],
    "porque": ["Isso porque {x}."],
    "regra": ["A regra é: {x}."],
    "definicao": ["Em resumo, {x}."],
    "parte-de": ["Isso faz parte de {x}."],
    "diferente-de": ["Já {x}."],
    "consequencia": ["Com isso, {x}."],
    "exemplo-de": ["Por exemplo: {x}."],
    "antes-de": ["Antes disso, {x}."],
    "depois-de": ["Depois disso, {x}."],
    "equivale": ["No mesmo sentido, {x}."],
    "fechamento": [],
}


class Expressao:
    def __init__(self, banco, sorteio: random.Random | None = None) -> None:
        self.banco = banco
        self.sorteio = sorteio or random.Random()
        self._versao = -1
        self._frases: dict[str, list[str]] = {}
        self._ultima: dict[str, str] = {}   # não repetir a mesma frase duas vezes seguidas

    def _atualizar(self) -> None:
        if self._versao == self.banco.versao_linguagem:
            return
        frases: dict[str, list[str]] = {}
        for _, bruto in self.banco.recursos_ativos("compreensao.json"):
            for parte, lista in (json.loads(bruto).get("expressao") or {}).items():
                frases.setdefault(parte, []).extend(lista)
        self._frases = frases
        self._versao = self.banco.versao_linguagem

    def frases(self, parte: str) -> list[str]:
        """As frases em vigor para uma parte: as dos addons ou, sem elas, as do PADRAO."""
        self._atualizar()
        return self._frases.get(parte) or PADRAO.get(parte, [])

    def dizer(self, parte: str, x: str = "") -> str:
        """Uma frase sorteada para `parte`, com `x` na lacuna. "" se não houver frase."""
        opcoes = self.frases(parte)
        if not opcoes:
            return ""
        livres = [f for f in opcoes if f != self._ultima.get(parte)] or opcoes
        frase = self.sorteio.choice(livres)
        self._ultima[parte] = frase
        if "{x}" in frase:
            x = x.strip().rstrip(".")
            # No meio da frase, "O HAVING filtra" vira "o HAVING filtra"
            # (mas siglas e nomes como "SQL" ou "Python" ficam como estão).
            if not frase.startswith("{x}") and len(x) > 1 and x[0].isupper() and x[1].islower() \
                    and x.split(" ", 1)[0] in {"O", "A", "Os", "As", "Um", "Uma", "Ele", "Ela",
                                               "Isso", "Esse", "Essa", "Este", "Esta"}:
                x = x[0].lower() + x[1:]
            frase = frase.replace("{x}", x)
        return frase[:1].upper() + frase[1:]
