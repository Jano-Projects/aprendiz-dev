"""
Resposta extrativa: monta a resposta com as FRASES mais relevantes de vários
conhecimentos. Útil para notas longas e trechos de arquivos importados,
onde a resposta está "escondida" no meio de um texto maior.

Passo a passo:

    1. Junta os conhecimentos aceitos e quebra o texto em frases.
    2. Dá uma nota a cada frase, combinando dois critérios:
         • relevância: quantos termos da pergunta a frase contém (0 a 1);
         • centralidade: quanto a frase se parece com as demais (TextRank).
    3. Escolhe as melhores frases e as devolve na ORDEM ORIGINAL,
       para o texto continuar fazendo sentido.

TextRank (Mihalcea & Tarau, 2004) é a ideia do PageRank do Google aplicada
a frases: cada frase "vota" nas frases parecidas com ela. Frases que recebem
muitos votos de frases importantes são importantes. Calculamos por iteração:

    nota(i) = (1 − d) + d · Σ_j  sim(i, j) / Σ_k sim(j, k) · nota(j)

com d = 0,85 (fator de amortecimento) e sim = palavras em comum,
normalizada pelo tamanho das frases.
"""

from __future__ import annotations

import math
import re

from aprendiz.algoritmos.base import (
    AlgoritmoResposta, Candidato, ContextoBusca, RespostaGerada, registrar,
)
from aprendiz.linguagem import TextoProcessado

_SEPARADOR_FRASES = re.compile(r"(?<=[.!?;])\s+|\n+")

MAX_FRASES = 3
MAX_CONHECIMENTOS = 3
PESO_RELEVANCIA = 0.7
PESO_CENTRALIDADE = 0.3


def _similaridade(a: set[str], b: set[str]) -> float:
    """Palavras em comum, normalizada (fórmula do artigo original do TextRank)."""
    if len(a) < 2 or len(b) < 2:
        return float(len(a & b) > 0) * 0.5
    return len(a & b) / (math.log(len(a)) + math.log(len(b)))


def textrank(conjuntos: list[set[str]], d: float = 0.85, iteracoes: int = 30) -> list[float]:
    n = len(conjuntos)
    if n == 0:
        return []
    sim = [[_similaridade(conjuntos[i], conjuntos[j]) if i != j else 0.0
            for j in range(n)] for i in range(n)]
    saida = [sum(linha) or 1.0 for linha in sim]
    notas = [1.0] * n
    for _ in range(iteracoes):
        notas = [
            (1 - d) + d * sum(sim[j][i] / saida[j] * notas[j] for j in range(n))
            for i in range(n)
        ]
    maior = max(notas) or 1.0
    return [x / maior for x in notas]


@registrar
class RespostaExtrativa(AlgoritmoResposta):
    nome = "extrativa"
    titulo = "Extrativa (resumo)"
    descricao = "Junta as frases mais relevantes de vários conhecimentos. Boa para textos longos."
    explicacao = """
**Ideia:** em vez de devolver textos inteiros, **escolher as frases** que respondem à pergunta.

**Passo a passo**
1. Quebra os até 3 melhores conhecimentos em frases.
2. Dá uma nota a cada frase: `0,7 × relevância + 0,3 × centralidade`.
   - **Relevância:** fração dos termos da pergunta presentes na frase.
   - **Centralidade (TextRank):** as frases "votam" nas frases parecidas com elas, como
     o PageRank do Google faz com páginas. Frases que resumem o assunto ficam com nota alta.
3. Devolve as 3 melhores frases, na ordem em que aparecem no texto original.

**Exemplo:** num trecho sobre o carro (óleo, filtro, pneus), a pergunta "calibragem dos
pneus" recebe só a frase dos pneus.

**Bom para:** notas longas e arquivos importados. **Limite:** pode cortar contexto que
estava em outra frase.
"""

    def responder(self, consulta: TextoProcessado, candidatos: list[Candidato],
                  ctx: ContextoBusca) -> RespostaGerada:
        termos = set(consulta.radicais)

        # 1. Frases de cada conhecimento, guardando de onde vieram.
        frases: list[dict] = []
        for ordem, cand in enumerate(candidatos[:MAX_CONHECIMENTOS]):
            for posicao, frase in enumerate(_SEPARADOR_FRASES.split(cand.conhecimento["conteudo"])):
                frase = frase.strip()
                if len(frase) < 2:
                    continue
                radicais = set(ctx.linguagem.processar(frase, corrigir=False).radicais)
                frases.append({"texto": frase, "radicais": radicais,
                               "fonte": cand.id, "ordem": (ordem, posicao)})

        if not frases:
            melhor = candidatos[0]
            return RespostaGerada(melhor.conhecimento["conteudo"], [melhor.id])

        # 2. Nota de cada frase.
        centralidade = textrank([f["radicais"] for f in frases])
        for f, c in zip(frases, centralidade):
            relevancia = len(termos & f["radicais"]) / len(termos) if termos else 0.0
            f["relevancia"] = round(relevancia, 3)
            f["centralidade"] = round(c, 3)
            f["nota"] = round(PESO_RELEVANCIA * relevancia + PESO_CENTRALIDADE * c, 3)

        # 3. Melhores frases (priorizando as que têm algum termo da pergunta),
        #    devolvidas na ordem original.
        relevantes = [f for f in frases if f["relevancia"] > 0] or frases
        escolhidas = sorted(relevantes, key=lambda f: f["nota"], reverse=True)[:MAX_FRASES]
        escolhidas.sort(key=lambda f: f["ordem"])

        texto = " ".join(f["texto"] for f in escolhidas)
        fontes = list(dict.fromkeys(f["fonte"] for f in escolhidas))
        return RespostaGerada(
            texto=texto,
            fontes=fontes,
            detalhes={"frases": [
                {k: f[k] for k in ("texto", "relevancia", "centralidade", "nota")}
                for f in sorted(frases, key=lambda f: f["nota"], reverse=True)[:8]
            ]},
        )
