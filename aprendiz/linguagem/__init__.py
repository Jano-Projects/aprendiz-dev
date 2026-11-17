"""Processamento de linguagem natural (PLN) clássico, sem redes neurais."""

from aprendiz.linguagem.entidades import extrair_entidades
from aprendiz.linguagem.intencoes import ClassificadorIntencoes
from aprendiz.linguagem.normalizador import Linguagem, TextoProcessado, normalizar
from aprendiz.linguagem.stemmer import radical

__all__ = [
    "ClassificadorIntencoes",
    "Linguagem",
    "TextoProcessado",
    "extrair_entidades",
    "normalizar",
    "radical",
]
