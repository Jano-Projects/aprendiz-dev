"""
Recomendação de algoritmos para um addon: qual BUSCA e qual RESPOSTA usar.

Em vez de "achismo", a recomendação vem de um TESTE com o próprio conteúdo:

    1. Monta um Aprendiz temporário (banco num arquivo descartável) e instala
       nele só os itens do addon, com a linguagem do addon.
    2. Para cada item, faz perguntas parecidas com as que alguém faria:
           • a própria pergunta (ou "o que significa <palavra>", num verbete)
             e até três das suas variações;
           • a pergunta com um erro de digitação;
           • para notas e trechos, o começo do texto.
    3. Conta, para cada algoritmo de busca, quantas vezes o item certo veio
       em PRIMEIRO lugar e acima do limiar (acerto@1).
    4. Recomenda o que mais acertou. Empate → o mais leve, nesta ordem:
       BM25, TF-IDF, Híbrido, Fuzzy.

A resposta recomendada depende do formato do conteúdo: textos longos
(notas e trechos com mais de 400 caracteres) pedem a Extrativa, que monta a
resposta com as frases mais relevantes; pares curtos pedem a Direta.

Para addons grandes, o teste usa uma amostra de até 150 itens espalhados
pela lista, o que leva poucos segundos.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Any

PREFERENCIA = ["bm25", "tfidf", "hibrido", "fuzzy"]   # desempate: o mais leve primeiro
AMOSTRA_MAXIMA = 150
TEXTO_LONGO = 400


def _com_erro(texto: str) -> str | None:
    """Troca duas letras do meio da palavra mais longa: "farmacia" → "framacia"."""
    palavras = texto.split()
    if not palavras:
        return None
    maior = max(palavras, key=len)
    if len(maior) < 5:
        return None
    meio = len(maior) // 2
    trocada = maior[:meio - 1] + maior[meio] + maior[meio - 1] + maior[meio + 1:]
    return texto.replace(maior, trocada, 1)


def perguntas_de_teste(item: dict[str, Any]) -> list[str]:
    """As perguntas usadas para testar se a busca encontra este item."""
    tipo = item.get("tipo") or ("pergunta" if item.get("pergunta") else "nota")
    variacoes = list(item.get("variacoes") or [])[:3]  # outros jeitos de perguntar
    if tipo == "verbete":
        return [item["pergunta"], f"o que significa {item['pergunta']}", *variacoes]
    if item.get("pergunta"):
        base = item["pergunta"]
    else:
        # Notas e trechos: as primeiras palavras do texto.
        base = " ".join(re.findall(r"\w+", item["conteudo"])[:8])
    perguntas = [base, *variacoes]
    errada = _com_erro(base)
    if errada:
        perguntas.append(errada)
    return perguntas


def _amostra(itens: list[dict]) -> list[dict]:
    if len(itens) <= AMOSTRA_MAXIMA:
        return itens
    passo = len(itens) / AMOSTRA_MAXIMA
    return [itens[int(i * passo)] for i in range(AMOSTRA_MAXIMA)]


def resposta_recomendada(itens: list[dict]) -> str:
    longos = [k for k in itens if k.get("tipo") in ("nota", "trecho")
              and len(k.get("conteudo", "")) > TEXTO_LONGO]
    if itens and sum(1 for k in itens if k.get("teia")) / len(itens) >= 0.5:
        return "trabalhada"   # 2.0: addon com teia de porquês
    return "extrativa" if itens and len(longos) / len(itens) >= 0.5 else "direta"


# Perguntas que nenhum addon de conhecimento deveria responder (2.0). Uma
# busca que aceita alguma delas "acerta" por ser frouxa, e isso conta contra.
FORA_DO_ASSUNTO = [
    "quem ganhou a copa do mundo de 2002", "como fazer bolo de cenoura",
    "qual a capital da frança", "previsão do tempo para amanhã",
    "quanto custa uma passagem de avião", "me conta uma piada",
]
PESO_FALSOS = 0.5      # cada resposta indevida pesa metade de um acerto


def recomendar(conhecimentos: list[dict[str, Any]],
               linguagem: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """
    Testa os algoritmos com os itens e devolve:

        {"busca": "bm25", "resposta": "direta", "acerto": 0.97,
         "acertos": {"bm25": 0.97, "tfidf": 0.95, ...},
         "falsos": {"bm25": 0.0, ...}, "perguntas": 40}

    A escolha é pela nota = acerto − 0,5 × falsos: a fração de perguntas FORA
    do assunto do addon que a busca respondeu mesmo assim.

    ou None se não houver conhecimentos para testar.
    """
    # Importações aqui dentro: este módulo é usado pelo core e pela
    # ferramenta criar_addon.py, e evita ciclos de importação.
    from aprendiz.addons import criar_pacote
    from aprendiz.algoritmos import BUSCAS
    from aprendiz.core.assistente import Assistente
    from aprendiz.memoria import Banco

    # A variedade (0.8+) depende do manifesto do addon e não muda a busca.
    itens = _amostra([{c: v for c, v in k.items() if c != "variedade"}
                      for k in conhecimentos if k.get("conteudo")])
    if not itens:
        return None

    with tempfile.TemporaryDirectory(prefix="aprendiz-recomendacao-") as pasta:
        banco = Banco(Path(pasta) / "teste.db")
        try:
            assistente = Assistente(banco)
            assistente.instalar_addon(criar_pacote(
                {"id": "teste-recomendacao", "nome": "Teste", "versao": "1.0.0"},
                itens, linguagem or {}))
            # Cada item instalado, na mesma ordem: o id que a busca deve achar.
            instalados = {(k["pergunta"] or "", k["conteudo"]): k["id"]
                          for k in banco.listar_conhecimentos(
                              limite=len(itens) + 10, addon_id="teste-recomendacao")}
            casos = []
            for item in itens:
                alvo = instalados.get(((item.get("pergunta") or ""), item["conteudo"]))
                if alvo:
                    casos += [(pergunta, alvo) for pergunta in perguntas_de_teste(item)]

            acertos: dict[str, float] = {}
            falsos: dict[str, float] = {}
            for nome in BUSCAS:
                certos = 0
                for pergunta, alvo in casos:
                    consulta = assistente.linguagem.processar(pergunta)
                    _, aceitos, _ = assistente.buscar(consulta, nome, limite=3)
                    certos += bool(aceitos) and aceitos[0].id == alvo
                acertos[nome] = round(certos / len(casos), 3) if casos else 0.0
                # 2.0: acertar não basta; não pode responder o que o addon não sabe.
                erros = sum(bool(assistente.buscar(assistente.linguagem.processar(p), nome,
                                                   limite=3)[1]) for p in FORA_DO_ASSUNTO)
                falsos[nome] = round(erros / len(FORA_DO_ASSUNTO), 3)
        finally:
            banco.fechar()

    ordem = [n for n in PREFERENCIA if n in acertos] + [n for n in acertos if n not in PREFERENCIA]
    nota = {n: round(acertos[n] - PESO_FALSOS * falsos[n], 3) for n in acertos}
    melhor = max(ordem, key=lambda n: (nota[n], -ordem.index(n)))
    return {
        "busca": melhor,
        "resposta": resposta_recomendada(itens),
        "acerto": acertos[melhor],
        "acertos": acertos,
        "falsos": falsos,
        "perguntas": len(casos),
    }
