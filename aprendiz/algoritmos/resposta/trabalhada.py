"""
Resposta trabalhada (2.0): o fato encontrado + a cadeia de porquês da teia,
dita com as frases dos addons de linguagem.

Não inventa nada: cada frase vem de um fragmento ou de um porquê escrito num
addon. O trabalho é ESCOLHER (o caminho que a teia montou), ORDENAR (cada
porquê seguido dos porquês dele, como uma pessoa explicaria) e DIZER (as
frases de expressão).

    Pelo que tenho em **SQL 1 · Básico**:            ← abertura
    O WHERE filtra as linhas da consulta.             ← o fato (fragmento achado)

    Isso porque ele filtra antes de agrupar.          ← porquê nível 1
    A regra é: o GROUP BY junta linhas iguais.        ←   o fragmento ligado (resumo)

    Já o HAVING filtra depois de agrupar.             ← outro porquê nível 1

Sem teia no conhecimento achado, responde como a Direta.
"""

from __future__ import annotations

import re

from aprendiz.algoritmos.base import (
    AlgoritmoResposta, Candidato, ContextoBusca, RespostaGerada, registrar,
)
from aprendiz.linguagem import TextoProcessado

_FIM_FRASE = re.compile(r"(?<=[.!?])\s")
MAX_RESUMO = 220


def resumo(conteudo: str) -> str:
    """A primeira frase de um conteúdo (sem blocos de código, listas ou tabelas)."""
    for linha in conteudo.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith(("```", "|", "-", "*", "#", ">")):
            if linha.startswith("```"):
                break   # o resto é código: não serve de resumo
            continue
        frase = _FIM_FRASE.split(linha, maxsplit=1)[0]
        if frase.endswith(":"):
            continue   # "o WHERE filtra as linhas:" apresenta um exemplo; não resume
        return frase if len(frase) <= MAX_RESUMO else frase[:MAX_RESUMO].rsplit(" ", 1)[0] + "…"
    return ""


@registrar
class RespostaTrabalhada(AlgoritmoResposta):
    nome = "trabalhada"
    titulo = "Trabalhada (porquês)"
    apelido = "Explica"
    quando_usar = "Entender o porquê: o fato e a cadeia de motivos que leva até a base."
    custo = "médio"
    descricao = "Responde o fato e explica os porquês, seguindo a teia dos addons."
    explicacao = """
**Ideia:** além de dizer *o quê*, explicar *por quê*, como uma pessoa faria.

**Passo a passo**
1. Pega o caminho de porquês que a teia montou a partir do melhor candidato.
2. Começa pelo fato encontrado.
3. Para cada porquê, diz a explicação e, se ele liga a outro fragmento, um resumo desse
   fragmento, logo em seguida, com os porquês dele (até 3 níveis).
4. Veste cada parte com as frases de expressão dos addons de linguagem.

**Bom para:** addons com teia ("F:", "Q:" no perguntas.txt).
**Limite:** só explica o que os addons escreveram; sem teia, responde como a Direta.
"""

    def responder(self, consulta: TextoProcessado, candidatos: list[Candidato],
                  ctx: ContextoBusca) -> RespostaGerada:
        melhor = candidatos[0]
        caminho = ctx.caminho
        if caminho is None or not caminho.usados or ctx.expressao is None:
            return RespostaGerada(melhor.conhecimento["conteudo"], [melhor.id],
                                  {"usado": melhor.id, "teia": False})
        dizer = ctx.expressao.dizer
        partida = caminho.partida

        addon_id = partida.get("addon_id")
        if addon_id:
            addon = ctx.banco.obter_addon(addon_id) or {}
            abertura = dizer("abertura_addon", addon.get("nome") or addon_id)
        else:
            abertura = dizer("abertura_dono")
        partes = [f"{abertura}\n\n{partida['conteudo']}" if abertura else partida["conteudo"]]

        # Filhos de cada fragmento (pelo id), para contar a cadeia em profundidade:
        # o porquê e, logo depois, os porquês do fragmento que ele liga.
        filhos: dict[str, list] = {}
        for passo in caminho.usados:
            filhos.setdefault(passo.origem_id, []).append(passo)

        fontes = [melhor.id]

        def contar(passo) -> str:
            frases = []
            if passo.texto:
                frases.append(dizer(passo.relacao, passo.texto))
            destino = passo.para
            if destino is not None and not passo.cortado:
                fontes.append(destino["id"])
                # O porquê escrito já diz o essencial do elo; o resumo do
                # fragmento ligado só entra quando o porquê não tem texto.
                trecho = "" if passo.texto else resumo(destino["conteudo"])
                if trecho:
                    frases.append(dizer(passo.relacao, trecho))
                for filho in filhos.get(destino["id"], []):
                    frases.append(contar(filho))
            return " ".join(f for f in frases if f)

        for passo in filhos.get(partida["id"], []):
            texto = contar(passo)
            if texto:
                partes.append(texto)
        fechamento = dizer("fechamento")
        if fechamento:
            partes.append(fechamento)
        return RespostaGerada(
            texto="\n\n".join(partes),
            fontes=list(dict.fromkeys(fontes)),
            detalhes={"usado": melhor.id, "teia": True, "porques": len(caminho.usados)},
        )
