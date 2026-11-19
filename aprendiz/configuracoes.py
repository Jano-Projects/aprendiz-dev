"""
Configurações ajustáveis: parâmetros dos algoritmos e personalização da interface.

Por que uma LISTA FECHADA?
    Addons podem trazer parâmetros e personalizações. Como addons vêm da
    internet, só aceitamos chaves conhecidas e valores validados aqui: um
    addon nunca consegue alterar algo fora desta lista.

De onde vem o valor de cada chave (precedência, da maior para a menor):

    1. o DONO, pelo menu Configurações          → origem "dono"
    2. um ADDON ATIVO (o instalado mais recente) → origem "addon"
    3. o PADRÃO do app (definido abaixo)         → origem "padrao"

Assim, o que o dono escolhe sempre vence, como acontece com os conhecimentos.

Tipos de configuração (são também tipos de addon, na "classificacao"):
    parametros     → como o assistente busca e responde
    personalizacao → como a interface se apresenta
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

_COR = re.compile(r"^#[0-9a-fA-F]{6}$")
_CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


# ---------------------------------------------------------------- validadores
def _numero(minimo: float, maximo: float) -> Callable[[Any], float]:
    def validar(valor: Any) -> float:
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise ValueError("precisa ser um número")
        if not minimo <= valor <= maximo:
            raise ValueError(f"precisa estar entre {minimo} e {maximo}")
        return round(float(valor), 3)
    return validar


def _escolha(opcoes: Callable[[], list[str]]) -> Callable[[Any], str]:
    def validar(valor: Any) -> str:
        if valor not in opcoes():
            raise ValueError(f"opções válidas: {', '.join(opcoes())}")
        return valor
    return validar


def _texto(minimo: int, maximo: int) -> Callable[[Any], str]:
    def validar(valor: Any) -> str:
        if not isinstance(valor, str):
            raise ValueError("precisa ser texto")
        valor = _CONTROLE.sub("", valor).strip()
        if not minimo <= len(valor) <= maximo:
            raise ValueError(f"precisa ter de {minimo} a {maximo} caracteres")
        return valor
    return validar


_NORMA = re.compile(r"^(pt-[A-Z]{2})?$")


def _norma(valor: Any) -> str:
    if not isinstance(valor, str) or not _NORMA.match(valor):
        raise ValueError("use o id de uma norma (ex.: pt-BR, pt-PT) ou deixe vazio")
    return valor


def _cor(valor: Any) -> str:
    if not isinstance(valor, str) or not _COR.match(valor):
        raise ValueError("use uma cor no formato #RRGGBB")
    return valor.lower()


# Importações tardias: evitam importação circular com o pacote de algoritmos.
def _buscas() -> list[str]:
    from aprendiz.algoritmos import BUSCAS
    return list(BUSCAS)


def _respostas() -> list[str]:
    from aprendiz.algoritmos import RESPOSTAS
    return list(RESPOSTAS)


def _limiar_padrao(nome: str) -> Callable[[], float]:
    def padrao() -> float:
        from aprendiz.algoritmos import BUSCAS
        return BUSCAS[nome].limiar
    return padrao


# ---------------------------------------------------------------- definições
@dataclass(frozen=True)
class Definicao:
    chave: str
    tipo: str                      # "parametros" | "personalizacao"
    titulo: str
    descricao: str
    padrao: Any                    # valor fixo ou função sem argumentos
    validar: Callable[[Any], Any]
    extras: dict = field(default_factory=dict)  # dicas para a interface

    def valor_padrao(self) -> Any:
        return self.padrao() if callable(self.padrao) else self.padrao


DEFINICOES: dict[str, Definicao] = {d.chave: d for d in [
    # ---- parâmetros
    Definicao("busca.padrao", "parametros", "Algoritmo de busca",
              "Algoritmo usado para encontrar os conhecimentos.",
              "bm25", _escolha(_buscas), {"opcoes": "busca"}),
    Definicao("resposta.padrao", "parametros", "Algoritmo de resposta",
              "Como o texto final é montado.",
              "direta", _escolha(_respostas), {"opcoes": "resposta"}),
    *[Definicao(f"limiar.{nome}", "parametros", f"Limiar: {titulo}",
                "Confiança mínima para aceitar uma resposta. Mais alto = mais exigente "
                "(inventa menos, recusa mais).",
                _limiar_padrao(nome), _numero(0.05, 1.0),
                {"minimo": 0.05, "maximo": 1.0, "passo": 0.05})
      for nome, titulo in [("bm25", "BM25"), ("tfidf", "TF-IDF"),
                           ("fuzzy", "Fuzzy"), ("hibrido", "Híbrido"),
                           ("calibrado", "Calibrado")]],
    Definicao("revisao.norma", "parametros", "Norma da revisão de texto",
              "Norma usada para revisar textos quando a mensagem não diz qual "
              "(precisa de um addon de norma). Automática = a que mais combina com o texto.",
              "", _norma, {"opcoes": "normas"}),
    Definicao("prioridade_dono.margem", "parametros", "Prioridade do que você ensina",
              "O que você ensinou vence um addon se tiver pelo menos esta fração da "
              "confiança dele (0,9 = até 10% abaixo).",
              0.9, _numero(0.5, 1.0), {"minimo": 0.5, "maximo": 1.0, "passo": 0.05}),
    # ---- personalização
    Definicao("personalizacao.nome", "personalizacao", "Nome do assistente",
              "Como o assistente se apresenta na interface.",
              "Aprendiz", _texto(1, 30)),
    Definicao("personalizacao.cor", "personalizacao", "Cor de destaque",
              "Cor dos botões e destaques da interface.",
              "#4f46e5", _cor, {"cor": True}),
    Definicao("personalizacao.boas_vindas", "personalizacao", "Mensagem de boas-vindas",
              "Texto exibido abaixo do nome, na tela inicial.",
              "Eu só sei o que você me ensina, e tudo fica guardado neste computador.",
              _texto(1, 200)),
]}

TIPOS = ("parametros", "personalizacao")


def validar(chave: str, valor: Any) -> Any:
    """Valida um par chave/valor. Lança ValueError com mensagem legível."""
    definicao = DEFINICOES.get(chave)
    if not definicao:
        raise ValueError(f"configuração desconhecida: {chave}")
    try:
        return definicao.validar(valor)
    except ValueError as erro:
        raise ValueError(f"{definicao.titulo}: {erro}") from None


def validar_bloco(tipo: str, dados: Any) -> dict[str, Any]:
    """Valida um bloco inteiro (ex.: parametros.json de um addon)."""
    if not isinstance(dados, dict) or not dados:
        raise ValueError(f"{tipo}: precisa ser um objeto com pelo menos uma configuração")
    saida = {}
    for chave, valor in dados.items():
        definicao = DEFINICOES.get(chave)
        if not definicao or definicao.tipo != tipo:
            raise ValueError(f"{tipo}: '{chave}' não é uma configuração deste tipo")
        saida[chave] = validar(chave, valor)
    return saida


class Configuracoes:
    """Lê e grava configurações, resolvendo a precedência dono > addon > padrão."""

    def __init__(self, banco) -> None:
        self.banco = banco

    def efetivas(self) -> dict[str, dict[str, Any]]:
        """chave → {valor, origem, addon_id, addon_nome}, para todas as definições."""
        linhas = self.banco.linhas_configuracoes()  # já ordenadas: dono, depois addons recentes
        escolhidas: dict[str, dict] = {}
        for l in linhas:
            if l["chave"] in escolhidas or l["chave"] not in DEFINICOES:
                continue
            try:
                valor = validar(l["chave"], json.loads(l["valor"]))
            except ValueError:
                continue  # valor antigo que deixou de ser válido: ignora
            escolhidas[l["chave"]] = {
                "valor": valor,
                "origem": "dono" if not l["addon_id"] else "addon",
                "addon_id": l["addon_id"] or None,
                "addon_nome": l.get("addon_nome"),
            }
        return {
            chave: escolhidas.get(chave, {"valor": d.valor_padrao(), "origem": "padrao",
                                          "addon_id": None, "addon_nome": None})
            for chave, d in DEFINICOES.items()
        }

    def valor(self, chave: str) -> Any:
        return self.efetivas()[chave]["valor"]

    def definir(self, chave: str, valor: Any) -> Any:
        valor = validar(chave, valor)
        self.banco.definir_configuracao(chave, json.dumps(valor))
        return valor

    def remover(self, chave: str) -> None:
        if chave not in DEFINICOES:
            raise ValueError(f"configuração desconhecida: {chave}")
        self.banco.remover_configuracao(chave)

    def do_dono(self, tipo: str) -> dict[str, Any]:
        """O que o dono definiu de um tipo (usado na exportação)."""
        return {
            chave: info["valor"] for chave, info in self.efetivas().items()
            if info["origem"] == "dono" and DEFINICOES[chave].tipo == tipo
        }

    def descrever(self) -> list[dict[str, Any]]:
        """Tudo o que a interface precisa para montar a tela de configurações."""
        efetivas = self.efetivas()
        return [{
            "chave": d.chave, "tipo": d.tipo, "titulo": d.titulo, "descricao": d.descricao,
            "padrao": d.valor_padrao(), **efetivas[d.chave], **d.extras,
        } for d in DEFINICOES.values()]
