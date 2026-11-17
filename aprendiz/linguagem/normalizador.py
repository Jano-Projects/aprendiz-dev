"""
Normalizador: transforma a mensagem crua em algo que o computador compara bem.

Exemplo do caminho completo de "Vc sabe qual o HORÁRIO da farmásia?":

    1. minúsculas + sem acento  → "vc sabe qual o horario da farmasia?"
    2. pontuação vira espaço    → "vc sabe qual o horario da farmasia"
       (antes, "wi-fi" e "e-mail" viram "wifi" e "email")
    3. tokens (palavras)        → [vc, sabe, qual, o, horario, da, farmasia]
    4. abreviações              → [voce, sabe, qual, o, horario, da, farmasia]
    5. correção de digitação    → farmasia → farmacia (se "farmacia" existir na base)
    6. sinônimos                → (nenhum neste exemplo)
    7. remove stopwords         → [horario, farmacia]
    8. radicais                 → [horari, farmac]

O resultado é um `TextoProcessado`, que guarda TODAS as etapas. Isso é
proposital: o painel "Por que respondi isso?" mostra cada uma delas.

A classe `Linguagem` carrega as tabelas do banco (abreviações, sinônimos,
stopwords) e as mantém em memória, recarregando só quando algo muda.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from rapidfuzz import fuzz, process

from aprendiz.linguagem.stemmer import radical

_NAO_ALFANUMERICO = re.compile(r"[^a-z0-9]+")

# Prefixo curto + hífen vira uma palavra só: "wi-fi" → "wifi", "e-mail" → "email".
# Só para 1 ou 2 letras, para não colar palavras compostas ("segunda-feira").
_PREFIXO_HIFEN = re.compile(r"\b([a-z]{1,2})-(?=[a-z])")

# Versão das regras de normalização. Se ela mudar, os textos de busca já
# gravados ficam desatualizados: o Assistente reindexa a base ao abrir.
VERSAO_NORMALIZACAO = 2


def remover_acentos(texto: str) -> str:
    """
    "ação" → "acao".

    A normalização NFKD separa cada letra acentuada em duas partes: a letra
    base e o acento (um caractere "combinante"). Depois é só descartar os
    caracteres combinantes.
    """
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento, só letras/números separados por um espaço."""
    texto = remover_acentos(texto.lower())
    texto = _PREFIXO_HIFEN.sub(r"\1", texto)
    return _NAO_ALFANUMERICO.sub(" ", texto).strip()


def tokenizar(texto: str) -> list[str]:
    """Divide o texto normalizado em palavras (tokens)."""
    return texto.split()


@dataclass
class TextoProcessado:
    """Resultado de cada etapa do processamento de um texto."""

    original: str
    normalizado: str
    tokens: list[str]                 # após abreviações, correções e sinônimos
    conteudo: list[str]               # tokens sem stopwords
    radicais: list[str]               # radicais do conteúdo → usados na BUSCA
    radicais_todos: list[str]         # radicais de todos os tokens → usados na INTENÇÃO
    expansoes: dict[str, str] = field(default_factory=dict)
    correcoes: dict[str, str] = field(default_factory=dict)
    sinonimos: dict[str, str] = field(default_factory=dict)

    @property
    def texto_busca(self) -> str:
        """Texto que vai para o índice de busca (radicais separados por espaço)."""
        return " ".join(self.radicais)

    def como_dict(self) -> dict:
        return {
            "normalizado": self.normalizado,
            "tokens": self.tokens,
            "conteudo": self.conteudo,
            "radicais": self.radicais,
            "expansoes": self.expansoes,
            "correcoes": self.correcoes,
            "sinonimos": self.sinonimos,
        }


class Linguagem:
    """Banco de linguagem em memória + o processamento de textos."""

    # Correção de digitação: só tenta em palavras com pelo menos 4 letras e
    # aceita a sugestão se a similaridade for >= 80 (de 0 a 100).
    TAMANHO_MINIMO_CORRECAO = 4
    SIMILARIDADE_MINIMA_CORRECAO = 80

    def __init__(self, banco) -> None:
        self.banco = banco
        self._versao_ling = -1
        self._versao_vocab = -1
        self.abreviacoes: dict[str, str] = {}
        self.sinonimos: dict[str, str] = {}
        self.stopwords: set[str] = set()
        self.vocabulario: set[str] = set()

    # ------------------------------------------------------------------ cache
    def _atualizar_tabelas(self) -> None:
        if self._versao_ling != self.banco.versao_linguagem:
            self.abreviacoes = self.banco.mapa_abreviacoes()
            self.sinonimos = self.banco.mapa_sinonimos()
            self.stopwords = self.banco.lista_stopwords()
            self._versao_ling = self.banco.versao_linguagem

    def _atualizar_vocabulario(self) -> None:
        """
        Vocabulário = todas as palavras que aparecem na base de conhecimento.
        Ele é a referência para corrigir erros de digitação: só "corrigimos"
        para palavras que o assistente realmente conhece.
        """
        if self._versao_vocab != self.banco.versao_conhecimento:
            vocab: set[str] = set()
            for c in self.banco.conhecimentos_ativos():
                texto = f"{c.get('pergunta') or ''} {c['conteudo']}"
                vocab.update(tokenizar(normalizar(texto)))
            self.vocabulario = {p for p in vocab if not p.isdigit()}
            self._versao_vocab = self.banco.versao_conhecimento

    # ------------------------------------------------------------------ etapas
    def _expandir(self, tokens: list[str], registro: dict[str, str]) -> list[str]:
        saida: list[str] = []
        for t in tokens:
            if t in self.abreviacoes:
                registro[t] = self.abreviacoes[t]
                saida.extend(self.abreviacoes[t].split())  # "oq" → "o que"
            else:
                saida.append(t)
        return saida

    def _corrigir(self, tokens: list[str], registro: dict[str, str]) -> list[str]:
        if not self.vocabulario:
            return tokens
        saida: list[str] = []
        for t in tokens:
            if (
                len(t) >= self.TAMANHO_MINIMO_CORRECAO
                and not t.isdigit()
                and t not in self.vocabulario
                and t not in self.stopwords
                and t not in self.sinonimos  # sinônimo conhecido não é erro
            ):
                # rapidfuzz compara a palavra com todo o vocabulário de forma
                # muito rápida (o núcleo é escrito em C++).
                achado = process.extractOne(
                    t, self.vocabulario, scorer=fuzz.ratio,
                    score_cutoff=self.SIMILARIDADE_MINIMA_CORRECAO,
                )
                if achado:
                    registro[t] = achado[0]
                    t = achado[0]
            saida.append(t)
        return saida

    def _aplicar_sinonimos(self, tokens: list[str], registro: dict[str, str]) -> list[str]:
        saida = []
        for t in tokens:
            if t in self.sinonimos:
                registro[t] = self.sinonimos[t]
                t = self.sinonimos[t]
            saida.append(t)
        return saida

    # ------------------------------------------------------------------ público
    def processar(self, texto: str, corrigir: bool = True) -> TextoProcessado:
        """
        Executa todas as etapas. Use corrigir=False ao INDEXAR conhecimento:
        o que o dono ensina é a referência, não deve ser "corrigido".
        """
        self._atualizar_tabelas()
        if corrigir:
            self._atualizar_vocabulario()

        normalizado = normalizar(texto)
        expansoes: dict[str, str] = {}
        correcoes: dict[str, str] = {}
        sinonimos: dict[str, str] = {}

        tokens = self._expandir(tokenizar(normalizado), expansoes)
        if corrigir:
            tokens = self._corrigir(tokens, correcoes)
        tokens = self._aplicar_sinonimos(tokens, sinonimos)

        conteudo = [t for t in tokens if t not in self.stopwords]
        return TextoProcessado(
            original=texto,
            normalizado=normalizado,
            tokens=tokens,
            conteudo=conteudo,
            radicais=[radical(t) for t in conteudo],
            radicais_todos=[radical(t) for t in tokens],
            expansoes=expansoes,
            correcoes=correcoes,
            sinonimos=sinonimos,
        )
