"""
Seletor de algoritmos.

Importar os subpacotes `busca` e `resposta` executa os decoradores
@registrar, que preenchem os dicionários BUSCAS e RESPOSTAS.
"""

from aprendiz.algoritmos import busca, resposta  # noqa: F401  (registra os plugins)
from aprendiz.algoritmos.base import (
    BUSCAS, RESPOSTAS, AlgoritmoBusca, AlgoritmoResposta, Candidato, ContextoBusca,
    RespostaGerada, registrar,
)


def listar_algoritmos() -> dict:
    """Formato usado pela interface para montar os seletores."""
    def info(a):
        dados = {"nome": a.nome, "titulo": a.titulo, "descricao": a.descricao,
                 "explicacao": a.explicacao.strip()}
        if isinstance(a, AlgoritmoBusca):
            dados["limiar"] = a.limiar
        return dados

    return {
        "busca": [info(a) for a in BUSCAS.values()],
        "resposta": [info(a) for a in RESPOSTAS.values()],
    }


__all__ = [
    "BUSCAS", "RESPOSTAS", "AlgoritmoBusca", "AlgoritmoResposta", "Candidato",
    "ContextoBusca", "RespostaGerada", "listar_algoritmos", "registrar",
]
