"""
Ajuste pessoal da busca Calibrada (2.6): o modelo aprende com o DONO, no
próprio aparelho, sem internet e sem bibliotecas novas.

De onde vêm os exemplos
    Cada avaliação (tabela `avaliacoes` do banco) diz se um conhecimento era
    ou não a resposta para uma pergunta:

        👍 na resposta                → o conhecimento era o certo
        👎 na resposta                → o conhecimento era o errado
        "não era isso" no chat        → o conhecimento era o errado
        Corrigir                      → o conhecimento novo é o certo e o
                                        que tinha respondido era o errado

    Um 👍 rende mais de um exemplo: se aquele era o certo, os OUTROS
    candidatos da mesma pergunta eram errados. É o mesmo jeito como o treino
    oficial (ferramentas/treinar_calibrado.py) monta os dados.

O que é treinado
    Só a 1ª etapa da Calibrada (os pesos de cada sinal e o viés), por
    descida de gradiente na perda logística, a mesma conta da regressão
    logística do treino oficial. A 2ª etapa (decidir se responde) fica igual.

Por que ele não "esquece" o oficial
    Com poucos exemplos, um modelo livre decoraria a última semana de uso e
    estragaria o resto. Por isso a perda tem um termo que PUXA cada peso de
    volta para o oficial (regularização L2 em direção ao modelo oficial, em
    vez de em direção a zero):

        perda = média das perdas logísticas
                + λ / (2n) · Σ (peso − peso_oficial)²

    λ (LAMBDA) é a força dessa âncora. Com poucas avaliações quase nada
    muda; com muitas, a sua opinião passa a pesar mais que a âncora.

Tudo aqui é função pura (sem banco): quem chama (core/assistente.py) passa
as avaliações e uma função que calcula os sinais de uma pergunta.
"""

from __future__ import annotations

import json
import math
from typing import Callable

from aprendiz.algoritmos.busca.calibrado import sigmoide

MIN_AVALIACOES = 5        # menos que isso, não treina
MAX_AVALIACOES = 300      # só as mais recentes (treino rápido em máquina fraca)
OUTROS_POR_ACERTO = 4     # candidatos errados tirados de cada 👍
LAMBDA = 5.0              # força da âncora no modelo oficial
ITERACOES = 200
PASSO = 0.5               # tamanho de cada passo do gradiente

Exemplo = tuple[list[float], int]   # (sinais padronizados, 1 = certo / 0 = errado)


def padronizar(sinais: dict[str, float], modelo: dict) -> list[float]:
    """Mesma padronização da Calibrada: z = (x − média) / desvio."""
    return [(sinais.get(n, 0.0) - m) / (d or 1.0)
            for n, m, d in zip(modelo["sinais"], modelo["media"], modelo["desvio"])]


def montar_exemplos(avaliacoes: list[dict], sinais_de: Callable[[str], list[tuple[dict, dict]]],
                    modelo: dict) -> tuple[list[Exemplo], list[list[tuple[int, list[float]]]]]:
    """
    Transforma avaliações em exemplos de treino.

    Devolve (exemplos, grupos). Cada grupo é a lista de candidatos de uma
    pergunta com 👍, como (1 se é o certo, sinais): serve para medir se o
    certo ficou em 1º lugar antes e depois do ajuste.
    Avaliação cujo conhecimento não aparece entre os candidatos é pulada:
    não dá para aprender a ordenar o que a busca nem encontrou.
    """
    exemplos: list[Exemplo] = []
    grupos: list[list[tuple[int, list[float]]]] = []
    cache: dict[str, list[tuple[dict, dict]]] = {}
    for a in avaliacoes:
        linhas = cache.get(a["pergunta"])
        if linhas is None:
            linhas = cache[a["pergunta"]] = sinais_de(a["pergunta"])
        alvo = next((s for doc, s in linhas if doc["id"] == a["conhecimento_id"]), None)
        if alvo is None:
            continue
        x = padronizar(alvo, modelo)
        exemplos.append((x, int(a["certo"])))
        if a["certo"]:
            outros = [padronizar(s, modelo) for doc, s in linhas if doc["id"] != a["conhecimento_id"]]
            # Os outros mais fortes primeiro: são os que competiram com o certo.
            outros.sort(key=lambda xo: -_z(xo, modelo["pesos"], modelo["vies"]))
            exemplos.extend((xo, 0) for xo in outros[:OUTROS_POR_ACERTO])
            grupos.append([(1, x)] + [(0, xo) for xo in outros])
    return exemplos, grupos


def _z(x: list[float], pesos: list[float], vies: float) -> float:
    return vies + sum(p * v for p, v in zip(pesos, x))


def treinar(exemplos: list[Exemplo], oficial: dict, lambda_: float = LAMBDA,
            iteracoes: int = ITERACOES, passo: float = PASSO) -> tuple[list[float], float]:
    """
    Descida de gradiente partindo do modelo oficial. Devolve (pesos, viés).

    Gradiente de cada peso j (n = número de exemplos, p = chance prevista):
        ∂perda/∂w_j = [ Σ (p − y) · x_j  +  λ · (w_j − w_oficial_j) ] / n
    """
    w0, b0 = list(oficial["pesos"]), oficial["vies"]
    w, b = list(w0), b0
    n = len(exemplos)
    if not n:
        return w, b
    # Com âncora muito forte, o passo fixo passaria do ponto e divergiria:
    # o termo λ/n do gradiente limita o tamanho do passo.
    passo = passo / max(1.0, lambda_ / n)
    for _ in range(iteracoes):
        gw = [lambda_ * (wj - w0j) for wj, w0j in zip(w, w0)]
        gb = lambda_ * (b - b0)
        for x, y in exemplos:
            erro = sigmoide(_z(x, w, b)) - y
            gb += erro
            for j, xj in enumerate(x):
                gw[j] += erro * xj
        w = [wj - passo * g / n for wj, g in zip(w, gw)]
        b -= passo * gb / n
    return w, b


def acerto_no_topo(grupos: list[list[tuple[int, list[float]]]], pesos: list[float],
                   vies: float) -> float:
    """Fração das perguntas com 👍 em que o certo fica em 1º lugar."""
    if not grupos:
        return 0.0
    ok = sum(max(g, key=lambda item: _z(item[1], pesos, vies))[0] == 1 for g in grupos)
    return ok / len(grupos)


def ajustar(avaliacoes: list[dict], sinais_de: Callable[[str], list[tuple[dict, dict]]],
            oficial: dict, data: str) -> dict | None:
    """
    O ajuste inteiro. Devolve o modelo pessoal (cópia do oficial com pesos e
    viés novos e um resumo em "pessoal") ou None se ainda não há exemplos
    suficientes.
    """
    avaliacoes = avaliacoes[:MAX_AVALIACOES]
    if len(avaliacoes) < MIN_AVALIACOES or not any(a["certo"] for a in avaliacoes):
        return None
    exemplos, grupos = montar_exemplos(avaliacoes, sinais_de, oficial)
    if not any(y for _, y in exemplos):
        return None
    pesos, vies = treinar(exemplos, oficial)
    distancia = math.sqrt(sum((a - b) ** 2 for a, b in zip(pesos, oficial["pesos"]))
                          + (vies - oficial["vies"]) ** 2)
    return {
        **oficial,
        "pesos": [round(p, 6) for p in pesos],
        "vies": round(vies, 6),
        "pessoal": {
            "data": data,
            "avaliacoes": len(avaliacoes),
            "exemplos": len(exemplos),
            "lambda": LAMBDA,
            "distancia_do_oficial": round(distancia, 4),
            "acerto_antes": round(acerto_no_topo(grupos, oficial["pesos"], oficial["vies"]), 4),
            "acerto_depois": round(acerto_no_topo(grupos, pesos, vies), 4),
            "perguntas_com_acerto": len(grupos),
        },
    }


CHAVE_META = "calibrado.pessoal"   # onde o banco guarda o ajuste do dono (tabela meta)


def do_banco(banco, oficial: dict) -> dict | None:
    """O ajuste do DONO gravado no banco, se ainda serve ao modelo oficial."""
    bruto = banco.obter_meta(CHAVE_META)
    modelo = json.loads(bruto) if bruto else None
    return modelo if modelo and compativel(modelo, oficial) else None


def para_arquivo(modelo: dict) -> dict:
    """O ajuste no formato do ajuste.json de um addon (addons/pacote.py)."""
    resumo = modelo.get("pessoal") or {}
    return {"sinais": modelo["sinais"], "pesos": modelo["pesos"], "vies": modelo["vies"],
            "resumo": {"avaliacoes": resumo.get("avaliacoes", 0),
                       "exemplos": resumo.get("exemplos", 0),
                       "data": (resumo.get("data") or "")[:10]}}


def compativel(pessoal: dict, oficial: dict) -> bool:
    """O ajuste só vale para o modelo oficial que tem os MESMOS sinais (um treino
    oficial novo, com outros sinais, invalida o ajuste antigo)."""
    return pessoal.get("sinais") == oficial["sinais"] and \
        len(pessoal.get("pesos") or []) == len(oficial["sinais"])
