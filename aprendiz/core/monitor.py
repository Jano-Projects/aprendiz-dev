"""
Monitor (2.4): a ficha técnica do "modelo" do Aprendiz e a memória do processo.

O Aprendiz não é uma rede neural, mas tem PARÂMETROS como qualquer modelo de
aprendizado de máquina. Esta ficha os conta por componente, separados em
quatro tipos, para quem estuda saber o que é o quê:

    aprendido      ajustado por um treino a partir de dados rotulados
                   (pesos da busca Calibrada; probabilidades do Naive Bayes)
    estatística    calculado da base, sem rótulo (IDF de cada termo, pesos
                   TF-IDF, médias e desvios usados para padronizar)
    pré-treinado   veio pronto num addon (vetores de palavras, lemas)
    hiperparâmetro escolhido por uma pessoa (limiares, k do RRF, k1 e b do
                   BM25, profundidade da teia, pesos da Extrativa)

Para comparar: um modelo de linguagem pequeno tem centenas de milhões de
parâmetros; o Aprendiz, com os addons da homologação, tem cerca de 1,8 milhão,
e quase todos são pré-treinados (vetores de palavras, quantizados em 1 byte
cada, e lemas). A parte que de fato APRENDE com rótulos tem menos de mil, e
por isso roda em qualquer máquina.

A rota GET /api/modelo devolve esta ficha; a aba Modelo do Monitor a mostra.
"""

from __future__ import annotations

import json
import os
import platform
import sqlite3
import sys
from typing import Any

# Parâmetros fixos do BM25 no FTS5 do SQLite (a função bm25() sem argumentos).
BM25_K1 = 1.2
BM25_B = 0.75


def memoria_mb() -> float | None:
    """Memória residente (RSS) do processo, em MB; None se o sistema não informar."""
    try:   # Linux
        with open("/proc/self/status", encoding="ascii") as f:
            for linha in f:
                if linha.startswith("VmRSS:"):
                    return round(int(linha.split()[1]) / 1024, 1)
    except OSError:
        pass
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class Contadores(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]
            c = Contadores()
            c.cb = ctypes.sizeof(c)
            processo = ctypes.windll.kernel32.GetCurrentProcess()
            if ctypes.windll.psapi.GetProcessMemoryInfo(processo, ctypes.byref(c), c.cb):
                return round(c.WorkingSetSize / 1024 / 1024, 1)
        except (OSError, AttributeError):
            return None
    return None


def _componente(nome: str, tipo: str, tecnica: str, parametros: int, descricao: str,
                detalhes: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"nome": nome, "tipo": tipo, "tecnica": tecnica, "parametros": int(parametros),
            "descricao": descricao, "detalhes": detalhes or {}}


def ficha_do_modelo(assistente) -> dict[str, Any]:
    """Todos os componentes, com a contagem de parâmetros de cada um."""
    from aprendiz import __version__
    from aprendiz.algoritmos import BUSCAS
    from aprendiz.algoritmos.busca import calibrado_pesos
    from aprendiz.algoritmos.busca.hibrido import K_RRF
    from aprendiz.algoritmos.resposta import extrativa
    from aprendiz.core import teia as modulo_teia
    from aprendiz.memoria.banco import teia_de

    banco, ctx = assistente.banco, assistente.contexto
    componentes = []

    # ---- Busca Calibrada: o único componente treinado com rótulos ----------
    m = calibrado_pesos.MODELO
    n = len(m.get("sinais") or [])
    decisao = m.get("decisao") or {}
    nd = len(decisao.get("pesos") or [])
    componentes.append(_componente(
        "Busca Calibrada · 1ª etapa", "aprendido", "Regressão logística (L2)",
        n + 1, "Um peso por sinal mais o viés: a chance de cada candidato ser a resposta.",
        {"sinais": n, "regularização C": m.get("regularizacao"),
         "pesos": dict(zip(m.get("sinais") or [], m.get("pesos") or []))}))
    componentes.append(_componente(
        "Busca Calibrada · 2ª etapa", "aprendido", "Regressão logística",
        nd + 1, "Decide se responde: chance de o 1º lugar estar certo.",
        {"sinais": decisao.get("sinais"), "pesos": decisao.get("pesos"), "viés": decisao.get("vies")}))
    componentes.append(_componente(
        "Busca Calibrada · padronização", "estatística", "z-score (média e desvio do treino)",
        2 * n, "Média e desvio de cada sinal, calculados no treino.", {}))

    # ---- Naive Bayes das intenções -----------------------------------------
    assistente._treinar_classificador()
    nb = assistente.classificador
    classes = len(nb.log_prior)
    vocab = len(nb.vocabulario)
    componentes.append(_componente(
        "Intenções", "aprendido", "Naive Bayes multinomial (Laplace)",
        classes * (vocab + 1), "P(palavra | intenção) para cada palavra e intenção, mais P(intenção).",
        {"classes": classes, "vocabulário": vocab,
         "exemplos": len(banco.exemplos_intencoes(incluir_addons=True))}))

    # ---- Índices de busca ---------------------------------------------------
    tfidf = BUSCAS["tfidf"]._indice(ctx)
    nnz = sum(len(v) for v in tfidf["vetores"])
    componentes.append(_componente(
        "TF-IDF", "estatística", "Vetores esparsos TF×IDF normalizados (L2)",
        len(tfidf["idf"]) + nnz, "Um IDF por termo e um peso por termo presente em cada documento.",
        {"documentos": len(tfidf["docs"]), "termos (IDF)": len(tfidf["idf"]),
         "pesos não nulos": nnz,
         "densidade": round(nnz / (len(tfidf["docs"]) * len(tfidf["idf"])), 5)
         if tfidf["docs"] and tfidf["idf"] else 0}))
    componentes.append(_componente(
        "BM25", "hiperparâmetro", "Okapi BM25 no FTS5 (SQLite)",
        2, "k1 (saturação) e b (ajuste de tamanho); as estatísticas ficam no índice do SQLite.",
        {"k1": BM25_K1, "b": BM25_B, "documentos": len(tfidf["docs"])}))
    fuzzy = BUSCAS["fuzzy"]._indice(ctx)
    componentes.append(_componente(
        "Fuzzy", "hiperparâmetro", "Levenshtein · WRatio (RapidFuzz)",
        0, "Não tem parâmetros: compara letras com cada alvo indexado.",
        {"alvos indexados": len(fuzzy["textos"])}))

    # ---- Addons pré-treinados: vetores e lemas -----------------------------
    dimensoes_total = palavras_total = 0
    for addon_id, dados in banco.recursos_ativos("vetores.info"):
        info = json.loads(dados)
        palavras_total += info.get("quantidade", 0)
        dimensoes_total = info.get("dimensoes", dimensoes_total)
    if palavras_total:
        componentes.append(_componente(
            "Vetores de palavras", "pré-treinado", "Embeddings densos (cosseno)",
            palavras_total * dimensoes_total, "Um vetor por palavra; palavras de sentido parecido apontam para o mesmo lado.",
            {"palavras": palavras_total, "dimensões": dimensoes_total,
             "precisão": "int8 (1 byte por número)",
             "tamanho": f"{palavras_total * dimensoes_total / 1024 / 1024:.1f} MB"}))
    lemas = banco._consultar(
        "SELECT COUNT(*) AS n FROM addon_lexico x JOIN addons a ON a.id = x.addon_id "
        "WHERE a.ativo = 1 AND x.lema IS NOT NULL")[0]["n"]
    if lemas:
        componentes.append(_componente(
            "Lemas", "pré-treinado", "Tabela de lematização",
            lemas, "Forma de dicionário de cada palavra flexionada (\"fui\" → \"ser\").",
            {"formas": lemas}))

    # ---- Teia de porquês: um grafo, sem pesos -------------------------------
    nos = arestas = 0
    for doc in banco.conhecimentos_ativos():
        t = teia_de(doc)
        if t:
            nos += 1
            arestas += len(t.get("porques") or [])
    componentes.append(_componente(
        "Teia de porquês", "hiperparâmetro", "Grafo dirigido · busca em largura (BFS)",
        2, "Profundidade máxima e número máximo de passos; os nós e arestas vêm dos addons.",
        {"nós": nos, "arestas": arestas, "profundidade": modulo_teia.PROFUNDIDADE,
         "passos máximos": modulo_teia.MAX_PASSOS}))

    # ---- Hiperparâmetros das respostas e limiares ---------------------------
    config = assistente.configuracoes.efetivas()
    limiares = {nome: config[f"limiar.{nome}"]["valor"] for nome in BUSCAS
                if f"limiar.{nome}" in config}
    componentes.append(_componente(
        "Limiares e fusões", "hiperparâmetro", "Corte de confiança · Reciprocal Rank Fusion",
        len(limiares) + 1, "Confiança mínima de cada busca e o k do RRF.",
        {**{f"limiar {k}": v for k, v in limiares.items()}, "k do RRF": K_RRF}))
    componentes.append(_componente(
        "Resposta Extrativa", "hiperparâmetro", "TextRank (PageRank em frases)",
        4, "Pesos de relevância e centralidade, frases e conhecimentos usados.",
        {"peso relevância": extrativa.PESO_RELEVANCIA,
         "peso centralidade": extrativa.PESO_CENTRALIDADE,
         "frases": extrativa.MAX_FRASES, "amortecimento d": 0.85}))

    por_tipo: dict[str, int] = {}
    for c in componentes:
        por_tipo[c["tipo"]] = por_tipo.get(c["tipo"], 0) + c["parametros"]
    return {
        "total_parametros": sum(por_tipo.values()),
        "por_tipo": por_tipo,
        "componentes": componentes,
        "treino_calibrado": m.get("treino") or {},
        "base": {
            "conhecimentos": banco.contar_conhecimentos(),
            "de addons": banco.contar_conhecimentos(de_addons=True),
            "addons ativos": sum(1 for a in banco.listar_addons() if a.get("ativo")),
        },
        "ambiente": {
            "aprendiz": __version__,
            "python": platform.python_version(),
            "sqlite": sqlite3.sqlite_version,
            "sistema": f"{platform.system()} {platform.release()}",
            "processadores": os.cpu_count(),
            "memoria_mb": memoria_mb(),
        },
    }
