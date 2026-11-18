"""
Busca híbrida: combina BM25, TF-IDF e Fuzzy com Reciprocal Rank Fusion (RRF).

Cada algoritmo tem pontos fortes diferentes e notas em escalas diferentes
(BM25 sem limite, cosseno de 0 a 1, WRatio de 0 a 100). Como misturar?

O RRF ignora as notas e usa só a POSIÇÃO de cada documento em cada lista:

    RRF(doc) = Σ  1 / (k + posição_no_algoritmo_i)        (k = 60, valor clássico)

Um documento que aparece bem colocado em várias listas sobe; um que só um
algoritmo encontrou fica mais abaixo. É simples, robusto e muito usado em
buscadores modernos.

Confiança do híbrido: o RRF só ORDENA (sempre existe um 1º lugar, mesmo
quando nada serve). Para ACEITAR um documento exigimos CONSENSO:

    - o Fuzzy quase idêntico (frase digitada com pequenos erros); ou
    - o BM25 (ou 2 algoritmos) confiante E a pergunta fala do ASSUNTO do
      documento (alguma palavra dela está no título/variações); ou
    - 2 algoritmos confiantes E TODAS as palavras da pergunta no documento; ou
    - TODAS as palavras da pergunta no documento, escritas exatamente igual.

(BM25 e TF-IDF medem quase a mesma coisa, palavras em comum; por isso a
concordância deles, sozinha, não basta.)

Sem consenso, a confiança fica logo abaixo do limiar: o documento continua
na lista (aparece em "Por que respondi isso?"), mas não vira resposta.
Exemplo: "você tem nome?" contém "nome", que aparece numa regra sobre o
trema ("nomes estrangeiros"). Só o BM25 concorda, e "nome" não é o assunto
da regra: recusado.
"""

from __future__ import annotations

from aprendiz.algoritmos.base import (
    BUSCAS, AlgoritmoBusca, Candidato, ContextoBusca, registrar,
)
from aprendiz.linguagem import TextoProcessado

K_RRF = 60
COMPONENTES = ("bm25", "tfidf", "fuzzy")
FUZZY_QUASE_IDENTICO = 0.95   # Fuzzy sozinho só decide se for praticamente a mesma frase
PALAVRAS_TITULO_SEM_PERGUNTA = 12  # sem 'pergunta', o começo do conteúdo faz as vezes de título


def _radicais_do_titulo(doc: dict, ctx: ContextoBusca) -> set[str]:
    """Radicais da pergunta + variações do documento (o seu "assunto"). Fica em cache."""
    cache = ctx.cache.setdefault("hibrido_titulos", {})
    chave = (doc["id"], doc.get("pergunta"), doc.get("variacoes"))
    if chave not in cache:
        from aprendiz.memoria.banco import lista_json
        formas = [doc.get("pergunta") or ""] + lista_json(doc, "variacoes")
        if not any(formas):
            formas = [" ".join((doc.get("conteudo") or "").split()[:PALAVRAS_TITULO_SEM_PERGUNTA])]
        radicais: set[str] = set()
        for forma in formas:
            radicais.update(ctx.linguagem.processar(forma, corrigir=False).radicais)
        cache[chave] = radicais
    return cache[chave]


def _palavras_exatas(doc: dict, ctx: ContextoBusca) -> set[str]:
    """Palavras do documento na forma escrita (normalizada, sem radical). Fica em cache."""
    from aprendiz.linguagem.normalizador import normalizar, tokenizar
    cache = ctx.cache.setdefault("hibrido_palavras", {})
    chave = (doc["id"], doc.get("conteudo"))
    if chave not in cache:
        cache[chave] = set(tokenizar(normalizar(f"{doc.get('pergunta') or ''} {doc.get('conteudo') or ''}")))
    return cache[chave]


def tem_consenso(algoritmos: dict[str, dict], consulta: TextoProcessado,
                 doc: dict, ctx: ContextoBusca) -> tuple[bool, str]:
    """Regra de aceitação do híbrido. Devolve (aceito, motivo) para a explicação."""
    confiantes = [n for n, d in algoritmos.items() if d["confianca"] >= ctx.limiar(n)]
    if algoritmos.get("fuzzy", {}).get("confianca", 0.0) >= FUZZY_QUASE_IDENTICO:
        return True, "fuzzy quase idêntico"
    # BM25 e TF-IDF medem quase a mesma coisa (palavras em comum), então a
    # "concordância" deles sozinha não prova nada. Além dela, exigimos que:
    #   - a pergunta fale do ASSUNTO do documento (título/variações), ou
    #   - TODAS as palavras da pergunta estejam no documento (com 2 algoritmos).
    lexico_ok = len(confiantes) >= 2 or "bm25" in confiantes
    if lexico_ok and set(consulta.radicais) & _radicais_do_titulo(doc, ctx):
        return True, "+".join(confiantes) + "+assunto"
    cobertura_total = algoritmos.get("bm25", {}).get("confianca", 0.0) >= 0.999
    if len(confiantes) >= 2 and cobertura_total:
        return True, "+".join(confiantes) + "+pergunta inteira"
    #   - ou TODAS as palavras da pergunta estejam no documento EXATAMENTE como
    #     foram escritas: "o que é trema?" acha "**trema** abolido"; já "você tem
    #     nome?" só bate com "nomes" (mesmo radical, outra palavra).
    if cobertura_total and consulta.conteudo and set(consulta.conteudo) <= _palavras_exatas(doc, ctx):
        return True, "bm25+palavras exatas"
    return False, ("só " + confiantes[0]) if confiantes else "nenhum confiante"


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
4. Para **aceitar**, exige **consenso**: o Fuzzy quase idêntico; ou o BM25 seguro e a pergunta
   falando do assunto do conhecimento (título/variações); ou 2 algoritmos seguros e todas as
   palavras da pergunta presentes no conhecimento; ou todas presentes exatamente como escritas.
   Sem consenso, o resultado fica logo abaixo do limiar e não vira resposta.

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

        limiar = ctx.limiar(self.nome)
        candidatos = []
        for id, pontos in rrf.items():
            confianca = min(1.0, 0.5 * relativa[id])
            aceito, motivo = tem_consenso(por_algoritmo[id], consulta, docs[id], ctx)
            if not aceito:
                confianca = min(confianca, limiar * 0.98)  # fica logo abaixo do limiar
            candidatos.append(Candidato(
                conhecimento=docs[id],
                pontuacao=round(pontos, 5),
                confianca=round(confianca, 4),
                detalhes={"rrf": round(pontos, 5), "algoritmos": por_algoritmo[id],
                          "consenso": motivo},
            ))
        candidatos.sort(key=lambda c: c.pontuacao, reverse=True)
        return candidatos[:limite]
