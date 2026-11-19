"""
Normas da língua (Aprendiz 0.8+): os arquivos que os addons "norma" trazem
e a validação de cada um.

Uma NORMA é o jeito de escrever o português de um país: o vocabulário
(quais palavras existem e como se grafam), a ortografia em vigor (Acordo
de 1990 ou a anterior), as palavras que lá se dizem de outro jeito
("autocarro" em Portugal, "ônibus" no Brasil) e as regras de gramática que
a revisão de texto aponta. O MOTOR da revisão está no app
(capacidades/revisao.py); o addon traz só dados, validados aqui.

norma.json  (classificação "norma")
-----------------------------------
    {
      "norma": {
          "id": "pt-PT",                     ← "pt-" + duas letras maiúsculas
          "nome": "Português de Portugal",
          "pais": "Portugal",
          "ortografia": "1990"               ← "1990" (Acordo Ortográfico),
                                               "1945" (norma anterior, sem o
                                               Acordo) ou "ambas"
      },
      "fontes": ["Vocabulário derivado de ..."],   → atribuição dos dados

      "grafias": {"acção": "ação", ...},
          → formas de OUTRA norma (ou de outra ortografia) e a forma desta
            norma. Minúsculas, com acentos.
      "tipos_grafia": {"acção": "ortografia_anterior", ...}   (opcional)
          → por que a grafia muda (lista fechada TIPOS_GRAFIA)

      "erros_comuns": {"excessão": "exceção", "concerteza": "com certeza"},
          → escritas erradas muito comuns e a correta

      "equivalencias": [
          {"termos": ["autocarro", "autocarros"], "equivale": "ônibus",
           "uso": "Portugal e África", "nota": "...", "nivel": "variante"}],
          → palavras ou expressões (até 5 palavras) de OUTRA variante e o
            equivalente nesta. "nivel": "variante" (só outro uso) ou "dica"
            (falso amigo: a palavra existe aqui com outro sentido)

      "verbos": ["fazer", "dizer", ...],
          → infinitivos (classe "infinitivo" das regras)

      "regras": [ ... ]   → regras de gramática, descritas abaixo
    }

vocabulario.tsv  (opcional, junto com norma.json)
-------------------------------------------------
    Uma forma por linha, em minúsculas e COM acentos ("ação", "económico").
    É o dicionário de grafias da norma: uma palavra que não está aqui (nem
    no que o dono ensinou) é apontada pela revisão. Linhas com # são
    comentários. Pode ter milhões de linhas: o app guarda o arquivo como um
    bloco único, ORDENADO, e procura por busca binária (sem carregar uma
    lista de palavras na memória).

Regras de gramática
-------------------
Cada regra descreve uma sequência de palavras (o PADRÃO), o que sugerir no
lugar e por quê. Não há expressões regulares nem código vindo do addon:
o padrão é uma lista de ELEMENTOS de tipos fixos.

    {
      "id": "fazer-tempo",
      "nivel": "erro",                         → NIVEIS_REGRA
      "titulo": "Fazer indicando tempo",
      "padrao": [
          {"palavras": ["fazem", "faziam"]},   → uma destas palavras
          {"classe": "numero"},                → uma palavra da classe (CLASSES)
          {"palavras": ["anos", "meses"]}],
      "sugestao": "{1:troca} {2} {3}",          → o trecho corrigido
      "troca": {"fazem": "faz", "faziam": "fazia"},
      "mensagem": "Indicando tempo decorrido, 'fazer' fica no singular.",
      "exemplo": {"errado": "Fazem dois anos.", "certo": "Faz dois anos."}
    }

    Elementos do padrão (um destes, mais as opções):
        {"palavras": [...]}         palavra igual a uma da lista (minúsculas;
                                    com "sem_acento": true, ignora acentos)
        {"classe": "..."}           palavra de uma classe fixa (CLASSES)
        {"nao": {elemento}}         qualquer palavra que NÃO case com o elemento
        {"nao": [{...}, {...}]}     qualquer palavra que não case com NENHUM deles
        "opcional": true            o elemento pode faltar
        "na_pergunta": true         a palavra precisa estar numa frase que
                                    termina com "?"

    Na sugestão, {n} é a n-ésima palavra casada (contando os elementos do
    padrão a partir de 1; um elemento opcional ausente vira texto vazio).
    {n:transformacao} aplica uma transformação da lista fechada
    TRANSFORMACOES. "marcar": [i, j] (opcional) diz quais elementos
    sublinhar; o padrão é todos.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

ARQUIVO_NORMA = "norma.json"
ARQUIVO_VOCABULARIO = "vocabulario.tsv"

MAX_GRAFIAS = 600_000
MAX_EQUIVALENCIAS = 20_000
MAX_VERBOS = 60_000
MAX_REGRAS = 3_000
MAX_ELEMENTOS = 8
MAX_PALAVRAS_ELEMENTO = 4_000
MAX_VOCABULARIO = 6_000_000
MAX_TEXTO = 2_000

ORTOGRAFIAS = {
    "1990": "Acordo Ortográfico de 1990",
    "1945": "ortografia anterior ao Acordo de 1990",
    "ambas": "as duas ortografias (com e sem o Acordo de 1990)",
}

# Por que uma grafia de outra norma muda nesta (mensagens da revisão).
TIPOS_GRAFIA: dict[str, str] = {
    "variante": "grafia de outra variante do português",
    "ortografia_anterior": "grafia anterior ao Acordo Ortográfico de 1990",
    "ortografia_nova": "grafia do Acordo Ortográfico de 1990, que esta norma não adota",
    "acento": "acento de outra variante (timbre aberto/fechado)",
    "consoante": "consoante que se escreve numa variante e não na outra",
}

# Níveis das regras, do mais grave ao mais leve (a revisão ordena por eles).
NIVEIS_REGRA: dict[str, str] = {
    "erro": "Erro",
    "norma": "Fora da norma-padrão",
    "variante": "Uso de outra variante",
    "estilo": "Estilo",
    "dica": "Atenção",
}

# Classes de palavra que as regras podem usar. O APP decide o que cada uma
# quer dizer (capacidades/revisao.py); o addon só escolhe da lista.
CLASSES: dict[str, str] = {
    "qualquer": "qualquer palavra",
    "inicio": "começo de frase (não consome palavra)",
    "fim": "fim de frase (não consome palavra)",
    "numero": "número (em algarismos ou por extenso)",
    "pronome_obliquo": "pronome oblíquo átono (me, te, se, lhe, nos, vos, o, a…)",
    "pronome_reto": "pronome pessoal reto (eu, tu, ele, nós, vocês…)",
    "gerundio": "verbo no gerúndio (fazendo, dizendo…)",
    "infinitivo": "verbo no infinitivo (fazer, dizer…)",
    "participio": "particípio (feito, falado, partida…)",
    "verbo_com_pronome": "verbo com pronome ligado por hífen (disse-me, dá-lhe…)",
    "maiuscula": "palavra que começa com letra maiúscula",
}

# Transformações que a sugestão pode aplicar a uma palavra casada.
TRANSFORMACOES: dict[str, str] = {
    "troca": "troca pela forma indicada no mapa 'troca' da regra",
    "infinitivo": "gerúndio → infinitivo (fazendo → fazer)",
    "gerundio": "infinitivo → gerúndio (fazer → fazendo)",
    "proclise": "pronome para antes do verbo (disse-me → me disse)",
    "capital": "primeira letra maiúscula",
    "minuscula": "tudo em minúsculas",
}

_ID_NORMA = re.compile(r"^pt-[A-Z]{2}$")
_ID_REGRA = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
_CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# Uma "forma": letras (com acento), hífen e apóstrofo; minúsculas.
_FORMA = re.compile(r"^[a-zà-öø-ÿ](?:[a-zà-öø-ÿ'-]{0,58}[a-zà-öø-ÿ.])?$")
_MARCADOR = re.compile(r"\{(\d+)(?::([a-z]+))?\}")


class ErroNorma(ValueError):
    """Arquivo de norma inválido (vira ErroAddon em addons.py)."""


def forma(texto: str) -> str:
    """Como uma palavra é comparada no vocabulário: NFC e minúsculas."""
    return unicodedata.normalize("NFC", texto).lower()


# ---------------------------------------------------------------- utilidades
def _texto(valor: Any, maximo: int, campo: str, obrigatorio: bool = True) -> str:
    if valor is None and not obrigatorio:
        return ""
    if not isinstance(valor, str):
        raise ErroNorma(f"'{campo}' precisa ser texto.")
    valor = _CONTROLE.sub("", valor).strip()
    if (obrigatorio and not valor) or len(valor) > maximo:
        raise ErroNorma(f"'{campo}' precisa ter de 1 a {maximo} caracteres.")
    return valor


def _forma(valor: Any, campo: str, frase: int = 1) -> str:
    """Uma palavra (ou até `frase` palavras) em minúsculas, validada."""
    if not isinstance(valor, str) or len(valor) > 120:
        raise ErroNorma(f"'{campo}' precisa ser um texto curto.")
    partes = forma(valor).split()
    if not partes or len(partes) > frase or not all(_FORMA.match(p) for p in partes):
        raise ErroNorma(f"'{campo}': {valor!r} não é uma palavra válida.")
    return " ".join(partes)


def _mapa(bruto: Any, maximo: int, campo: str, frase: int = 1) -> dict[str, str]:
    if bruto is None:
        return {}
    if not isinstance(bruto, dict) or len(bruto) > maximo:
        raise ErroNorma(f"'{campo}' precisa ser um objeto com até {maximo} itens.")
    saida = {}
    for de, para in bruto.items():
        de = _forma(de, campo, frase)
        saida[de] = _forma(para, f"{campo}[{de}]", 5)
    return saida


# ---------------------------------------------------------------- norma.json
def validar_norma(bruto: Any) -> dict[str, Any]:
    """Valida norma.json e devolve tudo já normalizado (formas em minúsculas)."""
    if not isinstance(bruto, dict):
        raise ErroNorma(f"{ARQUIVO_NORMA} precisa ser um objeto JSON.")
    conhecidas = {"norma", "fontes", "grafias", "tipos_grafia", "erros_comuns",
                  "equivalencias", "verbos", "regras"}
    sobrando = set(bruto) - conhecidas
    if sobrando:
        raise ErroNorma(f"{ARQUIVO_NORMA} tem seções desconhecidas: {', '.join(sorted(sobrando))}.")

    info = bruto.get("norma")
    if not isinstance(info, dict):
        raise ErroNorma(f"{ARQUIVO_NORMA} precisa da seção 'norma' (id, nome, ortografia).")
    id_ = info.get("id")
    if not isinstance(id_, str) or not _ID_NORMA.match(id_):
        raise ErroNorma("'norma.id' precisa ser como pt-BR, pt-PT, pt-AO...")
    ortografia = info.get("ortografia")
    if ortografia not in ORTOGRAFIAS:
        raise ErroNorma(f"'norma.ortografia' precisa ser {', '.join(ORTOGRAFIAS)}.")
    saida: dict[str, Any] = {
        "norma": {"id": id_, "nome": _texto(info.get("nome"), 80, "norma.nome"),
                  "pais": _texto(info.get("pais"), 60, "norma.pais"),
                  "ortografia": ortografia},
    }

    fontes = bruto.get("fontes") or []
    if not isinstance(fontes, list) or len(fontes) > 20:
        raise ErroNorma("'fontes' precisa ser uma lista de até 20 textos.")
    saida["fontes"] = [_texto(f, 500, "fontes") for f in fontes]

    saida["grafias"] = _mapa(bruto.get("grafias"), MAX_GRAFIAS, "grafias")
    tipos = bruto.get("tipos_grafia") or {}
    if not isinstance(tipos, dict) or len(tipos) > MAX_GRAFIAS:
        raise ErroNorma("'tipos_grafia' precisa ser um objeto.")
    saida["tipos_grafia"] = {}
    for de, tipo in tipos.items():
        de = _forma(de, "tipos_grafia")
        if tipo not in TIPOS_GRAFIA:
            raise ErroNorma(f"'tipos_grafia[{de}]' precisa ser um destes: {', '.join(TIPOS_GRAFIA)}.")
        if de not in saida["grafias"]:
            raise ErroNorma(f"'tipos_grafia[{de}]' não corresponde a nenhuma grafia.")
        saida["tipos_grafia"][de] = tipo
    saida["erros_comuns"] = _mapa(bruto.get("erros_comuns"), MAX_EQUIVALENCIAS, "erros_comuns", 3)

    equivalencias = bruto.get("equivalencias") or []
    if not isinstance(equivalencias, list) or len(equivalencias) > MAX_EQUIVALENCIAS:
        raise ErroNorma(f"'equivalencias' precisa ser uma lista de até {MAX_EQUIVALENCIAS} itens.")
    saida["equivalencias"] = []
    for i, item in enumerate(equivalencias, start=1):
        campo = f"equivalencias[{i}]"
        if not isinstance(item, dict):
            raise ErroNorma(f"'{campo}' precisa ser um objeto JSON.")
        termos = item.get("termos")
        if not isinstance(termos, list) or not termos or len(termos) > 30:
            raise ErroNorma(f"'{campo}.termos' precisa ser uma lista de 1 a 30 termos.")
        nivel = item.get("nivel", "variante")
        if nivel not in ("variante", "dica"):
            raise ErroNorma(f"'{campo}.nivel' precisa ser \"variante\" ou \"dica\".")
        saida["equivalencias"].append({
            "termos": list(dict.fromkeys(_forma(t, f"{campo}.termos", 5) for t in termos)),
            "equivale": _texto(item.get("equivale"), 120, f"{campo}.equivale"),
            "uso": _texto(item.get("uso"), 120, f"{campo}.uso", obrigatorio=False),
            "nota": _texto(item.get("nota"), MAX_TEXTO, f"{campo}.nota", obrigatorio=False),
            "nivel": nivel,
        })

    verbos = bruto.get("verbos") or []
    if not isinstance(verbos, list) or len(verbos) > MAX_VERBOS:
        raise ErroNorma(f"'verbos' precisa ser uma lista de até {MAX_VERBOS} infinitivos.")
    saida["verbos"] = sorted({_forma(v, "verbos") for v in verbos})

    regras = bruto.get("regras") or []
    if not isinstance(regras, list) or len(regras) > MAX_REGRAS:
        raise ErroNorma(f"'regras' precisa ser uma lista de até {MAX_REGRAS} regras.")
    ids: set[str] = set()
    saida["regras"] = []
    for i, regra in enumerate(regras, start=1):
        nova = validar_regra(regra, f"regras[{i}]")
        if nova["id"] in ids:
            raise ErroNorma(f"Há duas regras com o id {nova['id']!r}.")
        ids.add(nova["id"])
        saida["regras"].append(nova)
    return saida


def _elemento(bruto: Any, campo: str, dentro_de_nao: bool = False) -> dict[str, Any]:
    if not isinstance(bruto, dict):
        raise ErroNorma(f"'{campo}' precisa ser um objeto JSON.")
    tipos = [t for t in ("palavras", "classe", "nao") if t in bruto]
    if len(tipos) != 1:
        raise ErroNorma(f"'{campo}' precisa de exatamente um destes: palavras, classe, nao.")
    novo: dict[str, Any] = {}
    if "palavras" in bruto:
        lista = bruto["palavras"]
        if not isinstance(lista, list) or not lista or len(lista) > MAX_PALAVRAS_ELEMENTO:
            raise ErroNorma(f"'{campo}.palavras' precisa ser uma lista de 1 a "
                            f"{MAX_PALAVRAS_ELEMENTO} palavras.")
        sem_acento = bool(bruto.get("sem_acento"))
        palavras = [_forma(p, f"{campo}.palavras") for p in lista]
        if sem_acento:
            palavras = [sem_acentos(p) for p in palavras]
        novo["palavras"] = sorted(set(palavras))
        if sem_acento:
            novo["sem_acento"] = True
    elif "classe" in bruto:
        if bruto["classe"] not in CLASSES:
            raise ErroNorma(f"'{campo}.classe' precisa ser uma destas: {', '.join(CLASSES)}.")
        novo["classe"] = bruto["classe"]
    else:
        if dentro_de_nao:
            raise ErroNorma(f"'{campo}': um 'nao' não pode conter outro 'nao'.")
        lista = bruto["nao"] if isinstance(bruto["nao"], list) else [bruto["nao"]]
        if not lista or len(lista) > 5:
            raise ErroNorma(f"'{campo}.nao' precisa de 1 a 5 elementos.")
        internos = [_elemento(e, f"{campo}.nao", True) for e in lista]
        if any(i.get("classe") in ("inicio", "fim") for i in internos):
            raise ErroNorma(f"'{campo}.nao' não pode usar começo ou fim de frase.")
        novo["nao"] = internos
    for opcao in ("opcional", "na_pergunta"):
        if bruto.get(opcao):
            if dentro_de_nao:
                raise ErroNorma(f"'{campo}': '{opcao}' vale para o elemento, não para o "
                                "'nao' interno.")
            if novo.get("classe") in ("inicio", "fim"):
                raise ErroNorma(f"'{campo}': '{opcao}' não vale para começo ou fim de frase.")
            novo[opcao] = True
    return novo


def validar_regra(bruto: Any, campo: str) -> dict[str, Any]:
    if not isinstance(bruto, dict):
        raise ErroNorma(f"'{campo}' precisa ser um objeto JSON.")
    id_ = bruto.get("id")
    if not isinstance(id_, str) or not _ID_REGRA.match(id_):
        raise ErroNorma(f"'{campo}.id' precisa ter letras minúsculas, números e hífen.")
    campo = f"regra {id_}"
    nivel = bruto.get("nivel")
    if nivel not in NIVEIS_REGRA:
        raise ErroNorma(f"'{campo}.nivel' precisa ser um destes: {', '.join(NIVEIS_REGRA)}.")
    padrao = bruto.get("padrao")
    if not isinstance(padrao, list) or not padrao or len(padrao) > MAX_ELEMENTOS:
        raise ErroNorma(f"'{campo}.padrao' precisa ter de 1 a {MAX_ELEMENTOS} elementos.")
    elementos = [_elemento(e, f"{campo}.padrao[{n}]") for n, e in enumerate(padrao, start=1)]
    if not any(e.get("classe") not in ("inicio", "fim") and not e.get("opcional")
               for e in elementos):
        raise ErroNorma(f"'{campo}.padrao' precisa casar com pelo menos uma palavra.")

    sugestao = bruto.get("sugestao")
    troca = _mapa(bruto.get("troca"), 2_000, f"{campo}.troca", 3) if bruto.get("troca") else {}
    if sugestao is not None:
        sugestao = _texto(sugestao, 300, f"{campo}.sugestao", obrigatorio=False)
        for numero, transformacao in _MARCADOR.findall(sugestao):
            if not 1 <= int(numero) <= len(elementos):
                raise ErroNorma(f"'{campo}.sugestao' usa {{{numero}}}, mas o padrão tem "
                                f"{len(elementos)} elementos.")
            if transformacao and transformacao not in TRANSFORMACOES:
                raise ErroNorma(f"'{campo}.sugestao': transformação desconhecida "
                                f"{transformacao!r}. Válidas: {', '.join(TRANSFORMACOES)}.")
            if transformacao == "troca" and not troca:
                raise ErroNorma(f"'{campo}.sugestao' usa :troca, mas a regra não tem 'troca'.")
    marcar = bruto.get("marcar")
    if marcar is not None:
        if (not isinstance(marcar, list) or len(marcar) != 2
                or not all(isinstance(n, int) and not isinstance(n, bool) for n in marcar)
                or not 1 <= marcar[0] <= marcar[1] <= len(elementos)):
            raise ErroNorma(f"'{campo}.marcar' precisa ser [início, fim] dentro do padrão.")
    exemplo = bruto.get("exemplo")
    if exemplo is not None:
        if not isinstance(exemplo, dict):
            raise ErroNorma(f"'{campo}.exemplo' precisa ser um objeto.")
        exemplo = {k: _texto(exemplo.get(k), 300, f"{campo}.exemplo.{k}")
                   for k in ("errado", "certo")}
    nova = {
        "id": id_, "nivel": nivel,
        "titulo": _texto(bruto.get("titulo"), 120, f"{campo}.titulo"),
        "padrao": elementos,
        "mensagem": _texto(bruto.get("mensagem"), MAX_TEXTO, f"{campo}.mensagem"),
    }
    if sugestao:
        nova["sugestao"] = sugestao
    if troca:
        nova["troca"] = troca
    if marcar:
        nova["marcar"] = marcar
    if exemplo:
        nova["exemplo"] = exemplo
    return nova


def sem_acentos(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return unicodedata.normalize("NFC", "".join(c for c in decomposto
                                                if not unicodedata.combining(c)))


# ---------------------------------------------------------------- vocabulario.tsv
def validar_vocabulario(bruto: bytes) -> bytes:
    """
    vocabulario.tsv → o BLOCO que o app guarda: as formas em NFC, minúsculas,
    sem repetição, ORDENADAS e separadas por "\\n", com um "\\n" no começo e
    no fim (assim toda forma fica entre dois "\\n" e a busca binária é simples).
    """
    try:
        texto = bruto.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ErroNorma(f"{ARQUIVO_VOCABULARIO} precisa estar em UTF-8.") from None
    del bruto
    # Lido linha a linha (io.StringIO), sem montar uma lista de milhões de
    # textos. Se o arquivo já vier ordenado e sem repetição (como os da loja
    # oficial), o bloco é montado direto; senão, ordenamos.
    import io

    def formas():
        for n, linha in enumerate(io.StringIO(texto), start=1):
            linha = linha.split("\t", 1)[0].strip()
            if not linha or linha.startswith("#"):
                continue
            palavra = forma(linha)
            if not _FORMA.match(palavra):
                raise ErroNorma(f"{ARQUIVO_VOCABULARIO}, linha {n}: {linha!r} não é "
                                "uma palavra válida.")
            yield palavra

    saida = io.BytesIO()
    saida.write(b"\n")
    anterior, total = "", 0
    for palavra in formas():
        if palavra <= anterior:          # fora de ordem ou repetida: ordena tudo
            unicas = sorted(set(formas()))
            if len(unicas) > MAX_VOCABULARIO:
                raise ErroNorma(f"{ARQUIVO_VOCABULARIO} passa do limite de "
                                f"{MAX_VOCABULARIO} formas.")
            return ("\n" + "\n".join(unicas) + "\n").encode("utf-8")
        anterior = palavra
        total += 1
        if total > MAX_VOCABULARIO:
            raise ErroNorma(f"{ARQUIVO_VOCABULARIO} passa do limite de {MAX_VOCABULARIO} formas.")
        saida.write(palavra.encode("utf-8") + b"\n")
    if not total:
        raise ErroNorma(f"{ARQUIVO_VOCABULARIO} está vazio.")
    return saida.getvalue()


@dataclass
class Vocabulario:
    """
    Um vocabulário guardado como um bloco de bytes ordenado. A busca é
    BINÁRIA direto nos bytes: escolhe um ponto no meio, acha a linha em
    que ele cai e compara. Como o UTF-8 preserva a ordem dos caracteres,
    a ordem dos bytes é a mesma da lista ordenada em Python.

    Custo: ~22 comparações para 3 milhões de formas, sem montar nenhuma
    lista na memória (só o bloco, que já está lá).
    """

    bloco: bytes = b"\n"
    total: int = field(default=0)

    def __post_init__(self) -> None:
        if not self.total:
            self.total = max(self.bloco.count(b"\n") - 1, 0)

    def __contains__(self, palavra: str) -> bool:
        alvo = palavra.encode("utf-8")
        if not alvo or b"\n" in alvo:
            return False
        bloco = self.bloco
        inicio, fim = 0, len(bloco) - 1          # bloco[inicio] e bloco[fim] são "\n"
        while inicio < fim:
            meio = (inicio + fim) // 2
            a = bloco.rfind(b"\n", inicio, meio + 1)   # "\n" que abre a linha do meio
            b = bloco.find(b"\n", a + 1)
            if a < inicio or b < 0 or b > fim:
                return False
            linha = bloco[a + 1:b]
            if linha == alvo:
                return True
            if linha < alvo:
                inicio = b
            else:
                fim = a
            if fim - inicio <= 1:
                return False
        return False

    def __len__(self) -> int:
        return self.total
