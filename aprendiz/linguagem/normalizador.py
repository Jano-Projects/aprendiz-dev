"""
Normalizador: transforma a mensagem crua em algo que o computador compara bem.

Exemplo do caminho completo de "Vc sabe qual o HORÁRIO da farmásia?":

    1. minúsculas + sem acento  → "vc sabe qual o horario da farmasia?"
    2. pontuação vira espaço    → "vc sabe qual o horario da farmasia"
       (antes, "wi-fi" e "e-mail" viram "wifi" e "email", e
       "c++" e "c#" viram "cpp" e "csharp")
    3. tokens (palavras)        → [vc, sabe, qual, o, horario, da, farmasia]
    4. abreviações              → [voce, sabe, qual, o, horario, da, farmasia]
    5. correção de digitação    → farmasia → farmacia (se "farmacia" existir na base)
    6. sinônimos                → (nenhum neste exemplo)
    7. remove stopwords         → [horario, farmacia]
    8. radicais                 → [horari, farmac]

Com um addon de COMPREENSÃO ativo (0.7+), entram mais duas etapas:

    5b. expressões  → "dar um jeito" vira "resolver" (antes dos sinônimos)
    6b. lemas       → "fui" vira "ser", "fiz" vira "fazer" (depois dos
                      sinônimos, só nas palavras que não são stopwords)

e a correção de digitação deixa em paz as palavras que existem no
português, mesmo que não estejam na base ("carro" não vira "caro").

O resultado é um `TextoProcessado`, que guarda TODAS as etapas. Isso é
proposital: o Monitor mostra cada uma delas.

A classe `Linguagem` carrega as tabelas do banco (abreviações, sinônimos,
stopwords) e as mantém em memória, recarregando só quando algo muda.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from rapidfuzz import fuzz, process
from rapidfuzz.distance import OSA

from aprendiz.linguagem import numeros
from aprendiz.linguagem.lexico import Lexico
from aprendiz.linguagem.stemmer import radical

_NAO_ALFANUMERICO = re.compile(r"[^a-z0-9]+")

# Prefixo curto + hífen vira uma palavra só: "wi-fi" → "wifi", "e-mail" → "email".
# Só para 1 ou 2 letras, para não colar palavras compostas ("segunda-feira").
_PREFIXO_HIFEN = re.compile(r"\b([a-z]{1,2})-(?=[a-z])")

# Nomes de linguagens com símbolo, que a pontuação apagaria: sem isto,
# "c++", "c#" e "c" virariam a mesma palavra. "c++" → "cpp", "g++" → "gpp",
# "notepad++" → "notepadpp", "c#" → "csharp", "f#" → "fsharp".
_MAIS_MAIS = re.compile(r"\b([a-z]+)\+\+")
_SUSTENIDO = re.compile(r"\b([cf])#")
# O operador seta do C ("p->campo") também tem nome próprio, senão some com a pontuação.
_SETA = re.compile(r"->")

# Versão das regras de normalização. Se ela mudar, os textos de busca já
# gravados ficam desatualizados: o Assistente reindexa a base ao abrir.
VERSAO_NORMALIZACAO = 7


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
    """Minúsculas, sem acento, números em algarismos, só letras/números separados por um espaço."""
    texto = remover_acentos(texto.lower())
    texto = _PREFIXO_HIFEN.sub(r"\1", texto)
    texto = _MAIS_MAIS.sub(r"\1pp", texto)
    texto = _SUSTENIDO.sub(r"\1sharp", texto)
    texto = _SETA.sub(" seta ", texto)
    texto = numeros.simbolos(texto)                      # "2+2" → "2 mais 2"
    tokens = _NAO_ALFANUMERICO.sub(" ", texto).split()
    return " ".join(numeros.palavras(tokens))            # "dois mais 2" → "2 soma 2"


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
    expressoes: dict[str, str] = field(default_factory=dict)
    lemas: dict[str, str] = field(default_factory=dict)
    # 2.5.1: o normalizado com abreviações expandidas e erros corrigidos, mas
    # ANTES de sinônimos, expressões e lemas. É o que as etapas que leem a
    # frase por padrões (dicionário, padrões de frase) devem ver:
    # "o q siginfica trampo" → "o que significa trampo".
    reescrito: str = ""

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
            "expressoes": self.expressoes,
            "lemas": self.lemas,
        }


class Linguagem:
    """Banco de linguagem em memória + o processamento de textos."""

    # Correção de digitação: só tenta em palavras com pelo menos 4 letras e
    # aceita a sugestão se a similaridade for >= 80 (de 0 a 100).
    # A similaridade (2.5.1) vem da distância OSA (Damerau-Levenshtein
    # restrita): trocar duas letras vizinhas de lugar ("mlihas") custa UMA
    # edição, e não duas, como na Levenshtein comum. Assim "mlihas" vira
    # "milhas" (1 troca), e não "linhas" (2 substituições).
    TAMANHO_MINIMO_CORRECAO = 4
    SIMILARIDADE_MINIMA_CORRECAO = 80

    def __init__(self, banco) -> None:
        self.banco = banco
        self._versao_ling = -1
        self._versao_vocab = -1
        self._frequencia: dict[str, int] = {}
        self._pares: set[tuple[str, str]] = set()
        self.abreviacoes: dict[str, str] = {}
        self.sinonimos: dict[str, str] = {}
        self.stopwords: set[str] = set()
        self.vocabulario: set[str] = set()
        self.lexico = Lexico(banco)
        self.expressoes: dict[tuple[str, ...], list[str]] = {}
        self._maior_expressao = 0

    # ------------------------------------------------------------------ cache
    def _atualizar_tabelas(self) -> None:
        if self._versao_ling != self.banco.versao_linguagem:
            self.abreviacoes = self.banco.mapa_abreviacoes()
            self.sinonimos = self.banco.mapa_sinonimos()
            self.stopwords = self.banco.lista_stopwords()
            self._carregar_expressoes()
            self._versao_ling = self.banco.versao_linguagem

    def _carregar_expressoes(self) -> None:
        """Expressões dos addons de compreensão ativos (o mais novo vence)."""
        import json
        self.expressoes = {}
        for _, dados in self.banco.recursos_ativos("compreensao.json"):
            for de, para in json.loads(dados).get("expressoes", {}).items():
                self.expressoes[tuple(de.split())] = para.split()
        self._maior_expressao = max((len(k) for k in self.expressoes), default=0)

    def _atualizar_vocabulario(self) -> None:
        """
        Vocabulário = todas as palavras que aparecem na base de conhecimento.
        Ele é a referência para corrigir erros de digitação: só "corrigimos"
        para palavras que o assistente realmente conhece.
        """
        if self._versao_vocab != self.banco.versao_conhecimento:
            frequencia: dict[str, int] = {}
            pares: set[tuple[str, str]] = set()
            for c in self.banco.conhecimentos_ativos():
                texto = f"{c.get('pergunta') or ''} {c['conteudo']}"
                palavras = tokenizar(normalizar(texto))
                for p in palavras:
                    frequencia[p] = frequencia.get(p, 0) + 1
                pares.update(zip(palavras, palavras[1:]))
            # Lista ORDENADA (não um conjunto): o resultado da correção não pode
            # depender da ordem em que o Python guarda um conjunto na memória.
            self.vocabulario = sorted(p for p in frequencia if not p.isdigit())
            self._frequencia, self._pares = frequencia, pares
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
        for i, t in enumerate(tokens):
            if (
                len(t) >= self.TAMANHO_MINIMO_CORRECAO
                and not t.isdigit()
                and t not in self.vocabulario
                and t not in self.stopwords
                and t not in self.sinonimos  # sinônimo conhecido não é erro
                and not self.lexico.conhece(t)  # palavra que existe não é erro
            ):
                # rapidfuzz compara a palavra com todo o vocabulário de forma
                # muito rápida (o núcleo é escrito em C++).
                achados = self._candidatos_correcao(t)
                if achados:
                    melhor = self._desempatar(achados, saida[-1] if saida else None,
                                              tokens[i + 1] if i + 1 < len(tokens) else None)
                    registro[t] = melhor
                    t = melhor
            saida.append(t)
        return saida

    def _candidatos_correcao(self, palavra: str) -> list[tuple[str, float, float]]:
        """
        Palavras do vocabulário parecidas com `palavra`: (candidata, OSA, ratio),
        as duas notas de 0 a 100 e calculadas em C++ pela rapidfuzz.

        A nota que decide (2.5.1) é a OSA (Damerau-Levenshtein restrita): ela
        conta a troca de duas letras vizinhas como UM erro, o que é o erro de
        digitação mais comum ("mlihas" ~ "milhas", e não "linhas"). A ratio
        (Indel) também traz candidatas, porque é mais tolerante a letra a mais
        ou a menos, e desempata no fim.
        """
        minimo = self.SIMILARIDADE_MINIMA_CORRECAO - 1e-6
        vistas: set[str] = set()
        for escala, scorer in ((1, fuzz.ratio), (100, OSA.normalized_similarity)):
            for candidata, _, _ in process.extract(palavra, self.vocabulario, scorer=scorer,
                                                   limit=8, score_cutoff=minimo / escala):
                vistas.add(candidata)
        achados = [(c, round(OSA.normalized_similarity(palavra, c) * 100, 4),
                    round(fuzz.ratio(palavra, c), 4)) for c in vistas]
        return sorted(achados, key=lambda a: (-a[1], -a[2], a[0]))

    def _desempatar(self, achados, anterior: str | None, proxima: str | None) -> str:
        """
        Entre as correções igualmente parecidas pela OSA ("grup" → "grupo" ou
        "group"; "torcar" → "trocar" ou "tocar"), vale a que forma com a palavra
        vizinha um PAR que existe na base ("group by"); depois, a mais frequente
        na base; depois, a de maior ratio; por fim, a ordem alfabética. Assim a
        mesma pergunta é sempre corrigida do mesmo jeito.
        """
        nota = achados[0][1]
        empatados = [a for a in achados if a[1] >= nota - 0.01]

        def chave(achado):
            palavra = achado[0]
            par = (anterior, palavra) in self._pares or (palavra, proxima) in self._pares
            return (not par, -self._frequencia.get(palavra, 0), -achado[2], palavra)

        return min(empatados, key=chave)[0]

    def _aplicar_expressoes(self, tokens: list[str], registro: dict[str, str]) -> list[str]:
        """
        Troca expressões de várias palavras, da MAIS LONGA para a mais curta:
        em "nao dar a minima", "dar a minima" é tentada antes de "dar a".
        Compara sequências de palavras (nada de regex vinda de addon).
        """
        if not self.expressoes:
            return tokens
        saida: list[str] = []
        i = 0
        while i < len(tokens):
            for tamanho in range(min(self._maior_expressao, len(tokens) - i), 1, -1):
                trecho = tuple(tokens[i:i + tamanho])
                if trecho in self.expressoes:
                    troca = self.expressoes[trecho]
                    registro[" ".join(trecho)] = " ".join(troca)
                    saida.extend(troca)
                    i += tamanho
                    break
            else:
                saida.append(tokens[i])
                i += 1
        return saida

    def _lematizar(self, tokens: list[str], registro: dict[str, str]) -> list[str]:
        """Troca cada palavra (que não seja stopword) pelo seu lema, se houver."""
        if not self.lexico.tem_lemas:
            return tokens
        saida = []
        for t in tokens:
            if t not in self.stopwords and not t.isdigit():
                lema = self.lexico.lema(t)
                if lema:
                    registro[t] = lema
                    t = lema
            saida.append(t)
        return saida

    def _aplicar_sinonimos(self, tokens: list[str], registro: dict[str, str]) -> list[str]:
        """
        Troca cada palavra pela forma principal do seu sinônimo. Tenta a palavra
        como foi escrita e, se não achar, o LEMA dela: com "automovel → carro"
        cadastrado, "automoveis" também vira "carro" (antes da 1.0, não virava).
        Os sinônimos já chegam resolvidos (sem conflitos, cadeias seguidas):
        ver linguagem/resolucao.py.
        """
        saida = []
        for t in tokens:
            alvo = self.sinonimos.get(t)
            if alvo is None and self.lexico.tem_lemas and t not in self.stopwords:
                lema = self.lexico.lema(t)
                if lema and lema in self.sinonimos:
                    alvo = self.sinonimos[lema]
            if alvo is not None:
                registro[t] = alvo
                t = alvo
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
        expressoes: dict[str, str] = {}
        lemas: dict[str, str] = {}

        self.lexico._atualizar()
        tokens = self._expandir(tokenizar(normalizado), expansoes)
        if corrigir:
            tokens = self._corrigir(tokens, correcoes)
        reescrito = " ".join(tokens)
        tokens = self._aplicar_expressoes(tokens, expressoes)
        tokens = self._aplicar_sinonimos(tokens, sinonimos)
        tokens = self._lematizar(tokens, lemas)

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
            expressoes=expressoes,
            lemas=lemas,
            reescrito=reescrito,
        )
