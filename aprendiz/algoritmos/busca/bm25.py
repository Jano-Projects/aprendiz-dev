"""
Busca BM25 usando o índice FTS5 do próprio SQLite.

BM25 (Best Matching 25) é o algoritmo clássico dos buscadores — foi o padrão
do Elasticsearch/Lucene por anos. A ideia:

    • Um documento é relevante se contém os termos da pergunta (TF).
    • Termos RAROS valem mais que termos comuns (IDF).
    • Repetir um termo ajuda, mas com retorno decrescente (saturação, k1).
    • Documentos longos são penalizados um pouco (normalização, b).

    score(D, Q) = Σ IDF(q) · f(q,D)·(k1+1) / ( f(q,D) + k1·(1 − b + b·|D|/média) )

Aqui não precisamos implementar a fórmula: o SQLite faz isso em C, dentro do
banco, sem carregar nada na memória. Por isso é o algoritmo PADRÃO —
o mais leve de todos.

Como a pontuação BM25 não tem escala fixa (depende do tamanho da base),
usamos a COBERTURA (fração dos termos da pergunta presentes no documento)
como medida de confiança.
"""

from __future__ import annotations

from aprendiz.algoritmos.base import (
    AlgoritmoBusca, Candidato, ContextoBusca, cobertura, registrar,
)
from aprendiz.linguagem import TextoProcessado


@registrar
class BuscaBM25(AlgoritmoBusca):
    nome = "bm25"
    titulo = "BM25 (padrão)"
    descricao = "Ranking clássico de buscadores, feito pelo próprio SQLite. O mais leve."
    limiar = 0.5  # pelo menos metade dos termos da pergunta precisa aparecer
    explicacao = """
**Ideia:** um conhecimento é relevante quando contém as palavras da pergunta, e as palavras
**raras** valem mais que as comuns.

**Passo a passo**
1. A pergunta vira radicais: "qual a senha do wifi?" → `senh` `wifi`.
2. O SQLite procura, no índice FTS5, os conhecimentos que têm pelo menos um desses radicais.
3. Cada um recebe uma nota BM25, que soma, para cada termo da pergunta:
   - **IDF**: quanto mais raro o termo na base, mais ele vale;
   - **TF com saturação**: repetir o termo ajuda, mas cada vez menos;
   - **ajuste de tamanho**: textos muito longos perdem um pouco.
4. A **confiança** é a cobertura: a fração dos termos da pergunta presentes no conhecimento.

**Exemplo:** "senha do wifi" contra "A senha do wifi é casa123." → os 2 termos aparecem →
cobertura 2/2 = **1,0** (aceito, limiar 0,5).

**Bom para:** uso geral e máquinas fracas, porque tudo roda dentro do SQLite, em C.
**Limite:** palavras diferentes com o mesmo sentido ("horas" × "horário") não se encontram.
"""

    def buscar(self, consulta: TextoProcessado, ctx: ContextoBusca,
               limite: int = 5) -> list[Candidato]:
        termos = list(dict.fromkeys(consulta.radicais))  # únicos, mantendo a ordem
        if not termos:
            return []

        # Sintaxe FTS5: "termo1" OR "termo2" ... As aspas tratam cada radical
        # como literal (os radicais só têm letras/números, mas é boa prática).
        expressao = " OR ".join(f'"{t}"' for t in termos)
        linhas = ctx.banco.buscar_fts(expressao, limite * 3)

        candidatos = []
        for linha in linhas:
            doc = ctx.banco.obter_conhecimento(linha["id"])
            if not doc:
                continue
            cob = cobertura(termos, set(doc["texto_busca"].split()))
            candidatos.append(Candidato(
                conhecimento=doc,
                pontuacao=round(-linha["score"], 4),  # invertido: maior = melhor
                confianca=round(cob, 4),
                detalhes={"bm25": round(-linha["score"], 4), "cobertura": round(cob, 4)},
            ))

        # Ordena por confiança e desempata pelo BM25.
        candidatos.sort(key=lambda c: (c.confianca, c.pontuacao), reverse=True)
        return candidatos[:limite]
