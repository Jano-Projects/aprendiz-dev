"""
Junta as abreviações e os sinônimos de VÁRIOS addons sem que um estrague o outro.

O problema (até a 0.9): cada addon trazia pares "termo → valor" e o último
instalado sobrescrevia os outros. Com vários addons de idioma ativos:

    addon A:  banco → assento        addon B:  banco → instituicao
    → "banco" virava o que o último addon dissesse, e metade das perguntas se perdia.

    addon A:  automovel → carro      addon B:  carro → veiculo
    → "automovel" parava em "carro" e nunca encontrava "veiculo" (um salto só).

As regras daqui (1.0):

1. O DONO decide. Uma entrada dele vence qualquer addon.
2. CONFLITO: o mesmo termo com valores diferentes em addons diferentes (e sem
   decisão do dono) NÃO é trocado: a palavra fica como foi escrita. Melhor
   não trocar do que trocar pelo sentido errado. O conflito aparece na tela
   "Linguagem", onde o dono escolhe com um clique.
3. CADEIAS (só sinônimos): a → b → c vira a → c e b → c. Um ciclo
   (a → b → a) vira o menor termo do ciclo em ordem alfabética, sempre o mesmo.

Tudo aqui é função pura (sem banco), fácil de testar e de estudar.
"""

from __future__ import annotations

from typing import Iterable


def resolver(entradas_addons: Iterable[tuple[str, str, str]], dono: dict[str, str],
             encadear: bool = False) -> tuple[dict[str, str], list[dict]]:
    """
    entradas_addons: (termo, valor, nome_do_addon) dos addons ATIVOS.
    dono: termo → valor cadastrado pelo dono.
    encadear: True para sinônimos (resolve a → b → c).
    Devolve (mapa final, conflitos).
    """
    opcoes: dict[str, dict[str, list[str]]] = {}   # termo → valor → [addons]
    for termo, valor, addon in entradas_addons:
        opcoes.setdefault(termo, {}).setdefault(valor, []).append(addon)

    mapa: dict[str, str] = {}
    conflitos: list[dict] = []
    for termo, valores in sorted(opcoes.items()):
        if termo in dono:
            continue
        if len(valores) == 1:
            mapa[termo] = next(iter(valores))
        else:
            conflitos.append({"termo": termo, "opcoes": [
                {"valor": v, "addons": sorted(set(a))} for v, a in sorted(valores.items())]})
    mapa.update(dono)

    if encadear:
        mapa = _encadear(mapa)
    # Trocar uma palavra por ela mesma não faz nada; só polui a explicação.
    return {t: v for t, v in mapa.items() if t != v}, conflitos


def _encadear(mapa: dict[str, str]) -> dict[str, str]:
    """Segue cada termo até a forma final; ciclos viram o menor termo do ciclo."""
    final: dict[str, str] = {}
    for inicio in mapa:
        caminho = [inicio]
        atual = inicio
        while atual in mapa and mapa[atual] not in caminho:
            atual = mapa[atual]
            caminho.append(atual)
        if atual in mapa:                          # parou num ciclo
            ciclo = caminho[caminho.index(mapa[atual]):]
            atual = min(ciclo)
        final[inicio] = atual
    return final
