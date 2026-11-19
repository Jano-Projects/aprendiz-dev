"""
Contratos (interfaces) dos algoritmos e o registro do "seletor".

O seletor de algoritmos usa o padrão de projeto STRATEGY: várias classes
com a mesma interface, intercambiáveis em tempo de execução. A interface
escolhe pelo NOME e o pipeline não precisa saber qual está usando.

Para criar um algoritmo novo (veja docs/criar-algoritmo.md):

    1. Crie um arquivo em algoritmos/busca/ (ou resposta/).
    2. Escreva uma classe que herde de AlgoritmoBusca (ou AlgoritmoResposta).
    3. Decore com @registrar.
    4. Importe o módulo em algoritmos/__init__.py.

Pronto: ele aparece sozinho no seletor da interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from aprendiz.linguagem import Linguagem, TextoProcessado


@dataclass
class ContextoBusca:
    """O que os algoritmos podem consultar: o banco e a linguagem."""

    banco: Any
    linguagem: Linguagem
    # Espaço para cada algoritmo guardar seus índices em memória entre buscas.
    cache: dict[str, Any] = field(default_factory=dict)
    # Limiares em vigor (nome do algoritmo → valor). O Assistente preenche a
    # cada pergunta a partir das Configurações; o que faltar usa o padrão
    # declarado na classe do algoritmo.
    limiares: dict[str, float] = field(default_factory=dict)
    # Caminho de porquês do melhor candidato (core/teia.py), quando ele tem
    # teia. O Assistente preenche a cada pergunta; None = sem teia.
    caminho: Any = None
    # Frases dos addons de linguagem para vestir a resposta (core/expressao.py).
    expressao: Any = None
    # Sinais do assunto declarado (2.4): função (consulta, conhecimento) → dict,
    # preenchida pelo Assistente e usada pela busca Calibrada.
    sinais_assunto: Any = None

    def limiar(self, nome: str) -> float:
        """Confiança mínima em vigor para o algoritmo de busca `nome`."""
        return self.limiares.get(nome, BUSCAS[nome].limiar)


@dataclass
class Candidato:
    """Um conhecimento encontrado pela busca."""

    conhecimento: dict[str, Any]
    pontuacao: float     # valor "bruto" do algoritmo (usado para ordenar)
    confianca: float     # 0 a 1, comparável com o limiar do algoritmo
    detalhes: dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.conhecimento["id"]


@dataclass
class RespostaGerada:
    texto: str
    fontes: list[str]                         # ids dos conhecimentos usados
    detalhes: dict[str, Any] = field(default_factory=dict)


class AlgoritmoBusca(ABC):
    nome: str = ""        # identificador usado pela API (ex.: "bm25")
    titulo: str = ""      # nome exibido na interface
    descricao: str = ""   # texto curto para o usuário entender a escolha
    explicacao: str = ""  # como funciona, em Markdown (aparece em "Como funciona?")
    limiar: float = 0.5   # confiança mínima PADRÃO (o dono ou um addon podem ajustar)
    # 1.0: como o modelo aparece para quem não é da área.
    apelido: str = ""     # nome curto e humano (ex.: "Equilibrado")
    quando_usar: str = "" # uma frase: em que situação escolher este
    custo: str = "leve"   # "leve", "médio" ou "pesado" (processamento por pergunta)

    @abstractmethod
    def buscar(self, consulta: TextoProcessado, ctx: ContextoBusca,
               limite: int = 5) -> list[Candidato]:
        """Devolve os candidatos mais relevantes, do melhor para o pior."""


class AlgoritmoResposta(ABC):
    nome: str = ""
    titulo: str = ""
    descricao: str = ""
    explicacao: str = ""
    apelido: str = ""
    quando_usar: str = ""
    custo: str = "leve"

    @abstractmethod
    def responder(self, consulta: TextoProcessado, candidatos: list[Candidato],
                  ctx: ContextoBusca) -> RespostaGerada:
        """Monta o texto final a partir dos candidatos ACEITOS (acima do limiar)."""


# ---------------------------------------------------------------------------
# Registro: nome → instância. Preenchido pelo decorador @registrar.
# ---------------------------------------------------------------------------
BUSCAS: dict[str, AlgoritmoBusca] = {}
RESPOSTAS: dict[str, AlgoritmoResposta] = {}


def registrar(cls):
    """Decorador que coloca o algoritmo no seletor."""
    instancia = cls()
    if isinstance(instancia, AlgoritmoBusca):
        BUSCAS[instancia.nome] = instancia
    elif isinstance(instancia, AlgoritmoResposta):
        RESPOSTAS[instancia.nome] = instancia
    else:  # pragma: no cover
        raise TypeError(f"{cls.__name__} não é um algoritmo de busca nem de resposta")
    return cls


def cobertura(termos_consulta: list[str], termos_documento: set[str]) -> float:
    """
    Fração dos termos da pergunta que aparecem no documento (0 a 1).

    Medida simples e intuitiva de "quanto da pergunta este conhecimento
    responde". Usada como confiança pelo BM25, cuja pontuação bruta não tem
    escala fixa.
    """
    unicos = set(termos_consulta)
    if not unicos:
        return 0.0
    return len(unicos & termos_documento) / len(unicos)
