"""
Léxico: lemas e vetores de palavras trazidos pelos addons de compreensão.

Sem nenhum desses addons ativo, nada aqui muda o comportamento do Aprendiz.
Com eles:

  • LEMA — "fui", "foi" e "era" viram "ser"; "fiz" e "fez" viram "fazer".
    O radicalizador (stemmer.py) já junta "falar", "falei" e "falando",
    mas não junta formas irregulares; o lema resolve isso.

  • LÉXICO — saber que "carro" é uma palavra do português evita que a
    correção de digitação a troque por "caro" só porque "caro" está na base.

  • VETORES — números que representam o sentido aproximado de cada palavra.
    Dois vetores apontando para a mesma direção = palavras de sentido
    parecido. A semelhança é o cosseno do ângulo entre eles:

        cosseno(a, b) = (a · b) / (|a| × |b|)      → 1 = mesmo sentido

As palavras ficam no SQLite (podem ser centenas de milhares); aqui só
guardamos em memória as consultadas por último (cache LRU), e os vetores
de cada addon são lidos uma vez, como um bloco de bytes.
"""

from __future__ import annotations

import json
import math
from array import array
from collections import OrderedDict


class _CacheLRU(OrderedDict):
    """Dicionário que esquece o item usado há mais tempo quando enche."""

    def __init__(self, maximo: int) -> None:
        super().__init__()
        self.maximo = maximo

    def guardar(self, chave, valor) -> None:
        self[chave] = valor
        self.move_to_end(chave)
        if len(self) > self.maximo:
            self.popitem(last=False)


class Lexico:
    TAMANHO_CACHE = 50_000

    def __init__(self, banco) -> None:
        self.banco = banco
        self._versao = -1
        self._cache = _CacheLRU(self.TAMANHO_CACHE)
        self._blocos: dict[str, tuple[int, bytes, int]] = {}  # addon_id → (dimensões, dados, quantidade)
        self.tem_lemas = False
        self.tem_vetores = False

    def _atualizar(self) -> None:
        """Addons mudaram (instalados, ativados...)? Esquece o que sabia."""
        if self._versao != self.banco.versao_linguagem:
            self._cache.clear()
            self._blocos.clear()
            self.tem_lemas, self.tem_vetores = self.banco.tem_lexico()
            self._versao = self.banco.versao_linguagem

    def _consultar(self, palavra: str) -> tuple[str | None, tuple[str, int] | None]:
        self._atualizar()
        if not (self.tem_lemas or self.tem_vetores):
            return None, None
        if palavra in self._cache:
            self._cache.move_to_end(palavra)
            return self._cache[palavra]
        resultado = self.banco.consultar_lexico(palavra)
        self._cache.guardar(palavra, resultado)
        return resultado

    # ------------------------------------------------------------------ lemas
    def lema(self, palavra: str) -> str | None:
        """O lema da palavra, ou None se ela não tem lema diferente."""
        lema, _ = self._consultar(palavra)
        return lema or None

    def conhece(self, palavra: str) -> bool:
        """A palavra existe no português (segundo os addons ativos)?"""
        lema, vetor = self._consultar(palavra)
        return lema is not None or vetor is not None

    # ------------------------------------------------------------------ vetores
    def sem_relacao(self, a: str, b: str) -> bool:
        """
        Duas palavras com o mesmo começo são de famílias DIFERENTES? Com o addon
        de vetores, o sentido decide: "indicar" e "índice" (cosseno 0,02) ou
        "numerar" e "número" (0,03) só se parecem na escrita, enquanto
        "índices"/"índice" (0,73) e "ordenar"/"ordenação" (0,45) são a mesma
        ideia. Sem vetor para alguma das duas, não dá para afirmar: False.
        """
        self._atualizar()
        if a == b or not self.tem_vetores:
            return False
        va, vb = self.vetor(a), self.vetor(b)
        return va is not None and vb is not None and cosseno(va, vb) < LIMIAR_MESMA_FAMILIA

    def frequente(self, palavra: str, limite: int) -> bool:
        """
        Está entre as `limite` palavras mais comuns? Os vetores vêm ordenados
        por frequência, então o número do vetor da palavra é a sua posição.
        """
        _, ref = self._consultar(palavra)
        if ref is None or ref[1] < 0:
            return False
        bloco = self._bloco(ref[0])
        # Num vocabulário pequeno, "as N mais comuns" não quer dizer nada.
        return bloco is not None and ref[1] < min(limite, bloco[2] // 10)

    def _bloco(self, addon_id: str) -> tuple[int, bytes, int] | None:
        if addon_id not in self._blocos:
            info = self.banco.recurso(addon_id, "vetores.info")
            dados = self.banco.recurso(addon_id, "vetores.dados")
            if not info or not dados:
                return None
            info = json.loads(info)
            self._blocos[addon_id] = (info["dimensoes"], bytes(dados), info["quantidade"])
        return self._blocos[addon_id]

    def vetor(self, palavra: str, apelidos: bool = True) -> list[float] | None:
        """
        O vetor da palavra já NORMALIZADO (comprimento 1), ou None. Se a
        palavra não tem vetor, tenta o do seu lema ("fizemos" → "fazer").
        apelidos=False ignora palavras que só emprestam o vetor de outra.
        """
        info = self.vetor_info(palavra)
        if info is None or (info[1] and not apelidos):
            return None
        return info[0]

    def vetor_info(self, palavra: str) -> tuple[list[float], bool] | None:
        """(vetor normalizado, é apelido?) — ver addon_lexico em memoria/banco.py."""
        lema, ref = self._consultar(palavra)
        if (ref is None or ref[1] < 0) and lema:
            _, ref_lema = self._consultar(lema)
            if ref_lema is not None and (ref is None or ref_lema[1] >= 0):
                ref = ref_lema
        if ref is None:
            return None
        apelido = ref[1] < 0
        numero = -ref[1] - 1 if apelido else ref[1]
        bloco = self._bloco(ref[0])
        if not bloco:
            return None
        d, dados, _ = bloco
        inicio = numero * d
        if inicio + d > len(dados):
            return None
        bruto = array("b", dados[inicio:inicio + d])
        norma = math.sqrt(sum(x * x for x in bruto)) or 1.0
        return [x / norma for x in bruto], apelido


# Abaixo disto, duas palavras de começo igual não são flexão uma da outra.
# Medido nos vetores do addon: as falsas ficam perto de 0 (indicar/índice
# 0,02; numerar/número 0,03) e as verdadeiras acima de 0,3 (salvar/salvo 0,35).
LIMIAR_MESMA_FAMILIA = 0.15


def cosseno(a: list[float], b: list[float]) -> float:
    """Para vetores normalizados, o cosseno é só o produto escalar."""
    return sum(x * y for x, y in zip(a, b))
