"""
Busca TF-IDF + similaridade do cosseno, implementada em Python puro.

É o algoritmo mais DIDÁTICO do projeto: dá para seguir cada conta.

1) TF-IDF transforma cada texto em um vetor de pesos:

       peso(termo, doc) = TF × IDF
       TF  = quantas vezes o termo aparece no documento
       IDF = log((N + 1) / (df + 1)) + 1
             N  = total de documentos
             df = em quantos documentos o termo aparece

   Termos que aparecem em todo lugar (IDF baixo) pesam pouco;
   termos raros e específicos pesam muito.

2) Similaridade do cosseno compara dois vetores pelo ÂNGULO entre eles:

       cos(A, B) = (A · B) / (|A| × |B|)

   Vai de 0 (nada em comum) a 1 (mesma "direção", mesmos termos na mesma
   proporção). Como normalizamos os vetores dos documentos ao montar o
   índice, basta um produto escalar na hora da busca.

O índice fica em memória e só é reconstruído quando a base muda
(comparando banco.versao_conhecimento).
"""

from __future__ import annotations

import math
from collections import Counter

from aprendiz.algoritmos.base import AlgoritmoBusca, Candidato, ContextoBusca, registrar
from aprendiz.linguagem import TextoProcessado


def _normalizar_vetor(vetor: dict[str, float]) -> dict[str, float]:
    norma = math.sqrt(sum(v * v for v in vetor.values()))
    return {t: v / norma for t, v in vetor.items()} if norma else vetor


@registrar
class BuscaTFIDF(AlgoritmoBusca):
    nome = "tfidf"
    titulo = "TF-IDF + cosseno"
    apelido = "Didático"
    quando_usar = "Para estudar como uma busca funciona; bases pequenas e médias."
    custo = "leve"
    descricao = "Vetores de pesos comparados pelo ângulo. Didático e equilibrado."
    limiar = 0.25
    explicacao = """
**Ideia:** transformar cada texto num **vetor de pesos** e comparar a direção dos vetores.

**Passo a passo**
1. Para cada termo de cada conhecimento, calcula o peso **TF × IDF**:
   - TF = quantas vezes o termo aparece no texto;
   - IDF = `log((N+1)/(df+1)) + 1`, que é alto para termos raros na base.
2. Normaliza cada vetor (comprimento 1).
3. Faz o mesmo com a pergunta e calcula a **similaridade do cosseno**: a soma dos produtos
   dos pesos dos termos em comum. 1 = mesma direção, 0 = nada em comum.
4. A **confiança** é o próprio cosseno.

**Exemplo:** "que horas a farmácia abre" ainda encontra "horário da farmácia → 8h às 20h",
porque `farmac` é um termo raro, de peso alto, e domina a comparação.

**Bom para:** estudar (dá para conferir cada conta à mão) e para perguntas escritas de outro
jeito. **Limite:** monta o índice na memória, o que pesa mais em bases muito grandes.
"""

    def _indice(self, ctx: ContextoBusca) -> dict:
        cache = ctx.cache.get(self.nome)
        if cache and cache["versao"] == ctx.banco.versao_conhecimento:
            return cache

        docs = ctx.banco.conhecimentos_ativos()
        termos_por_doc = [doc["texto_busca"].split() for doc in docs]
        n = len(docs)

        df: Counter[str] = Counter()
        for termos in termos_por_doc:
            df.update(set(termos))
        idf = {t: math.log((n + 1) / (f + 1)) + 1 for t, f in df.items()}

        vetores = []
        for termos in termos_por_doc:
            tf = Counter(termos)
            vetores.append(_normalizar_vetor({t: c * idf[t] for t, c in tf.items()}))

        cache = {"versao": ctx.banco.versao_conhecimento, "docs": docs,
                 "vetores": vetores, "idf": idf}
        ctx.cache[self.nome] = cache
        return cache

    def buscar(self, consulta: TextoProcessado, ctx: ContextoBusca,
               limite: int = 5) -> list[Candidato]:
        indice = self._indice(ctx)
        if not consulta.radicais or not indice["docs"]:
            return []

        idf = indice["idf"]
        tf = Counter(consulta.radicais)
        # Termos que não existem em nenhum documento não contribuem.
        vetor_q = _normalizar_vetor({t: c * idf[t] for t, c in tf.items() if t in idf})
        if not vetor_q:
            return []

        resultados = []
        for doc, vetor_d in zip(indice["docs"], indice["vetores"]):
            similaridade = sum(peso * vetor_d.get(t, 0.0) for t, peso in vetor_q.items())
            if similaridade > 0:
                resultados.append(Candidato(
                    conhecimento=doc,
                    pontuacao=round(similaridade, 4),
                    confianca=round(similaridade, 4),
                    detalhes={"cosseno": round(similaridade, 4)},
                ))

        resultados.sort(key=lambda c: c.pontuacao, reverse=True)
        return resultados[:limite]
