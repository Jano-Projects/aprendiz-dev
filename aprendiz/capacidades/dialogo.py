"""
Diálogo: o motor que usa a seção "dialogo" dos addons de compreensão (0.9+).

A compreensão (capacidades/compreensao.py) entende O QUE a pessoa pergunta: o tipo
da pergunta e o assunto. O diálogo entende O QUE ELA FAZ com a frase, que é
o que um ser humano percebe primeiro numa conversa:

    "Olá, consegue me ajudar?"        → cumprimenta e PEDE AJUDA, sem assunto
    "estou meio perdido hoje"         → DESABAFA
    "o que você acha da vida?"        → pede uma OPINIÃO
    "não entendi" / "não era isso"    → reage à resposta ANTERIOR
    "e em Portugal?"                  → CONTINUA a pergunta anterior

Esses são os "atos de fala". Sem eles, o Aprendiz procurava as palavras da
frase na base: "consegue me ajudar?" encontrava "ajudei-lhe" num addon de
norma, porque a única palavra com conteúdo era "ajudar".

O motor fica no app; os DADOS (gatilhos, palavras de conversa, textos das
respostas) vêm dos addons. O que fazer com cada ato é de uma lista fechada
(recursos.ACOES_DIALOGO). Sem addon de diálogo ativo, `ativo` é falso e o
pipeline segue como antes.

As peças, na ordem em que o pipeline (core/assistente.py) usa:

    1. ABERTURA — separa o cumprimento do resto: "Olá, consegue..." vira
       "Olá!" (começo da resposta) + "consegue me ajudar?" (o que tratar).

    2. CONTINUAÇÃO — "e em Portugal?" / "e o tfidf?" reescreve a pergunta
       anterior da conversa ("o que significa kota em Portugal?").

    3. ATO DE FALA — o gatilho pode ter palavras no meio ("estou MEIO
       perdido" casa com "estou perdido"): até FOLGA palavras entre duas
       palavras do gatilho.

    4. ASSUNTO REAL — o que sobra tirando stopwords, palavras de conversa
       e cumprimentos. Sem assunto real, a busca nem é feita.

Tudo é comparação de listas de palavras; nenhum texto de addon vira código.
"""

from __future__ import annotations

import json
import zlib
from dataclasses import dataclass, field
from typing import Any

from aprendiz.linguagem.normalizador import normalizar, tokenizar
from aprendiz.linguagem.stemmer import radical

FOLGA = 2                 # palavras que podem aparecer entre as do gatilho
INICIO_MAXIMO = 3         # o ato precisa começar até a 4ª palavra (depois da abertura)
MAX_CONTINUACAO = 7       # "e em Portugal?" é curta; frase longa é pergunta nova
PREPOSICOES_LUGAR = {"em", "no", "na", "nos", "nas"}
# Ligações que sobram entre o gatilho e o assunto: "o que você acha DA vida".
LIGACOES = {"de", "da", "do", "das", "dos", "sobre", "a", "o", "as", "os", "com", "em", "no",
            "na", "nos", "nas", "pra", "para", "isso", "nisso", "disso"}
ARTIGOS = {"o", "a", "os", "as", "um", "uma"}
# Artigos indefinidos: "uma gíria de Angola" é um assunto VAGO (qual gíria?).
INDEFINIDOS = {"um", "uma", "uns", "umas", "algum", "alguma", "alguns", "algumas", "qualquer"}
# Até quantas palavras depois do indefinido o assunto ainda é vago (2.5.1).
MAX_ASSUNTO_VAGO = 3
# "sim" e "não" só valem como a mensagem INTEIRA ("consegue fazer isso?" não é um "sim").
SO_A_FRASE = {"confirmar", "negar"}
# Ações que só valem quando a mensagem NÃO traz assunto além do gatilho.
SO_SEM_ASSUNTO = {"responder", "reformular", "outras_opcoes", "confirmar", "negar"}


@dataclass
class Leitura:
    """O que o diálogo entendeu de uma mensagem (vai para o painel)."""

    abertura: str | None = None            # "Olá!" — começo da resposta
    resto: str = ""                        # a mensagem sem a abertura (texto original)
    ato: dict[str, Any] | None = None      # o ato de fala reconhecido
    gatilho: str | None = None
    assunto: str | None = None             # o que vem depois do gatilho (texto original)
    # 2.5.1: o mesmo, sem tirar as ligações do começo ("os 10 clientes…",
    # "o que o c++ tem…"): é o que segue para a busca.
    pergunta: str | None = None
    assunto_real: list[str] = field(default_factory=list)  # palavras que são assunto
    vago: bool = False                     # "uma gíria de Angola": qual?
    continuacao: str | None = None         # pergunta anterior reescrita

    def como_dict(self) -> dict[str, Any]:
        return {"abertura": self.abertura or "—",
                "ato": f"{self.ato['id']} ({self.ato['acao']})" if self.ato else "—",
                "gatilho": self.gatilho or "—", "assunto": self.assunto or "—",
                "palavras de assunto": ", ".join(self.assunto_real) or "nenhuma",
                "assunto vago": "sim" if self.vago else "não",
                "continuação": self.continuacao or "—"}


def escolher(textos: list[str], semente: str) -> str:
    """Um dos textos, sempre o mesmo para a mesma mensagem (testes estáveis)."""
    return textos[zlib.crc32(semente.encode("utf-8")) % len(textos)]


def _casar(tokens: list[str], frase: tuple[str, ...], ate: int | None) -> tuple[int, int] | None:
    """
    Procura `frase` em `tokens` aceitando até FOLGA palavras entre duas
    palavras dela. Devolve (início, fim) ou None. `ate` limita a posição
    do início (None = qualquer posição).
    """
    limite = len(tokens) if ate is None else min(len(tokens), ate + 1)
    for inicio in range(limite):
        if tokens[inicio] != frase[0]:
            continue
        pos, ok = inicio, True
        for palavra in frase[1:]:
            achou = next((j for j in range(pos + 1, min(len(tokens), pos + 2 + FOLGA))
                          if tokens[j] == palavra), None)
            if achou is None:
                ok = False
                break
            pos = achou
        if ok:
            return inicio, pos + 1
    return None


def _palavras_originais(mensagem: str) -> list[str]:
    return [p for p in mensagem.replace(",", " , ").split() if p]


class Dialogo:
    def __init__(self, banco, linguagem) -> None:
        self.banco = banco
        self.linguagem = linguagem
        self._versao = -1
        self.dados: dict[str, Any] = {}

    # ------------------------------------------------------------------ dados
    def _frase(self, texto: str) -> tuple[str, ...]:
        """Gatilho processado do MESMO jeito que a mensagem (lemas, sinônimos...)."""
        return tuple(self.linguagem.processar(texto, corrigir=False).tokens)

    def _carregar(self) -> None:
        """Junta as seções "dialogo" dos addons ativos (refaz quando algo muda)."""
        if self._versao == self.banco.versao_linguagem:
            return
        dados: dict[str, Any] = {"aberturas": [], "conversa": set(), "sem_assunto": [],
                                 "continuacoes": [], "atos": []}
        atos: dict[str, dict] = {}
        for _, bruto in self.banco.recursos_ativos("compreensao.json"):
            doc = json.loads(bruto).get("dialogo") or {}
            for frase, texto in (doc.get("aberturas") or {}).items():
                dados["aberturas"].append((self._frase(frase), texto))
            for palavra in doc.get("conversa") or []:
                dados["conversa"].add(radical(palavra))
                for t in self._frase(palavra):
                    dados["conversa"].add(radical(t))
            dados["sem_assunto"] += doc.get("sem_assunto") or []
            dados["continuacoes"] += [self._frase(c) for c in doc.get("continuacoes") or []]
            for ato in doc.get("atos") or []:
                atos[ato["id"]] = {**ato, "_frases": [(self._frase(g), g) for g in ato["gatilhos"]]}
        # Abertura e gatilho mais longos primeiro: "boa noite" antes de "boa".
        dados["aberturas"].sort(key=lambda a: -len(a[0]))
        dados["atos"] = list(atos.values())
        for ato in dados["atos"]:
            ato["_frases"].sort(key=lambda f: -len(f[0]))
        self.dados = dados
        self._versao = self.banco.versao_linguagem

    @property
    def ativo(self) -> bool:
        self._carregar()
        return bool(self.dados["atos"] or self.dados["conversa"] or self.dados["aberturas"])

    # ------------------------------------------------------------------ assunto
    def assunto_real(self, tokens: list[str]) -> list[str]:
        """Palavras que dizem DE QUE se trata (sem stopwords, conversa e cumprimentos)."""
        self._carregar()
        cumprimentos = {t for frase, _ in self.dados["aberturas"] for t in frase}
        return [t for t in tokens
                if t not in self.linguagem.stopwords and t not in cumprimentos
                and radical(t) not in self.dados["conversa"] and not t.isdigit()]

    # ------------------------------------------------------------------ 1. abertura
    def _abertura(self, mensagem: str, tokens: list[str]) -> tuple[str | None, str, int]:
        """
        Tira os cumprimentos do começo. Devolve (resposta da abertura, resto
        da mensagem original, quantos tokens foram tirados). Só tira se
        sobrar alguma coisa: "bom dia" sozinho é das intenções sociais.
        """
        respostas: list[str] = []
        pulados = 0
        mudou = True
        while mudou:
            mudou = False
            for frase, texto in self.dados["aberturas"]:
                n = len(frase)
                if tuple(tokens[pulados:pulados + n]) == frase and len(tokens) > pulados + n:
                    if texto not in respostas:
                        respostas.append(texto)
                    pulados += n
                    mudou = True
                    break
        if not pulados:
            return None, mensagem, 0
        return " ".join(respostas), self._depois(mensagem, pulados), pulados

    def _depois(self, mensagem: str, pular: int) -> str:
        """O texto ORIGINAL depois dos `pular` primeiros tokens (com acentos)."""
        palavras = _palavras_originais(mensagem)
        consumidas = i = 0
        while consumidas < pular and i < len(palavras):
            consumidas += len(self.linguagem._expandir(tokenizar(normalizar(palavras[i])), {}))
            i += 1
        while i < len(palavras) and palavras[i] in (",", "!", ".", "-", "—"):
            i += 1
        return " ".join(palavras[i:]).replace(" , ", ", ").strip(" ?!.,;:") or ""

    # ------------------------------------------------------------------ 2. continuação
    def continuar(self, tokens: list[str], mensagem: str, anterior: str | None,
                  compreensao=None) -> str | None:
        """
        "e em Portugal?" depois de "o que significa kota em Angola?" →
        "o que significa kota em Portugal". Devolve a pergunta reescrita.
        """
        if not anterior or len(tokens) > MAX_CONTINUACAO:
            return None
        frase = next((f for f in self.dados["continuacoes"] if tuple(tokens[:len(f)]) == f), None)
        if not frase:
            return None
        # O que vem depois do "e": "em Portugal", "o tfidf".
        cauda = " ".join(_palavras_originais(mensagem)[1:]).strip(" ?!.,;:")
        if not cauda:
            return None
        base = _palavras_originais(anterior.strip().rstrip("?!.").strip())
        segunda = tokens[1] if len(tokens) > 1 else ""
        if segunda in PREPOSICOES_LUGAR:
            # Troca o último "em/no/na X" da pergunta anterior; se não houver, acrescenta.
            for i in range(len(base) - 1, 0, -1):
                if normalizar(base[i]) in PREPOSICOES_LUGAR:
                    return " ".join(base[:i] + [cauda])
            return " ".join(base + [cauda])
        if segunda in ARTIGOS or segunda in ("sobre", "quanto", "para", "com"):
            # Troca o ASSUNTO da pergunta anterior: "o que é bm25" → "o que é tfidf".
            novo = cauda.split(" ", 1)[1] if segunda in ARTIGOS | {"sobre"} and " " in cauda else cauda
            if compreensao is not None and compreensao.ativa:
                consulta = self.linguagem.processar(anterior)
                analise = compreensao.analisar(consulta, anterior)
                if analise.tipo and analise.assunto:
                    corte = anterior.rfind(analise.assunto)
                    if corte > 0:
                        return f"{anterior[:corte].strip()} {novo}"
            return None
        return None

    # ------------------------------------------------------------------ 3. ato
    def ler(self, mensagem: str, tokens: list[str]) -> Leitura:
        """Abertura, ato de fala e assunto de uma mensagem."""
        self._carregar()
        leitura = Leitura(resto=mensagem)
        # Um ato que começa na 1ª palavra e é mais longo que o cumprimento vence
        # o cumprimento: "tudo bem com você?" é pergunta, não abertura.
        inteiro = self._atos(tokens)
        abertura = self._abertura(mensagem, tokens)
        if abertura[2] and any(c[3][0] == 0 and -c[1] > abertura[2] for c in inteiro):
            abertura = (None, mensagem, 0)
        leitura.abertura, leitura.resto, pulados = abertura
        resto_tokens = tokens[pulados:]
        candidatos = inteiro if not pulados else self._atos(resto_tokens)
        if candidatos:
            candidatos.sort(key=lambda c: (c[0], c[3][0], c[1]))
            _, _, ato, (inicio, fim), original = candidatos[0]
            leitura.ato, leitura.gatilho = ato, original
            leitura.assunto_real = self.assunto_real(resto_tokens[fim:])
            depois = self._depois(leitura.resto, fim).split()
            leitura.pergunta = " ".join(depois) or None
            while depois and normalizar(depois[0]) in LIGACOES:
                depois.pop(0)
            if depois and normalizar(depois[0]) in INDEFINIDOS and len(depois) > 1:
                # Vago é o assunto CURTO ("uma senha", "uma gíria de Angola").
                # Uma descrição ("uma função que chama ela mesma", "um laço
                # dentro de outro laço") já diz o que se quer (2.5.1).
                resto = [normalizar(p) for p in depois[1:]]
                leitura.vago = len(resto) <= MAX_ASSUNTO_VAGO and "que" not in resto
                depois.pop(0)
            leitura.assunto = " ".join(depois) or None
        else:
            leitura.assunto_real = self.assunto_real(resto_tokens)
        return leitura

    def _atos(self, tokens: list[str]) -> list[tuple[int, int, dict, tuple[int, int], str]]:
        """Atos cujo gatilho aparece nos tokens: (prioridade, -tamanho, ato, (início, fim), gatilho)."""
        candidatos = []
        for ato in self.dados["atos"]:
            ate = None if ato["acao"] == "crise" else INICIO_MAXIMO
            for frase, original in ato["_frases"]:
                achado = _casar(tokens, frase, ate)
                if achado and ato["acao"] in SO_A_FRASE and (
                        achado[0] > 0 or len(tokens) - achado[1] > 1):
                    continue
                if achado:
                    prioridade = 0 if ato["acao"] == "crise" else 1
                    candidatos.append((prioridade, -len(frase), ato, achado, original))
                    break
        return candidatos

    def texto(self, ato: dict, semente: str, assunto: str | None = None,
              vago: bool = False) -> str:
        """O texto de resposta de um ato, com {assunto} preenchido."""
        lista = ato["respostas"]
        if not assunto and ato.get("sem_assunto"):
            lista = ato["sem_assunto"]
        elif assunto and vago and ato.get("assunto_vago"):
            lista = ato["assunto_vago"]
        return escolher(lista, semente).replace("{assunto}", assunto or "isso")

    def cobre(self, assunto_real: list[str], texto_busca: str) -> bool:
        """O conhecimento fala de TODAS as palavras do assunto? (radicais)"""
        radicais = set(texto_busca.split())
        return all(radical(t) in radicais for t in assunto_real)

    def sem_assunto(self, semente: str) -> str | None:
        self._carregar()
        return escolher(self.dados["sem_assunto"], semente) if self.dados["sem_assunto"] else None
