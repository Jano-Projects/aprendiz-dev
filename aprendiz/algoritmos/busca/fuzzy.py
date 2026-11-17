"""
Busca aproximada (fuzzy) com a biblioteca rapidfuzz.

Os outros algoritmos comparam TERMOS EXATOS (radicais). O fuzzy compara
SEQUÊNCIAS DE CARACTERES, então tolera:

    • erros de digitação que escaparam do corretor  ("horaro", "farmcia")
    • palavras grudadas ou separadas                 ("wi fi" × "wifi")
    • ordem diferente das palavras

A base é a distância de Levenshtein: o número mínimo de inserções,
remoções e trocas de letras para transformar um texto no outro.
A rapidfuzz converte isso numa nota de 0 a 100 e oferece vários
"comparadores". Usamos o WRatio, que combina alguns deles e lida bem
com textos de tamanhos diferentes (pergunta curta × nota longa).

Compara as palavras de conteúdo SEM radicalizar (a radicalização
"estragaria" a comparação de letras).
"""

from __future__ import annotations

from rapidfuzz import fuzz, process

from aprendiz.algoritmos.base import AlgoritmoBusca, Candidato, ContextoBusca, registrar
from aprendiz.linguagem import TextoProcessado


@registrar
class BuscaFuzzy(AlgoritmoBusca):
    nome = "fuzzy"
    titulo = "Fuzzy (tolerante a erros)"
    descricao = "Compara letra a letra. Bom para erros de digitação e textos curtos."
    limiar = 0.75
    explicacao = """
**Ideia:** comparar **letras**, não palavras inteiras, para tolerar erros de digitação.

**Passo a passo**
1. Pega as palavras importantes da pergunta (sem radicalizar): "farmcia horario".
2. Compara com a **pergunta** de cada par ensinado (ou com o conteúdo, no caso de notas).
3. A comparação usa a **distância de Levenshtein**: quantas letras é preciso inserir, apagar
   ou trocar para transformar um texto no outro. A biblioteca RapidFuzz converte isso numa
   nota de 0 a 100 (o comparador WRatio também lida com ordem e tamanhos diferentes).
4. A **confiança** é a nota ÷ 100.

**Exemplo:** "farmcia" × "farmácia" → falta 1 letra em 8, nota alta.

**Bom para:** erros de digitação e textos curtos. **Limite:** perde para os outros em notas
longas, onde a pergunta é só uma pequena parte do texto.
"""

    def _indice(self, ctx: ContextoBusca) -> dict:
        cache = ctx.cache.get(self.nome)
        if cache and cache["versao"] == ctx.banco.versao_conhecimento:
            return cache

        docs = ctx.banco.conhecimentos_ativos()
        textos = {}
        for doc in docs:
            # Para pares pergunta/resposta, a PERGUNTA é o melhor alvo de
            # comparação; para notas e trechos, o próprio conteúdo.
            alvo = doc["pergunta"] or doc["conteudo"]
            textos[doc["id"]] = " ".join(ctx.linguagem.processar(alvo, corrigir=False).conteudo)

        cache = {"versao": ctx.banco.versao_conhecimento,
                 "docs": {d["id"]: d for d in docs}, "textos": textos}
        ctx.cache[self.nome] = cache
        return cache

    def buscar(self, consulta: TextoProcessado, ctx: ContextoBusca,
               limite: int = 5) -> list[Candidato]:
        indice = self._indice(ctx)
        alvo = " ".join(consulta.conteudo)
        if not alvo or not indice["textos"]:
            return []

        # extract devolve [(texto, nota, chave), ...] já ordenado pela nota.
        achados = process.extract(alvo, indice["textos"], scorer=fuzz.WRatio, limit=limite)
        return [
            Candidato(
                conhecimento=indice["docs"][chave],
                pontuacao=round(nota, 2),
                confianca=round(nota / 100, 4),
                detalhes={"wratio": round(nota, 2)},
            )
            for _texto, nota, chave in achados
            if nota > 0
        ]
