"""
Busca calibrada: um reordenador APRENDIDO por regressão logística (2.4).

Os outros algoritmos dão, cada um, uma visão do problema (palavras em comum,
pesos raros, letras parecidas) e o Assistente completa com regras fixas
(folgas do assunto, palavra forte, consenso do Híbrido). O Calibrado troca
essas regras por UMA conta, cujos pesos foram aprendidos com perguntas reais:

    1. Junta os candidatos de BM25, TF-IDF e Fuzzy (o "conjunto de candidatos").
    2. Mede SINAIS de cada candidato: cobertura, cobertura ponderada pela
       raridade, cosseno, semelhança de letras, posição em cada lista, quanto
       a pergunta bate no assunto declarado, pergunta idêntica...
    3. Padroniza cada sinal (z = (x − média) / desvio) e faz a soma ponderada:

           z  = viés + Σ peso_i · sinal_i
           p  = 1 / (1 + e^(−z))          ← função sigmoide (logística)

    4. p é a CHANCE de o candidato ser a resposta (1ª etapa, ordena). Uma
       2ª etapa olha a chance do 1º lugar e a distância para o 2º e dá a
       chance de o 1º estar certo (decide se responde): é a confiança.

Onde está o machine learning? Só no TREINO, que roda na máquina de quem
desenvolve (ferramentas/treinar_calibrado.py, com scikit-learn). O app leva
apenas os números do arquivo calibrado_pesos.py e faz uma soma por candidato:
nenhuma biblioteca nova, nenhum custo extra no dispositivo.
"""

from __future__ import annotations

import math

from aprendiz.algoritmos.base import (
    BUSCAS, AlgoritmoBusca, Candidato, ContextoBusca, registrar,
)
from aprendiz.algoritmos.busca import calibrado_pesos
from aprendiz.algoritmos.busca.hibrido import tem_consenso
from aprendiz.linguagem import TextoProcessado

COMPONENTES = ("bm25", "tfidf", "fuzzy")
POR_COMPONENTE = 10   # candidatos pedidos a cada algoritmo


def sigmoide(z: float) -> float:
    if z >= 0:
        return 1 / (1 + math.exp(-z))
    e = math.exp(z)          # forma estável para z muito negativo
    return e / (1 + e)


def prever(sinais: dict[str, float], modelo: dict | None = None) -> tuple[float, dict[str, float]]:
    """
    Probabilidade de acerto e a contribuição de cada sinal (peso × sinal
    padronizado), para o Monitor.
    """
    modelo = modelo or calibrado_pesos.MODELO
    z = modelo["vies"]
    contribuicoes = {}
    for nome, media, desvio, peso in zip(modelo["sinais"], modelo["media"],
                                         modelo["desvio"], modelo["pesos"]):
        parte = peso * (sinais.get(nome, 0.0) - media) / (desvio or 1.0)
        contribuicoes[nome] = round(parte, 3)
        z += parte
    return sigmoide(z), contribuicoes


SINAIS_DA_DECISAO = ("nota_do_primeiro", "distancia_do_segundo")


def _logito(p: float) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def sinais_da_decisao(probabilidades: list[float]) -> list[float]:
    """
    Sinais da 2ª etapa, a partir das chances dos candidatos (em ordem): a nota
    do 1º lugar e a distância para o 2º, em logitos (log(p / (1 − p))), a
    escala em que a regressão logística soma.
    """
    primeiro = _logito(probabilidades[0])
    segundo = _logito(probabilidades[1]) if len(probabilidades) > 1 else _logito(0.0)
    return [primeiro, primeiro - segundo]


def chance_de_responder_certo(probabilidades: list[float], modelo: dict | None = None) -> float:
    """2ª etapa: a chance de o 1º lugar ser a resposta certa (decide se responde)."""
    modelo = modelo or calibrado_pesos.MODELO
    decisao = modelo.get("decisao")
    if not decisao or not probabilidades:
        return probabilidades[0] if probabilidades else 0.0
    z = decisao["vies"] + sum(p * s for p, s in zip(decisao["pesos"],
                                                     sinais_da_decisao(probabilidades)))
    return sigmoide(z)


def cobertura_idf(termos: list[str], doc_termos: set[str], idf: dict[str, float],
                  idf_ausente: float) -> float:
    """
    Cobertura ponderada pela raridade: termos raros pesam mais. Um termo que
    não existe na base ("banco" em "senha do banco") pesa o máximo, então
    não ser coberto custa caro, ao contrário da cobertura simples, que conta
    "senha" e "banco" como metade cada.
    """
    unicos = set(termos)
    if not unicos:
        return 0.0
    total = sum(idf.get(t, idf_ausente) for t in unicos)
    coberto = sum(idf.get(t, idf_ausente) for t in unicos if t in doc_termos)
    return coberto / total if total else 0.0


@registrar
class BuscaCalibrada(AlgoritmoBusca):
    nome = "calibrado"
    titulo = "Calibrado (aprendido)"
    apelido = "Calibrado"
    quando_usar = "Uso geral: junta todos os sinais numa probabilidade aprendida com perguntas reais."
    custo = "pesado"
    descricao = "Pesa todos os sinais com pesos aprendidos. A confiança é a chance de acerto."
    # O limiar vem do CUSTO de cada saída. Responder com chance p vale
    # p·(+1) + (1 − p)·(−1) = 2p − 1; recusar custa −r. Com r = 0,5 (dizer "não
    # sei" custa metade de uma resposta errada), compensa responder quando
    # 2p − 1 > −0,5, ou seja, p > 0,25. Quem quiser mais cautela sobe o limiar.
    limiar = 0.25
    # O Assistente não aplica as folgas fixas do assunto a este algoritmo:
    # os mesmos sinais já entram na conta, com o peso que o treino mediu.
    aprendido = True
    explicacao = """
**Ideia:** em vez de regras fixas ("aceite até 80% do limiar se bater no assunto"), uma conta
com **pesos aprendidos** a partir de perguntas reais.

**Passo a passo**
1. Junta os candidatos de BM25, TF-IDF e Fuzzy.
2. Mede os **sinais** de cada um: palavras em comum, palavras raras em comum, cosseno,
   letras parecidas, posição em cada lista, quanto a pergunta bate no assunto declarado,
   pergunta idêntica a uma variação e as próprias regras fixas (consenso do Híbrido e folgas
   do BM25), que viram sinais como os outros.
3. **1ª etapa (ordena):** soma ponderada dos sinais, passada pela **sigmoide**
   `p = 1 / (1 + e^(−z))`: a chance de cada candidato ser a resposta.
4. **2ª etapa (decide):** olhando a chance do 1º lugar e a distância para o 2º, a chance de
   o 1º estar certo. Ela é a confiança.
5. **Limiar 0,25**, tirado do custo: responder certo vale +1, errado −1 e "não sei" −0,5.
   Responder compensa quando `2p − 1 > −0,5`, isto é, `p > 0,25`. Com limiar 0,5, ele só
   responde quando acertar é mais provável do que errar.

**De onde vêm os pesos?** De uma **regressão logística** treinada com as variações das
perguntas dos addons (`ferramentas/treinar_calibrado.py`, com scikit-learn, só na máquina de
quem desenvolve). O app leva só os números: nenhuma biblioteca a mais.

**Bom para:** uso geral; o Monitor mostra quanto cada sinal pesou.
**Limite:** roda os três algoritmos, como o Híbrido; e só sabe o que o treino viu.
"""

    # ------------------------------------------------------------------ sinais
    def _conjunto(self, consulta: TextoProcessado, ctx: ContextoBusca) -> dict[str, dict]:
        """Candidatos dos três algoritmos, com posição e confiança de cada um."""
        conjunto: dict[str, dict] = {}
        for nome in COMPONENTES:
            for pos, cand in enumerate(BUSCAS[nome].buscar(consulta, ctx, POR_COMPONENTE), 1):
                item = conjunto.setdefault(cand.id, {"doc": cand.conhecimento})
                item[nome] = (pos, cand.confianca)
        return conjunto

    def sinais(self, consulta: TextoProcessado, ctx: ContextoBusca) -> list[tuple[dict, dict]]:
        """(conhecimento, sinais) de cada candidato. Usado pela busca e pelo treino."""
        conjunto = self._conjunto(consulta, ctx)
        if not conjunto:
            return []
        indice = BUSCAS["tfidf"]._indice(ctx)
        idf = indice["idf"]
        idf_ausente = math.log(len(indice["docs"]) + 1) + 1
        termos = list(dict.fromkeys(consulta.radicais))
        assunto = getattr(ctx, "sinais_assunto", None)

        linhas = []
        for item in conjunto.values():
            doc = item["doc"]
            doc_termos = set((doc.get("texto_busca") or "").split())
            s: dict[str, float] = {}
            for nome in COMPONENTES:
                pos, conf = item.get(nome, (0, 0.0))
                s[f"{nome}_conf"] = conf
                s[f"{nome}_rank"] = 1 / pos if pos else 0.0
            s["cobertura_idf"] = cobertura_idf(termos, doc_termos, idf, idf_ausente)
            s["termos"] = min(len(termos), 6) / 6
            # De propósito, nenhum sinal diz DE ONDE o conhecimento veio (dono ou
            # addon, com teia ou sem, nota ou pergunta): o treino só tem perguntas
            # de addons, e o modelo aprenderia a desconfiar do que o dono ensinou.
            if assunto:
                s.update(assunto(consulta, doc))
            linhas.append((doc, s))

        # Sinal relativo: o candidato que bate MAIS que todos no assunto.
        if linhas and "assunto" in linhas[0][1]:
            maior = max(s["assunto"] for _, s in linhas)
            unico = sum(1 for _, s in linhas if s["assunto"] == maior) == 1
            for _, s in linhas:
                s["melhor_assunto"] = float(maior > 0 and unico and s["assunto"] == maior)

        # As regras fixas também viram sinais: o consenso do Híbrido e a
        # aceitação do BM25 com as folgas do assunto. O modelo aprende quanto
        # confiar em cada regra, em vez de obedecer a ela sempre.
        for item, (doc, s) in zip(conjunto.values(), linhas):
            por_algoritmo = {n: {"posicao": item[n][0], "confianca": item[n][1]}
                             for n in COMPONENTES if n in item}
            s["consenso_hibrido"] = float(tem_consenso(por_algoritmo, consulta, doc, ctx)[0])
            if "assunto" in s:
                folga = 1.0
                if s["assunto"] and (s["palavras_assunto"] >= 0.5 or s["palavra_forte"]):
                    folga = 0.6 if s["melhor_assunto"] else 0.8
                s["regras_bm25"] = float(s["bm25_conf"] >= folga * ctx.limiar("bm25")
                                         and bool(s["cobre_assunto"]))
        return linhas

    # ------------------------------------------------------------------ busca
    def buscar(self, consulta: TextoProcessado, ctx: ContextoBusca,
               limite: int = 5) -> list[Candidato]:
        # 1ª etapa: a chance de cada candidato ser a resposta (ORDENA).
        # Modelo em uso: o ajuste pessoal do dono (2.6) ou o oficial.
        modelo = getattr(ctx, "modelo_calibrado", None) or calibrado_pesos.MODELO
        candidatos = []
        for doc, s in self.sinais(consulta, ctx):
            p, contribuicoes = prever(s, modelo)
            principais = dict(sorted(contribuicoes.items(), key=lambda kv: -abs(kv[1]))[:5])
            candidatos.append(Candidato(
                conhecimento=doc,
                pontuacao=round(p, 4),
                confianca=0.0,
                # Tudo o que o Monitor precisa para refazer a conta: os sinais
                # brutos, a parte de cada um na soma (peso × sinal padronizado),
                # o viés e z, que passa pela sigmoide.
                detalhes={"chance": round(p, 4), "sinais_que_mais_pesaram": principais,
                          "sinais": {k: round(v, 4) for k, v in s.items()},
                          "contribuicoes": contribuicoes,
                          "vies": round(modelo["vies"], 4),
                          "z": round(modelo["vies"] + sum(contribuicoes.values()), 4),
                          "modelo": "pessoal" if "pessoal" in modelo else "oficial"},
            ))
        if not candidatos:
            return []
        candidatos.sort(key=lambda c: c.pontuacao, reverse=True)

        # 2ª etapa: a chance de o 1º lugar estar certo (DECIDE se responde).
        # Ela é a confiança do 1º; os outros ficam na mesma proporção, abaixo dele.
        notas = [c.pontuacao for c in candidatos]
        certo = chance_de_responder_certo(notas, modelo)
        for c in candidatos:
            c.confianca = round(certo * (c.pontuacao / notas[0] if notas[0] else 0.0), 4)
        candidatos[0].detalhes["chance_de_estar_certo"] = round(certo, 4)
        candidatos[0].detalhes["decisao"] = dict(zip(SINAIS_DA_DECISAO,
                                                     (round(x, 4) for x in sinais_da_decisao(notas))))
        return candidatos[:limite]
