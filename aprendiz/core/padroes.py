"""
Padrões de frase (2.0): o SENTIDO que vem da estrutura da frase, não das
palavras soltas. Os padrões são dados (seção "padroes" do compreensao.json
dos addons); o app só sabe casar e reescrever.

    "quantos pedidos cada cliente fez"
     └ padrão "quantos * cada *"  →  conceitos: agrupar, contar
       as lacunas ("pedidos", "cliente") são EXEMPLOS, não o assunto

    pergunta reescrita para a busca: "quantos cada fez agrupar contar"

A busca por palavras sozinha via "pedidos" e "cliente" e respondia sobre o
banco de exemplo, que fala muito de pedidos e clientes. Quem lê a frase
inteira entende que a pessoa quer CONTAR POR GRUPO; o padrão guarda esse
entendimento.

Sintaxe de um padrão (já normalizado: minúsculas, sem acento, números em
algarismos):

    palavra        a palavra exata
    a|b|c          uma das alternativas
    *              uma lacuna de 1 a 3 palavras (o exemplo)
    <n>            um número

Um padrão casa em qualquer ponto da frase. Se vários casam, todos valem.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

MAX_LACUNA = 3


def compilar(padrao: str) -> re.Pattern:
    partes = []
    for i, peca in enumerate(padrao.split()):
        if peca == "*":
            partes.append(rf"(?P<l{i}>\S+(?:\s\S+){{0,{MAX_LACUNA - 1}}}?)")
        elif peca == "<n>":
            partes.append(r"\d+")
        else:
            partes.append("(?:" + "|".join(re.escape(a) for a in peca.split("|")) + ")")
    return re.compile(r"(?:^|(?<=\s))" + r"\s".join(partes) + r"(?=\s|$)")


@dataclass
class Leitura:
    """O que os padrões viram numa frase."""

    padroes: list[str] = field(default_factory=list)
    conceitos: list[str] = field(default_factory=list)
    exemplos: list[str] = field(default_factory=list)
    texto: str = ""                      # a frase reescrita para a busca

    def como_dict(self) -> dict[str, Any]:
        return {"padrões": "; ".join(self.padroes), "conceitos": ", ".join(self.conceitos),
                "exemplos (fora da busca)": ", ".join(self.exemplos) or "—",
                "busca com": self.texto}


class Padroes:
    def __init__(self, banco) -> None:
        self.banco = banco
        self._versao = -1
        self._lista: list[tuple[str, re.Pattern, list[str]]] = []

    def _atualizar(self) -> None:
        if self._versao == self.banco.versao_linguagem:
            return
        lista = []
        for _, bruto in self.banco.recursos_ativos("compreensao.json"):
            for item in json.loads(bruto).get("padroes") or []:
                lista.append((item["padrao"], compilar(item["padrao"]), item["conceitos"]))
        self._lista, self._versao = lista, self.banco.versao_linguagem

    def ler(self, normalizado: str) -> Leitura | None:
        """Os padrões que casam com a frase (já normalizada); None se nenhum."""
        self._atualizar()
        leitura = Leitura()
        tirar: set[int] = set()        # posições (em palavras) das lacunas
        for texto_padrao, regex, conceitos in self._lista:
            achado = regex.search(normalizado)
            if not achado:
                continue
            leitura.padroes.append(texto_padrao)
            leitura.conceitos += [c for c in conceitos if c not in leitura.conceitos]
            for nome, valor in achado.groupdict().items():
                if valor is None:
                    continue
                inicio = len(normalizado[:achado.start(nome)].split())
                tirar.update(range(inicio, inicio + len(valor.split())))
        if not leitura.padroes:
            return None
        palavras = normalizado.split()
        leitura.exemplos = [p for i, p in enumerate(palavras) if i in tirar]
        restantes = [p for i, p in enumerate(palavras) if i not in tirar]
        leitura.texto = " ".join(restantes + leitura.conceitos)
        return leitura
