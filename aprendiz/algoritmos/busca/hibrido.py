"""
Busca híbrida: combina BM25, TF-IDF e Fuzzy com Reciprocal Rank Fusion (RRF).

Cada algoritmo tem pontos fortes diferentes e notas em escalas diferentes
(BM25 sem limite, cosseno de 0 a 1, WRatio de 0 a 100). Como misturar?

O RRF ignora as notas e usa só a POSIÇÃO de cada documento em cada lista:

    RRF(doc) = Σ  1 / (k + posição_no_algoritmo_i)        (k = 60, valor clássico)

Um documento que aparece bem colocado em várias listas sobe; um que só um
algoritmo encontrou fica mais abaixo. É simples, robusto e muito usado em
buscadores modernos.

Confiança do híbrido: aceitamos o documento se PELO MENOS UM dos algoritmos
estiver confiante (confiança ≥ seu próprio limiar). A fórmula abaixo produz
0,5 exatamente nesse ponto, e o limiar do híbrido é 0,5.
"""

from __future__ import annotations

from aprendiz.algoritmos.base import (
    BUSCAS, AlgoritmoBusca, Candidato, ContextoBusca, registrar,
)
from aprendiz.linguagem import TextoProcessado

K_RRF = 60
COMPONENTES = ("bm25", "tfidf", "fuzzy")


@registrar
class BuscaHibrida(AlgoritmoBusca):
    nome = "hibrido"
    titulo = "Híbrido (RRF)"
    descricao = "Junta BM25, TF-IDF e Fuzzy pela posição de cada resultado. Mais robusto."
    limiar = 0.5
    explicacao = """
**Ideia:** consultar BM25, TF-IDF e Fuzzy e juntar as três listas usando só a **posição**
de cada resultado: a *Reciprocal Rank Fusion* (RRF).

**Passo a passo**
1. Roda os três algoritmos.
2. Cada conhecimento ganha, de cada algoritmo, `1 / (60 + posição)`:
   - 1º lugar → 1/61 ≈ 0,0164;
   - 2º lugar → 1/62 ≈ 0,0161;
   - fora da lista → 0.
3. Soma tudo e ordena. Quem aparece bem colocado em vários algoritmos sobe.
4. A **confiança** diz se pelo menos **um** dos algoritmos estava seguro: vale 0,5 quando
   algum atinge o próprio limiar.

**Por que a posição, e não a nota?** As notas estão em escalas diferentes (BM25 não tem
limite, o cosseno vai de 0 a 1 e o WRatio de 0 a 100). A posição é comparável.

**Bom para:** o resultado mais robusto. **Limite:** é o mais lento, porque roda os três.
"""

    def buscar(self, consulta: TextoProcessado, ctx: ContextoBusca,
               limite: int = 5) -> list[Candidato]:
        rrf: dict[str, float] = {}
        docs: dict[str, dict] = {}
        relativa: dict[str, float] = {}   # maior confiança/limiar entre os algoritmos
        por_algoritmo: dict[str, dict] = {}

        for nome in COMPONENTES:
            algoritmo = BUSCAS[nome]
            for posicao, cand in enumerate(algoritmo.buscar(consulta, ctx, limite * 2), start=1):
                rrf[cand.id] = rrf.get(cand.id, 0.0) + 1 / (K_RRF + posicao)
                docs[cand.id] = cand.conhecimento
                relativa[cand.id] = max(relativa.get(cand.id, 0.0),
                                        cand.confianca / ctx.limiar(nome))
                por_algoritmo.setdefault(cand.id, {})[nome] = {
                    "posicao": posicao, "confianca": cand.confianca,
                }

        candidatos = [
            Candidato(
                conhecimento=docs[id],
                pontuacao=round(pontos, 5),
                confianca=round(min(1.0, 0.5 * relativa[id]), 4),
                detalhes={"rrf": round(pontos, 5), "algoritmos": por_algoritmo[id]},
            )
            for id, pontos in rrf.items()
        ]
        candidatos.sort(key=lambda c: c.pontuacao, reverse=True)
        return candidatos[:limite]
