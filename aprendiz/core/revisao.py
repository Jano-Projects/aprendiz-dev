"""
Revisão de texto pela NORMA de um país (Aprendiz 0.8+).

Com um addon de norma ativo ("Português do Brasil", "Português de
Portugal", "Português de Angola"…), o Aprendiz revisa textos:

    revise: Fazem dois anos que não vejo o autocarro.
    revise em português de Portugal: Estou fazendo o facto.
    o certo é exceção ou excessão?
    como se escreve económico no Brasil?

O que é apontado, do mais grave ao mais leve:

    1. ERROS COMUNS ......... "excessão" → exceção (lista do addon)
    2. GRAFIA DE OUTRA NORMA  "facto" numa norma que escreve "fato", "acção"
                              onde vale o Acordo de 1990 (mapa "grafias")
    3. ORTOGRAFIA ........... palavra que não está no vocabulário da norma,
                              com sugestões (acentos e um erro de digitação)
    4. REGRAS DE GRAMÁTICA .. padrões de palavras do addon ("fazem dois anos"
                              → "faz dois anos"; veja aprendiz/normas.py)
    5. EQUIVALÊNCIAS ........ palavra de outra variante ("autocarro" numa
                              norma que diz "ônibus") e falsos amigos

O motor é este módulo; o addon só traz DADOS (listas, mapas e padrões de
tipos fixos). Nada de expressão regular vinda de fora.

Como é feita a busca no vocabulário
-----------------------------------
O vocabulário de uma norma pode ter milhões de formas. Ele fica no banco
como um bloco de bytes ordenado, e a pergunta "esta palavra existe?" é uma
busca binária nesse bloco (normas.Vocabulario). O bloco é lido do banco na
primeira revisão e fica em memória enquanto o addon estiver ativo.

Para sugerir a grafia certa de uma palavra desconhecida, geramos
CANDIDATAS (a mesma palavra com outros acentos, com uma letra trocada,
apagada, inserida ou duas letras invertidas) e ficamos com as que existem
no vocabulário: é a ideia do corretor de Peter Norvig, sem estatística.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from aprendiz import normas
from aprendiz.linguagem import normalizar
from aprendiz.normas import Vocabulario, forma, sem_acentos

# ---------------------------------------------------------------- constantes
MAX_TEXTO = 20_000                # caracteres revisados de uma vez
MAX_DESCONHECIDAS = 40            # palavras desconhecidas apontadas por revisão
MAX_SUGESTOES = 3

# Ordem de gravidade (a resposta e a interface usam esta ordem).
NIVEIS: dict[str, str] = {
    "erro": "Erro",
    "ortografia": "Ortografia",
    "grafia": "Grafia de outra norma",
    "norma": "Fora da norma-padrão",
    "variante": "Uso de outra variante",
    "estilo": "Estilo",
    "dica": "Atenção",
}
# Níveis cuja sugestão entra no "texto revisado". Estilo e dica são só avisos.
NIVEIS_APLICADOS = {"erro", "ortografia", "grafia", "norma", "variante"}

_PALAVRA = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*|\d+(?:[.,]\d+)*")
_FIM_FRASE = re.compile(r"[.!?…]\s*[\"'”»)\]]*\s*$|\n\s*$")
_PAUSA = re.compile(r"[,;:()\[\]—–\"“”«»]")

PRONOMES_OBLIQUOS = {"me", "te", "se", "lhe", "lhes", "nos", "vos"}
CLITICOS = PRONOMES_OBLIQUOS | {"o", "a", "os", "as", "lo", "la", "los", "las", "no", "na",
                                "nas", "mo", "ma", "mos", "mas", "to", "ta", "tos", "tas",
                                "lho", "lha", "lhos", "lhas", "no-lo", "vo-lo"}
# Terminações do futuro e do condicional na mesóclise (dir-te-ei, dar-lhe-ia).
MESOCLISE = {"ei", "ás", "á", "emos", "eis", "ão", "ia", "ias", "íamos", "íeis", "iam"}
PRONOMES_RETOS = {"eu", "tu", "ele", "ela", "nós", "vós", "eles", "elas", "você", "vocês"}
NUMEROS = {
    "um", "uma", "dois", "duas", "três", "quatro", "cinco", "seis", "sete", "oito", "nove",
    "dez", "onze", "doze", "treze", "catorze", "quatorze", "quinze", "dezesseis", "dezasseis",
    "dezessete", "dezassete", "dezoito", "dezenove", "dezanove", "vinte", "trinta",
    "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa", "cem", "cento",
    "duzentos", "duzentas", "trezentos", "quatrocentos", "quinhentos", "seiscentos",
    "setecentos", "oitocentos", "novecentos", "mil", "meia", "meio",
}
PARTICIPIOS_IRREGULARES = {
    "feito", "feita", "feitos", "feitas", "dito", "dita", "ditos", "ditas", "escrito",
    "escrita", "escritos", "escritas", "visto", "vista", "vistos", "vistas", "posto", "posta",
    "postos", "postas", "aberto", "aberta", "abertos", "abertas", "coberto", "coberta",
    "cobertos", "cobertas", "ganho", "gasto", "pago", "aceito", "aceite", "entregue",
    "morto", "morta", "mortos", "mortas", "preso", "presa", "presos", "presas", "vindo",
    "eleito", "salvo", "solto", "suspenso", "impresso", "expresso", "extinto", "limpo",
}
_SUFIXOS_PARTICIPIO = ("ado", "ada", "ados", "adas", "ido", "ida", "idos", "idas")

# Letras usadas para gerar candidatas na sugestão de grafia.
_LETRAS = "abcdefghijklmnopqrstuvwxyzáàâãéêíóôõúüç"
_VARIANTES_ACENTO = {
    "a": "aáàâã", "á": "aáàâã", "à": "aáàâã", "â": "aáàâã", "ã": "aáàâã",
    "e": "eéê", "é": "eéê", "ê": "eéê",
    "i": "ií", "í": "ií",
    "o": "oóôõ", "ó": "oóôõ", "ô": "oóôõ", "õ": "oóôõ",
    "u": "uúü", "ú": "uúü", "ü": "uúü",
    "c": "cç", "ç": "cç",
}


# ---------------------------------------------------------------- dados
@dataclass
class Token:
    texto: str                 # como está no texto
    forma: str                 # minúsculas (com acentos)
    inicio: int
    fim: int
    inicio_frase: bool         # primeira palavra de uma frase
    pausa_antes: bool          # há vírgula, dois-pontos… entre ela e a anterior
    na_pergunta: bool = False  # a frase termina com "?"

    @property
    def numero(self) -> bool:
        return self.texto[:1].isdigit()


@dataclass
class Apontamento:
    inicio: int
    fim: int
    trecho: str
    nivel: str
    tipo: str                  # erro_comum | grafia | ortografia | regra | equivalencia
    mensagem: str
    sugestoes: list[str] = field(default_factory=list)
    regra: str | None = None
    titulo: str | None = None
    exemplo: dict[str, str] | None = None
    destaque: list[int] | None = None   # [início, fim] a sublinhar, se menor que o trecho

    def como_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["nivel_titulo"] = NIVEIS[self.nivel]
        return d


@dataclass
class Norma:
    """Uma norma de um addon ativo, pronta para revisar."""

    id: str
    nome: str
    pais: str
    ortografia: str
    addon_id: str
    addon_nome: str
    dados: dict[str, Any]
    termos: set[str]                               # como a pessoa se refere a ela
    artigo: str = ""                               # "o" Brasil, "a" Guiné-Bissau, "" Angola
    vocabulario: Vocabulario | None = None
    verbos: set[str] = field(default_factory=set)
    equivalencias: dict[str, list[tuple[tuple[str, ...], dict]]] = field(default_factory=dict)
    erros_multi: dict[str, list[tuple[tuple[str, ...], str]]] = field(default_factory=dict)

    def resumo(self) -> dict[str, Any]:
        return {"id": self.id, "nome": self.nome, "pais": self.pais,
                "ortografia": self.ortografia,
                "ortografia_titulo": normas.ORTOGRAFIAS[self.ortografia],
                "addon_id": self.addon_id, "addon_nome": self.addon_nome,
                "vocabulario": len(self.vocabulario) if self.vocabulario else 0,
                "regras": len(self.dados.get("regras") or [])}


@dataclass
class Pedido:
    """O que a pessoa pediu: revisar um texto, comparar formas ou grafar uma palavra."""

    acao: str                          # "revisar" | "comparar" | "grafar"
    texto: str = ""
    opcoes: list[str] = field(default_factory=list)
    norma_texto: str | None = None     # "português de Portugal", como foi escrito
    explicito: bool = True             # pedido claro (com "revise:") ou só uma pergunta

    def como_dict(self) -> dict[str, Any]:
        return {"acao": self.acao, "norma pedida": self.norma_texto or "—",
                "tamanho": len(self.texto) if self.texto else len(self.opcoes)}


# ---------------------------------------------------------------- interpretação
_VERBO_REVISAR = (r"(?:revis[ae]r?|revisão|revisao|corrij[ae]|corrig[ei]r?|corrige|"
                  r"verifi(?:que|car|ca)|confir(?:a|ir|me)|confere|cheque|checar|checa)")
_OBJETO = (r"(?:\s+(?:o|este|esse|meu|a|esta|essa|minha|os|estes|meus)?\s*"
           r"(?:texto|frase|frases|par[áa]grafo|ortografia|gram[áa]tica|isto|isso|aqui)(?:\s+abaixo)?)?")
_NORMA_EM = (r"(?:\s+(?:em|no|na|pelo|pela|segundo\s+o|segundo\s+a|de\s+acordo\s+com\s+o|"
             r"de\s+acordo\s+com\s+a|para\s+o|para\s+a|pro|pra)\s+(?P<norma>[^:\n]{2,60}?))?")
PADRAO_REVISAR = re.compile(
    rf"^\s*(?:por\s+favor,?\s+)?{_VERBO_REVISAR}{_OBJETO}{_NORMA_EM}\s*:\s*(?P<texto>.+)$",
    re.I | re.S)
_PALAVRAS = r"[^\W\d_]+(?:['’-][^\W\d_]+)*(?:\s+[^\W\d_]+(?:['’-][^\W\d_]+)*){0,3}"
PADROES_COMPARAR = [
    re.compile(rf"^\s*(?:qual\s+(?:é|e)\s+)?(?:o\s+)?(?:certo|correto)(?:\s+(?:é|e))?\s*[:,]?\s*"
               rf"[\"“«']?(?P<a>{_PALAVRAS})[\"”»']?\s+ou\s+[\"“«']?(?P<b>{_PALAVRAS})[\"”»']?"
               rf"(?:\s*[,?]?\s*(?:em|no|na)\s+(?P<norma>[^?]{{2,40}}?))?\s*\??\s*$", re.I),
    re.compile(rf"^\s*(?:(?:se\s+)?escreve(?:-se)?\s+)?[\"“«']?(?P<a>{_PALAVRAS})[\"”»']?\s+ou\s+"
               rf"[\"“«']?(?P<b>{_PALAVRAS})[\"”»']?\s*[,?]?\s*(?:qual\s+(?:é|e)\s+)?(?:o\s+)?"
               rf"(?:certo|correto|que\s+(?:é|e)\s+certo)"
               rf"(?:\s+(?:em|no|na)\s+(?P<norma>[^?]{{2,40}}?))?\s*\??\s*$", re.I),
]
PADRAO_GRAFAR = re.compile(
    r"^\s*como\s+(?:é\s+que\s+|e\s+que\s+)?(?:se\s+)?escreve(?:r|-se)?\s+(?:a\s+palavra\s+)?"
    r"[\"“«']?(?P<x>[^\W\d_]+(?:['’-][^\W\d_]+)*)[\"”»']?"
    r"(?:\s+(?:em|no|na)\s+(?P<norma>[^?]{2,40}?))?\s*\??\s*$", re.I)
PADRAO_ESTA_CERTO = re.compile(
    r"^\s*(?:(?:é|e|está|esta|tá|ta)\s+(?:certo|correto|errado)|pode-se|posso)\s+"
    r"(?:escrever|dizer|falar|usar)\s+[\"“«']?(?P<texto>.+?)[\"”»']?"
    r"(?:\s+(?:em|no|na)\s+(?P<norma>(?:portugal|brasil|angola|moçambique|mocambique|"
    r"cabo verde|guiné|guine|timor|são tomé|sao tome)[^?]{0,30}))?\s*\??\s*$", re.I)


def interpretar(mensagem: str) -> Pedido | None:
    """Reconhece um pedido de revisão. None = a mensagem não é um."""
    m = PADRAO_REVISAR.match(mensagem)
    if m and m["texto"].strip():
        return Pedido("revisar", m["texto"].strip(), norma_texto=(m["norma"] or "").strip() or None)
    for padrao in PADROES_COMPARAR:
        m = padrao.match(mensagem.strip())
        if m:
            return Pedido("comparar", opcoes=[m["a"].strip(), m["b"].strip()],
                          norma_texto=(m["norma"] or "").strip() or None, explicito=False)
    m = PADRAO_GRAFAR.match(mensagem)
    if m:
        return Pedido("grafar", m["x"], norma_texto=(m["norma"] or "").strip() or None,
                      explicito=False)
    m = PADRAO_ESTA_CERTO.match(mensagem)
    if m:
        return Pedido("revisar", m["texto"].strip(), norma_texto=(m["norma"] or "").strip() or None,
                      explicito=False)
    return None


# ---------------------------------------------------------------- tokenização
def tokenizar(texto: str) -> list[Token]:
    tokens: list[Token] = []
    ultimo_fim = 0
    frase: list[Token] = []

    def fechar_frase(pontuacao: str) -> None:
        if "?" in pontuacao:
            for t in frase:
                t.na_pergunta = True
        frase.clear()

    for m in _PALAVRA.finditer(texto):
        entre = texto[ultimo_fim:m.start()]
        inicio_frase = not tokens or bool(_FIM_FRASE.search(entre))
        if inicio_frase:
            fechar_frase(entre)
        pausa = bool(_PAUSA.search(entre))
        bruto = m.group().replace("’", "'")
        tokens.append(Token(bruto, forma(bruto), m.start(), m.end(), inicio_frase, pausa))
        frase.append(tokens[-1])
        ultimo_fim = m.end()
    fechar_frase(texto[ultimo_fim:])
    return tokens


# ---------------------------------------------------------------- transformações
def infinitivo_de(gerundio: str) -> str | None:
    """fazendo → fazer, pondo → pôr, compondo → compor."""
    if gerundio == "pondo":
        return "pôr"
    for de, para in (("ando", "ar"), ("endo", "er"), ("indo", "ir"), ("ondo", "or")):
        if gerundio.endswith(de) and len(gerundio) > len(de) + 1:
            return gerundio[: -len(de)] + para
    return None


def gerundio_de(infinitivo: str) -> str | None:
    """fazer → fazendo, pôr → pondo."""
    if infinitivo == "pôr":
        return "pondo"
    for de, para in (("ar", "ando"), ("er", "endo"), ("ir", "indo"), ("or", "ondo")):
        if infinitivo.endswith(de) and len(infinitivo) > len(de):
            return infinitivo[: -len(de)] + para
    return None


def proclise_de(palavra: str) -> str | None:
    """disse-me → me disse; dá-lhe → lhe dá; amá-la → a amar. None se não souber."""
    partes = palavra.split("-")
    if len(partes) != 2:
        return None                         # mesóclise ou composto: não mexe
    verbo, pronome = partes
    if pronome in PRONOMES_OBLIQUOS or pronome in {"o", "a", "os", "as"}:
        return f"{pronome} {verbo}"
    if pronome in {"lo", "la", "los", "las"}:
        restaurado = {"á": "ar", "ê": "er", "é": "er", "í": "ir", "ô": "or"}.get(verbo[-1:])
        if restaurado and len(verbo) > 1:
            base = verbo[:-1] + restaurado
            if verbo == "pô":
                base = "pôr"
            return f"{pronome[1:]} {base}"
    return None


def _capital(texto: str) -> str:
    return texto[:1].upper() + texto[1:]


def _em(norma: "Norma") -> str:
    """'no Brasil', 'em Portugal', 'na Guiné-Bissau'."""
    preposicao = {"o": "no", "a": "na", "os": "nos", "as": "nas"}.get(norma.artigo, "em")
    return f"{preposicao} {norma.pais}"


def _imitar_maiuscula(original: str, novo: str) -> str:
    """Mantém a maiúscula do começo (Fazem → Faz)."""
    if original[:1].isupper() and novo:
        return _capital(novo)
    return novo


# ---------------------------------------------------------------- o revisor
class Revisor:
    def __init__(self, banco, lexico=None) -> None:
        self.banco = banco
        self.lexico = lexico                # opcional: ordena sugestões pela frequência
        self._versao = None
        self._normas: dict[str, Norma] = {}
        self._versao_dono = None
        self._palavras_dono: set[str] = set()

    # ------------------------------------------------------------ normas ativas
    def normas(self) -> dict[str, Norma]:
        """Normas dos addons ATIVOS (id → Norma). Recarrega se os addons mudaram."""
        versao = self.banco.versao_linguagem
        if versao == self._versao:
            return self._normas
        addons = {a["id"]: a for a in self.banco.listar_addons() if a["ativo"]}
        novas: dict[str, Norma] = {}
        for addon_id, bruto in self.banco.recursos_ativos("norma.json"):
            try:
                dados = json.loads(bytes(bruto).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                continue
            info = dados["norma"]
            a = addons.get(addon_id) or {}
            regiao = (a.get("manifesto") or {}).get("regiao") or {}
            variedades = [t for v in regiao.get("variedades") or [] for t in v.get("termos", [])]
            termos = {normalizar(t) for t in [info["nome"], info["pais"], info["id"],
                                              *regiao.get("termos", []), *variedades] if t}
            norma = Norma(info["id"], info["nome"], info["pais"], info["ortografia"], addon_id,
                          a.get("nome") or addon_id, dados, termos,
                          artigo=regiao.get("artigo", "") if normalizar(regiao.get("nome", ""))
                          == normalizar(info["pais"]) else "",
                          verbos=set(dados.get("verbos") or []))
            for item in dados.get("equivalencias") or []:
                for termo in item["termos"]:
                    partes = tuple(termo.split())
                    norma.equivalencias.setdefault(partes[0], []).append((partes, item))
            for errado, certo in (dados.get("erros_comuns") or {}).items():
                partes = tuple(errado.split())
                norma.erros_multi.setdefault(partes[0], []).append((partes, certo))
            for lista in (*norma.equivalencias.values(), *norma.erros_multi.values()):
                lista.sort(key=lambda par: -len(par[0]))      # a mais longa primeiro
            novas[info["id"]] = norma                          # o addon mais novo vence
        self._normas = novas
        self._versao = versao
        return novas

    def _vocabulario(self, norma: Norma) -> Vocabulario | None:
        if norma.vocabulario is None:
            bloco = self.banco.recurso(norma.addon_id, "vocabulario")
            if bloco:
                norma.vocabulario = Vocabulario(bytes(bloco))
        return norma.vocabulario

    def resolver_norma(self, texto: str | None) -> Norma | None:
        """'português de Portugal', 'pt-PT', 'Angola', 'europeu'… → a norma."""
        if not texto:
            return None
        alvo = normalizar(texto)
        palavras = alvo.split()
        while palavras and palavras[0] in {"o", "a", "do", "da", "de", "portugues", "lingua",
                                           "norma", "variante", "ortografia", "padrao"}:
            palavras.pop(0)
        candidatos = {alvo, " ".join(palavras)}
        for norma in self.normas().values():
            if candidatos & norma.termos:
                return norma
        apelidos = {"europeu": "pt-PT", "europeia": "pt-PT", "lusitano": "pt-PT",
                    "brasileiro": "pt-BR", "brasileira": "pt-BR", "br": "pt-BR",
                    "pt br": "pt-BR", "pt pt": "pt-PT"}
        for c in candidatos:
            if c in apelidos and apelidos[c] in self.normas():
                return self.normas()[apelidos[c]]
        return None

    def escolher(self, norma_id: str | None = None, texto_norma: str | None = None,
                 texto: str = "", padrao: str | None = None) -> tuple[Norma | None, str]:
        """
        Qual norma usar, e por quê: a pedida na mensagem, a escolhida em
        Configurações, a única ativa, ou a que melhor combina com o texto.
        """
        disponiveis = self.normas()
        if not disponiveis:
            return None, "nenhuma"
        if norma_id and norma_id in disponiveis:
            return disponiveis[norma_id], "escolhida"
        if texto_norma:
            achada = self.resolver_norma(texto_norma)
            if achada:
                return achada, "pedida"
        if padrao and padrao in disponiveis:
            return disponiveis[padrao], "configuracoes"
        if len(disponiveis) == 1:
            return next(iter(disponiveis.values())), "unica"
        return self._mais_provavel(texto, list(disponiveis.values())), "automatica"

    def _mais_provavel(self, texto: str, candidatas: list[Norma]) -> Norma:
        """
        A norma em que o texto tem menos marcas de OUTRA variante. Num empate
        (texto que serviria a várias normas), ficam as duas de referência:
        a do Brasil e a de Portugal, nessa ordem.
        """
        tokens = tokenizar(texto[:MAX_TEXTO])

        def pontos(norma: Norma) -> tuple[int, int, str]:
            marcas = sum(1 for t in tokens if t.forma in norma.dados.get("grafias", {}))
            marcas += sum(1 for t in tokens if t.forma in norma.equivalencias)
            vocab = self._vocabulario(norma)
            conhecidas = sum(1 for t in tokens if vocab and t.forma in vocab)
            referencia = {"pt-BR": 0, "pt-PT": 1}.get(norma.id, 2)
            return marcas, referencia, -conhecidas, norma.id
        return min(candidatas, key=pontos)

    # ------------------------------------------------------------ palavras aceitas
    def _aceitas(self) -> set[str]:
        """
        Palavras que nunca são apontadas como desconhecidas: as que o dono
        usou no que ensinou (nomes, termos do trabalho…) e os termos dos
        verbetes ativos (gírias e palavras regionais existem!).
        """
        versao = (self.banco.versao_conhecimento, self.banco.versao_linguagem)
        if versao == self._versao_dono:
            return self._palavras_dono
        palavras: set[str] = set()
        for doc in self.banco.conhecimentos_ativos():
            if doc.get("addon_id") and doc.get("tipo") != "verbete":
                continue
            textos = [doc.get("pergunta") or ""]
            if doc.get("addon_id"):
                textos += json.loads(doc.get("variacoes") or "[]")
            else:
                textos.append(doc.get("conteudo") or "")
            for texto in textos:
                palavras.update(t.forma for t in tokenizar(texto))
        self._palavras_dono = palavras
        self._versao_dono = versao
        return palavras

    # ------------------------------------------------------------ revisão
    def revisar(self, texto: str, norma: Norma) -> dict[str, Any]:
        texto = texto[:MAX_TEXTO]
        tokens = tokenizar(texto)
        apontamentos: list[Apontamento] = []
        apontamentos += self._multipalavras(texto, tokens, norma)
        cobertos = {i for a in apontamentos for i in range(a.inicio, a.fim)}
        apontamentos += self._palavras(texto, tokens, norma, cobertos)
        apontamentos += self._regras(texto, tokens, norma)
        apontamentos = self._sem_sobreposicao(apontamentos)
        return {
            "norma": norma.resumo(),
            "texto": texto,
            "apontamentos": [a.como_dict() for a in apontamentos],
            "texto_revisado": self.aplicar(texto, apontamentos),
            "palavras": len([t for t in tokens if not t.numero]),
        }

    def _multipalavras(self, texto: str, tokens: list[Token], norma: Norma) -> list[Apontamento]:
        """Erros comuns e equivalências de uma ou mais palavras ("casa de banho")."""
        saida: list[Apontamento] = []
        i = 0
        while i < len(tokens):
            achou = False
            for indice, nivel_tipo in ((norma.erros_multi, "erro_comum"),
                                       (norma.equivalencias, "equivalencia")):
                for partes, valor in indice.get(tokens[i].forma, []):
                    fim = i + len(partes)
                    if fim > len(tokens) or tuple(t.forma for t in tokens[i:fim]) != partes:
                        continue
                    if any(t.pausa_antes or t.inicio_frase for t in tokens[i + 1:fim]):
                        continue
                    trecho = texto[tokens[i].inicio:tokens[fim - 1].fim]
                    if nivel_tipo == "erro_comum":
                        sugestao = _imitar_maiuscula(trecho, valor)
                        saida.append(Apontamento(
                            tokens[i].inicio, tokens[fim - 1].fim, trecho, "erro", "erro_comum",
                            f"Erro comum de escrita: o certo é «{valor}».", [sugestao],
                            titulo="Erro comum"))
                    else:
                        saida.append(self._equivalencia(trecho, tokens[i].inicio,
                                                        tokens[fim - 1].fim, valor, norma))
                    i = fim
                    achou = True
                    break
                if achou:
                    break
            if not achou:
                i += 1
        return saida

    @staticmethod
    def _equivalencia(trecho: str, inicio: int, fim: int, item: dict, norma: Norma) -> Apontamento:
        uso = f" ({item['uso']})" if item.get("uso") else ""
        em = _em(norma)
        if item["nivel"] == "dica":
            mensagem = (f"Atenção: «{trecho}»{uso} tem outro sentido {em}. "
                        f"Aqui, o comum é «{item['equivale']}».")
        else:
            mensagem = (f"«{trecho}» é a forma usada em outra variante{uso}. "
                        f"{_capital(em)}, se diz «{item['equivale']}».")
        if item.get("nota"):
            mensagem += f" {item['nota']}"
        opcoes = [o.strip() for o in item["equivale"].split(" ou ") if o.strip()]
        return Apontamento(inicio, fim, trecho, item["nivel"], "equivalencia", mensagem,
                           [_imitar_maiuscula(trecho, o) for o in opcoes][:MAX_SUGESTOES],
                           titulo="Palavra de outra variante" if item["nivel"] == "variante"
                           else "Falso amigo")

    def _palavras(self, texto: str, tokens: list[Token], norma: Norma,
                  cobertos: set[int]) -> list[Apontamento]:
        """Grafias de outra norma e palavras fora do vocabulário."""
        saida: list[Apontamento] = []
        grafias = norma.dados.get("grafias") or {}
        tipos = norma.dados.get("tipos_grafia") or {}
        vocab = self._vocabulario(norma)
        aceitas = self._aceitas()
        outras = [n for n in self.normas().values() if n.id != norma.id]
        desconhecidas = 0
        for t in tokens:
            if t.numero or t.inicio in cobertos:
                continue
            # Nomes próprios e siglas: maiúscula fora do começo da frase, ou tudo maiúsculo.
            if (t.texto[:1].isupper() and not t.inicio_frase) or (len(t.texto) > 1 and t.texto.isupper()):
                continue
            w = t.forma
            if w in grafias:
                certo = grafias[w]
                motivo = normas.TIPOS_GRAFIA.get(tipos.get(w, "variante"))
                saida.append(Apontamento(
                    t.inicio, t.fim, t.texto, "grafia", "grafia",
                    f"«{t.texto}» é {motivo}. Na norma de {norma.pais} "
                    f"({normas.ORTOGRAFIAS[norma.ortografia]}): «{certo}».",
                    [_imitar_maiuscula(t.texto, certo)], titulo="Grafia de outra norma"))
                continue
            if vocab is None or self._existe(w, vocab) or w in aceitas:
                continue
            if desconhecidas >= MAX_DESCONHECIDAS:
                continue
            desconhecidas += 1
            sugestoes = self.sugerir(w, vocab)
            em_outra = next((n for n in outras if self._vocabulario(n) and
                             self._existe(w, self._vocabulario(n))), None)
            sugestoes = [_imitar_maiuscula(t.texto, s) for s in sugestoes]
            if em_outra:
                saida.append(Apontamento(
                    t.inicio, t.fim, t.texto, "grafia", "grafia",
                    f"«{t.texto}» está no vocabulário de {em_outra.nome}, mas não no de "
                    f"{norma.nome}." + (f" Aqui: «{sugestoes[0]}»." if sugestoes else ""),
                    sugestoes, titulo="Grafia de outra norma"))
            else:
                saida.append(Apontamento(
                    t.inicio, t.fim, t.texto, "ortografia", "ortografia",
                    f"Não encontrei «{t.texto}» no vocabulário de {norma.nome}."
                    + (" Talvez: " + ", ".join(f"«{s}»" for s in sugestoes) + "."
                       if sugestoes else
                       " Se for um nome ou termo que você usa, ensine-o e eu passo a aceitá-lo."),
                    sugestoes, titulo="Palavra desconhecida"))
        return saida

    @staticmethod
    def _existe(w: str, vocab: Vocabulario) -> bool:
        if w in vocab:
            return True
        if "-" not in w:
            return False
        # Verbo com pronome (dá-me, fazê-lo, dir-te-ei): confere o verbo.
        partes = w.split("-")
        cabeca, resto = partes[0], partes[1:]
        if all(p in CLITICOS or p in MESOCLISE for p in resto):
            if cabeca in vocab:
                return True
            # amá-lo → amar, fazê-la → fazer, parti-lo → partir, pô-lo → pôr
            for fim, inf in (("á", "ar"), ("ê", "er"), ("é", "er"), ("i", "ir"),
                             ("í", "ir"), ("ô", "or")):
                if cabeca.endswith(fim) and (cabeca[:-1] + inf in vocab or cabeca == "pô"):
                    return True
            # dir-te-ei, far-se-á: o infinitivo sem o -r final no futuro
            if resto[-1] in MESOCLISE and (cabeca + "r" in vocab or cabeca + "er" in vocab
                                           or cabeca in {"dir", "far", "trar"}):
                return True
            # vamo-nos, fizemo-lo: o -s que cai antes do pronome
            if cabeca + "s" in vocab or cabeca + "z" in vocab or cabeca[:-1] + "r" in vocab:
                return True
            return False
        # Palavra composta: aceita se todas as partes existem.
        return all(p in vocab for p in partes if p)

    def sugerir(self, palavra: str, vocab: Vocabulario) -> list[str]:
        """Grafias parecidas que existem no vocabulário (acentos primeiro)."""
        acentos = [c for c in self._variantes_acento(palavra) if c != palavra and c in vocab]
        if acentos:
            return self._ordenar(acentos)[:MAX_SUGESTOES]
        candidatas = {c for c in self._edicoes(palavra) if c != palavra}
        achadas = [c for c in candidatas if c in vocab]
        # Uma troca de acento depois de uma edição ("exessão" → "exceção") é
        # comum; tenta as variantes de acento das candidatas que não existem.
        if not achadas and len(palavra) <= 14:
            for c in list(candidatas)[:400]:
                achadas += [v for v in self._variantes_acento(c, 1) if v in vocab]
        return self._ordenar(list(dict.fromkeys(achadas)))[:MAX_SUGESTOES]

    def _ordenar(self, palavras: list[str]) -> list[str]:
        """Mais frequentes primeiro (se houver vetores de palavras), depois alfabética."""
        def chave(p: str) -> tuple[int, str]:
            posicao = 10 ** 9
            if self.lexico is not None:
                try:
                    _, ref = self.lexico._consultar(normalizar(p))
                    if ref is not None and ref[1] >= 0:
                        posicao = ref[1]
                except Exception:     # o léxico é só um desempate; nunca derruba a revisão
                    pass
            return posicao, p
        return sorted(palavras, key=chave)

    @staticmethod
    def _variantes_acento(palavra: str, maximo_trocas: int = 2) -> list[str]:
        """A palavra com outros acentos, mudando até `maximo_trocas` letras."""
        saida = {palavra}
        for _ in range(maximo_trocas):
            novas = set()
            for p in saida:
                for i, letra in enumerate(p):
                    for troca in _VARIANTES_ACENTO.get(letra, ""):
                        if troca != letra:
                            novas.add(p[:i] + troca + p[i + 1:])
            saida |= novas
            if len(saida) > 3_000:
                break
        return list(saida)

    @staticmethod
    def _edicoes(palavra: str) -> set[str]:
        """Todas as palavras a UMA edição de distância (Norvig)."""
        cortes = [(palavra[:i], palavra[i:]) for i in range(len(palavra) + 1)]
        apagadas = {a + b[1:] for a, b in cortes if b}
        trocadas = {a + b[1] + b[0] + b[2:] for a, b in cortes if len(b) > 1}
        substituidas = {a + c + b[1:] for a, b in cortes if b for c in _LETRAS}
        inseridas = {a + c + b for a, b in cortes for c in _LETRAS}
        # Trocas de som comuns no português: ss/ç, s/z, x/ch, g/j.
        sons = set()
        for de, para in (("ss", "ç"), ("ç", "ss"), ("s", "z"), ("z", "s"), ("x", "ch"),
                         ("ch", "x"), ("g", "j"), ("j", "g"), ("sc", "c"), ("c", "sc"),
                         ("ss", "c"), ("c", "ss"), ("s", "c"), ("ç", "s")):
            inicio = palavra.find(de)
            while inicio >= 0:
                sons.add(palavra[:inicio] + para + palavra[inicio + len(de):])
                inicio = palavra.find(de, inicio + 1)
        return apagadas | trocadas | substituidas | inseridas | sons

    # ------------------------------------------------------------ regras
    def _classe(self, classe: str, t: Token, norma: Norma) -> bool:
        w = t.forma
        if classe == "qualquer":
            return True
        if classe == "numero":
            return t.numero or w in NUMEROS
        if classe == "pronome_obliquo":
            return w in PRONOMES_OBLIQUOS
        if classe == "pronome_reto":
            return w in PRONOMES_RETOS
        if classe == "gerundio":
            inf = infinitivo_de(w) if w.endswith("ndo") else None
            return bool(inf) and (inf in norma.verbos if norma.verbos else len(w) > 4)
        if classe == "infinitivo":
            if norma.verbos:
                return w in norma.verbos
            return w.endswith(("ar", "er", "ir", "or", "ôr")) and len(w) > 3
        if classe == "participio":
            return w in PARTICIPIOS_IRREGULARES or (w.endswith(_SUFIXOS_PARTICIPIO) and len(w) > 4)
        if classe == "verbo_com_pronome":
            partes = w.split("-")
            return len(partes) >= 2 and all(p in CLITICOS or p in MESOCLISE for p in partes[1:])
        if classe == "maiuscula":
            return t.texto[:1].isupper()
        return False

    def _casa(self, elemento: dict, t: Token, norma: Norma) -> bool:
        if elemento.get("na_pergunta") and not t.na_pergunta:
            return False
        if "nao" in elemento:
            return not any(self._casa(e, t, norma) for e in elemento["nao"])
        if "palavras" in elemento:
            w = sem_acentos(t.forma) if elemento.get("sem_acento") else t.forma
            return w in elemento["_conjunto"]
        return self._classe(elemento["classe"], t, norma)

    def _casar(self, padrao: list[dict], tokens: list[Token], inicio: int,
               norma: Norma) -> list[int | None] | None:
        """
        Tenta casar o padrão a partir do token `inicio`. Devolve, para cada
        elemento, o índice do token casado (None se for opcional ausente ou
        de largura zero), ou None se não casar. Opcionais são tentados
        primeiro presentes, depois ausentes (busca com retrocesso).
        """
        def passo(e: int, i: int, anterior: int | None) -> list[int | None] | None:
            if e == len(padrao):
                return []
            el = padrao[e]
            classe = el.get("classe")
            if classe == "inicio":
                if i < len(tokens) and tokens[i].inicio_frase:
                    resto = passo(e + 1, i, anterior)
                    return None if resto is None else [None, *resto]
                return None
            if classe == "fim":
                if i == len(tokens) or tokens[i].inicio_frase:
                    resto = passo(e + 1, i, anterior)
                    return None if resto is None else [None, *resto]
                return None
            if i < len(tokens) and self._casa(el, tokens[i], norma):
                # Um padrão não atravessa vírgula nem fim de frase.
                if anterior is None or not (tokens[i].pausa_antes or tokens[i].inicio_frase):
                    resto = passo(e + 1, i + 1, i)
                    if resto is not None:
                        return [i, *resto]
            if el.get("opcional"):
                resto = passo(e + 1, i, anterior)
                return None if resto is None else [None, *resto]
            return None
        return passo(0, inicio, None)

    def _regras(self, texto: str, tokens: list[Token], norma: Norma) -> list[Apontamento]:
        saida: list[Apontamento] = []
        for regra in norma.dados.get("regras") or []:
            padrao = regra["padrao"]
            for el in padrao:      # conjuntos para comparar rápido (preparados uma vez)
                for alvo in (el, *(el.get("nao") or [])):
                    if "palavras" in alvo and "_conjunto" not in alvo:
                        alvo["_conjunto"] = set(alvo["palavras"])
            usados: set[int] = set()
            for inicio in range(len(tokens)):
                if inicio in usados:
                    continue
                casados = self._casar(padrao, tokens, inicio, norma)
                if not casados or not any(c is not None for c in casados):
                    continue
                presentes = [c for c in casados if c is not None]
                if presentes[0] != inicio:
                    continue
                usados.update(presentes)
                a, b = tokens[presentes[0]], tokens[presentes[-1]]
                trecho = texto[a.inicio:b.fim]
                sugestao = self._sugestao(regra, casados, tokens)
                if sugestao is not None and ":capital" not in regra.get("sugestao", ""):
                    sugestao = _imitar_maiuscula(trecho, sugestao)
                if sugestao is not None and sugestao == trecho:
                    continue                     # nada a mudar (ex.: troca sem efeito)
                destaque = None
                marca = regra.get("marcar")
                if marca:
                    marcados = [c for c in casados[marca[0] - 1:marca[1]] if c is not None]
                    if marcados:
                        destaque = [tokens[marcados[0]].inicio, tokens[marcados[-1]].fim]
                saida.append(Apontamento(
                    a.inicio, b.fim, trecho, regra["nivel"], "regra", regra["mensagem"],
                    [sugestao] if sugestao else [], regra["id"], regra["titulo"],
                    regra.get("exemplo"), destaque))
        return saida

    def _sugestao(self, regra: dict, casados: list[int | None],
                  tokens: list[Token]) -> str | None:
        modelo = regra.get("sugestao")
        if not modelo:
            return None
        falhou = False

        def trocar(m: re.Match) -> str:
            nonlocal falhou
            indice = casados[int(m.group(1)) - 1]
            if indice is None:
                return ""
            t = tokens[indice]
            transformacao = m.group(2)
            if not transformacao:
                return t.texto
            if transformacao == "troca":
                novo = regra.get("troca", {}).get(t.forma)
                if novo is None:
                    return t.texto
                return _imitar_maiuscula(t.texto, novo)
            if transformacao == "infinitivo":
                novo = infinitivo_de(t.forma)
            elif transformacao == "gerundio":
                novo = gerundio_de(t.forma)
            elif transformacao == "proclise":
                novo = proclise_de(t.forma)
            elif transformacao == "capital":
                novo = _capital(t.forma)
            elif transformacao == "minuscula":
                novo = t.forma
            else:
                novo = None
            if novo is None:
                falhou = True
                return t.texto
            return novo

        texto = normas._MARCADOR.sub(trocar, modelo)
        if falhou:
            return None
        return re.sub(r"\s+", " ", texto).strip()

    # ------------------------------------------------------------ resultado
    @staticmethod
    def _sem_sobreposicao(apontamentos: list[Apontamento]) -> list[Apontamento]:
        """Se dois apontamentos cobrem o mesmo trecho, fica o mais grave."""
        ordem = list(NIVEIS)
        escolhidos: list[Apontamento] = []
        for a in sorted(apontamentos, key=lambda x: (ordem.index(x.nivel), x.inicio)):
            if any(a.inicio < b.fim and b.inicio < a.fim for b in escolhidos):
                continue
            escolhidos.append(a)
        return sorted(escolhidos, key=lambda x: x.inicio)

    @staticmethod
    def aplicar(texto: str, apontamentos: list[Apontamento]) -> str:
        """O texto com as sugestões aplicadas (só nos níveis de NIVEIS_APLICADOS)."""
        partes, cursor = [], 0
        for a in sorted(apontamentos, key=lambda x: x.inicio):
            if a.nivel not in NIVEIS_APLICADOS or not a.sugestoes or a.inicio < cursor:
                continue
            partes.append(texto[cursor:a.inicio])
            partes.append(a.sugestoes[0])
            cursor = a.fim
        partes.append(texto[cursor:])
        return "".join(partes)

    # ------------------------------------------------------------ perguntas curtas
    def comparar(self, opcoes: list[str], norma: Norma) -> list[dict[str, Any]]:
        """'o certo é A ou B?' → para cada opção, se está certa e o que sugerir."""
        saida = []
        for opcao in opcoes:
            resultado = self.revisar(opcao, norma)
            apont = resultado["apontamentos"]
            graves = [a for a in apont if a["nivel"] in NIVEIS_APLICADOS]
            saida.append({"opcao": opcao, "certa": not graves, "apontamentos": apont,
                          "revisada": resultado["texto_revisado"]})
        return saida

    def grafar(self, palavra: str) -> dict[str, list[str]]:
        """
        'como se escreve economico?' → as grafias da palavra em cada norma
        ativa: {id da norma: [formas]}. Procura a forma com e sem acentos, e
        segue os mapas de grafia e de erros comuns.
        """
        w = forma(palavra)
        saida: dict[str, list[str]] = {}
        for norma in self.normas().values():
            vocab = self._vocabulario(norma)
            achadas = []
            if w in (norma.dados.get("erros_comuns") or {}):
                achadas.append(norma.dados["erros_comuns"][w])
            if w in (norma.dados.get("grafias") or {}):
                achadas.append(norma.dados["grafias"][w])
            if vocab is not None:
                if w in vocab:
                    achadas.append(w)
                achadas += [v for v in self._variantes_acento(sem_acentos(w), 3) if v in vocab]
                if not achadas:
                    achadas += self.sugerir(w, vocab)
            saida[norma.id] = list(dict.fromkeys(achadas))[:MAX_SUGESTOES]
        return saida


# ---------------------------------------------------------------- texto da resposta
def descrever(resultado: dict[str, Any], motivo: str) -> str:
    """Transforma o resultado de revisar() na resposta do chat (Markdown)."""
    n = resultado["norma"]
    como = {"pedida": "como você pediu", "configuracoes": "a escolhida em Configurações",
            "unica": "a única ativa", "automatica": "a que mais combina com o texto",
            "escolhida": "a escolhida"}.get(motivo, "")
    cabecalho = (f"Revisei pela norma **{n['nome']}** ({n['ortografia_titulo']}"
                 + (f"; {como}" if como else "") + ").")
    apont = resultado["apontamentos"]
    if not apont:
        return cabecalho + " Não encontrei nada a apontar."
    linhas = [cabecalho, f"Encontrei **{len(apont)}** "
              + ("ponto:" if len(apont) == 1 else "pontos:"), ""]
    for i, a in enumerate(apont, start=1):
        troca = f" → **{a['sugestoes'][0]}**" if a["sugestoes"] else ""
        outras = (f" (ou {', '.join(a['sugestoes'][1:])})" if len(a["sugestoes"]) > 1 else "")
        linhas.append(f"{i}. «{a['trecho']}»{troca}{outras} · *{a['nivel_titulo']}* — "
                      f"{a['mensagem']}")
    if resultado["texto_revisado"] != resultado["texto"]:
        linhas += ["", "**Texto revisado:**", ""]
        linhas += resultado["texto_revisado"].splitlines()
    avisos = [a for a in apont if a["nivel"] in ("estilo", "dica")]
    if avisos:
        linhas += ["", "*Os pontos de estilo e de atenção não entram no texto revisado.*"]
    return "\n".join(linhas)


def descrever_comparacao(opcoes: list[dict[str, Any]], norma: dict[str, Any]) -> str:
    certas = [o for o in opcoes if o["certa"]]
    linhas = [f"Na norma **{norma['nome']}**:", ""]
    for o in opcoes:
        if o["certa"]:
            linhas.append(f"- ✔ **{o['opcao']}** está certo.")
        else:
            motivo = o["apontamentos"][0]["mensagem"] if o["apontamentos"] else ""
            revisada = f" O certo seria **{o['revisada']}**." if o["revisada"] != o["opcao"] else ""
            linhas.append(f"- ✘ **{o['opcao']}** não está.{revisada} {motivo}".rstrip())
    if len(certas) == len(opcoes) and len(opcoes) > 1:
        linhas += ["", "As duas formas existem nesta norma; confira se o sentido é o que você quer."]
    return "\n".join(linhas)
