"""
Recursos de compreensão: os arquivos que os addons "compreensao" e
"vetores" trazem (Aprendiz 0.7+), e a validação de cada um.

Tudo aqui continua sendo DADO: listas de palavras, frases-gatilho, textos e
números. O motor que usa esses dados está no app (core/compreensao.py e
linguagem/lexico.py); o addon nunca traz código, nem expressões regulares
(uma regex vinda de fora poderia travar o app com padrões patológicos).

compreensao.json  (classificação "compreensao")
-----------------------------------------------
    {
      "expressoes":  {"dar um jeito": "resolver", ...},
          → expressões de várias palavras trocadas por uma forma simples
            antes da busca (valem para a pergunta e para o que é indexado)

      "tipos_pergunta": [
          {"tipo": "definicao", "gatilhos": ["o que e", "o que significa"]}, ...],
          → reconhece o TIPO da pergunta (o que é / como fazer / onde...).
            Tipos válidos: os de TIPOS_PERGUNTA, abaixo.

      "autoconhecimento": [
          {"id": "versao", "perguntas": ["qual a sua versao"], "funcao": "versao"},
          {"id": "ia", "perguntas": ["voce e uma ia"], "resposta": "Sou..."}],
          → perguntas sobre o próprio Aprendiz. "funcao" = resposta calculada
            pelo app na hora (lista fechada FUNCOES); "resposta" = texto fixo.

      "fora_de_alcance": [
          {"tema": "internet", "gatilhos": ["pesquise na internet"], "resposta": "..."}],
          → pedidos que um assistente offline não tem como atender.

      "necessidades": [
          {"gatilhos": ["estou com fome"], "palavras": ["receita", "comida"]}],
          → o que a pessoa PRECISA quando fala de um jeito indireto; as
            palavras ajudam a recomendar um addon.

      "catalogo": [
          {"id": "conversoes-medidas", "nome": "Conversões de medidas",
           "descricao": "...", "palavras": ["xicara", "polegada", ...]}]
          → addons da loja oficial, para recomendar quando o Aprendiz não
            sabe responder. Gerado a partir do catálogo da loja.

      "dialogo": {                                                  (0.9+)
          "aberturas": {"bom dia": "Bom dia!", "ola": "Olá!"},
              → cumprimentos que podem ABRIR uma frase ("Olá, consegue me
                ajudar?"): são separados do resto e viram o começo da resposta
          "conversa": ["conseguir", "ajudar", "explicar", "coisa"],
              → palavras de conversa: sozinhas não são ASSUNTO, então não
                disparam a busca ("consegue me ajudar?" não procura "ajudar")
          "sem_assunto": ["Estou aqui! O que você quer saber?"],
              → resposta quando a mensagem só tem palavras de conversa
          "continuacoes": ["e em", "e no", "e o"],
              → "e em Portugal?" continua a pergunta anterior da conversa
          "atos": [
              {"id": "pedido-ajuda", "acao": "convidar",
               "gatilhos": ["consegue me ajudar"], "respostas": ["Claro! ..."],
               "sem_assunto": ["..."], "assunto_vago": ["Qual {assunto}?"]}]
                                                   (sem_assunto e assunto_vago: opcionais)
              → atos de fala: O QUE a pessoa faz com a frase (pede ajuda,
                desabafa, pede opinião, diz que não entendeu...). "acao" é
                de uma lista fechada (ACOES_DIALOGO, abaixo); nas respostas,
                {assunto} vira o assunto da mensagem. "assunto_vago" é para
                um assunto indefinido ("me ajuda com UMA gíria de Angola?"):
                o Aprendiz pergunta qual, em vez de chutar uma resposta.
      }

lemas.tsv  (opcional, junto com compreensao.json)
-------------------------------------------------
    Uma palavra por linha, já normalizada (minúsculas, sem acento):

        fui<TAB>ser          → forma flexionada e o seu lema
        carro                → palavra conhecida (sem lema diferente)

    O lema une formas que o radicalizador não une ("fui", "foi" → "ser";
    "fiz", "fez" → "fazer"). A lista inteira também serve de LÉXICO: uma
    palavra que existe no português não é "corrigida" como erro de digitação.

vetores.bin  (classificação "vetores")
--------------------------------------
    Vetores de palavras (significado aproximado: "carro" fica perto de
    "automóvel" e "moto"). Binário simples, little-endian:

        8 bytes   assinatura  b"APRVET1\\0"
        uint16    dimensões (D)
        uint32    quantidade de vetores (V)
        uint32    quantidade de palavras (P)
        uint32    tamanho do bloco de palavras em bytes (B)
        B bytes   palavras em UTF-8 separadas por "\\n" (P palavras)
        uint16×P  para cada palavra, o número do vetor que ela usa
        int8×V×D  os vetores (cada um com o maior valor absoluto em 127)

    Várias palavras podem usar o mesmo vetor (formas raras apontam para o
    vetor de uma palavra parecida). O tamanho do arquivo precisa bater
    exatamente com o cabeçalho.
"""

from __future__ import annotations

import json
import re
import struct
from dataclasses import dataclass, field
from typing import Any

ARQUIVO_COMPREENSAO = "compreensao.json"
ARQUIVO_LEMAS = "lemas.tsv"
ARQUIVO_VETORES = "vetores.bin"

ASSINATURA_VETORES = b"APRVET1\0"
_CABECALHO = struct.Struct("<8sHIII")

MAX_EXPRESSOES = 20_000
MAX_GATILHOS = 300                  # por item
MAX_ITENS = 2_000                   # por lista (tipos, autoconhecimento...)
MAX_CATALOGO = 1_000
MAX_PALAVRAS_ITEM = 600
MAX_TEXTO = 4_000
MAX_LEMAS = 1_500_000
MAX_VETORES = 65_535                # índice cabe em uint16
MAX_PALAVRAS_VETORES = 1_000_000
MAX_DIMENSOES = 512

_PALAVRA = re.compile(r"^[a-z]{1,40}$")
_FRASE = re.compile(r"^[a-z0-9]+( [a-z0-9]+){0,9}$")
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
_CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Tipos de pergunta que o app sabe usar (o addon diz COMO reconhecê-los).
TIPOS_PERGUNTA: dict[str, str] = {
    "definicao": "o que é",
    "procedimento": "como fazer",
    "localizacao": "onde fica",
    "tempo": "quando",
    "causa": "por que",
    "quantidade": "quanto",
    "pessoa": "quem",
    "escolha": "qual",
    "confirmacao": "se é verdade",
    "pedido": "um pedido",
}

# O que o app faz com cada ato de fala (o addon diz COMO reconhecê-los).
ACOES_DIALOGO: dict[str, str] = {
    "convidar": "pedido sem assunto: convida a dizer o que precisa; com assunto, segue para a busca",
    "responder": "responde com um dos textos (elogio, crítica, conversa)",
    "acolher": "responde com um dos textos mesmo que a frase continue (desabafo, estado de ânimo)",
    "crise": "sofrimento grave: responde antes de tudo, em qualquer posição da frase",
    "opinar": "pede opinião: diz que não tem opinião própria e mostra o que sabe do assunto",
    "refletir": "pergunta reflexiva ou abstrata: só responde se a base não tiver nada",
    "reformular": "'não entendi': mostra a resposta anterior de outro jeito (o texto inteiro)",
    "outras_opcoes": "'não era isso': mostra os outros candidatos da resposta anterior",
    "confirmar": "'sim': aceita o que a resposta anterior ofereceu (ex.: ativar um addon)",
    "negar": "'não': encerra o que a resposta anterior ofereceu",
}
MAX_RESPOSTAS = 20                  # textos por ato

# Respostas de autoconhecimento que o APP calcula na hora (lista fechada).
FUNCOES: dict[str, str] = {
    "versao": "nome e versão do Aprendiz",
    "addons": "addons instalados e ativos",
    "conhecimentos": "quanto o Aprendiz sabe",
    "algoritmos": "algoritmos de busca e resposta em uso",
    "capacidades": "o que o Aprendiz consegue fazer",
    "limitacoes": "o que o Aprendiz não faz",
    "privacidade": "onde ficam os dados",
    "hora": "hora atual",
    "data": "data de hoje",
    "recomendacoes": "addons da loja que ainda não estão instalados",
    "ensinar": "como ensinar o Aprendiz",
}


class ErroRecurso(ValueError):
    """Arquivo de recurso inválido (vira ErroAddon em addons.py)."""


# ---------------------------------------------------------------- utilidades
def _texto(valor: Any, maximo: int, campo: str) -> str:
    if not isinstance(valor, str):
        raise ErroRecurso(f"'{campo}' precisa ser texto.")
    valor = _CONTROLE.sub("", valor).strip()
    if not valor or len(valor) > maximo:
        raise ErroRecurso(f"'{campo}' precisa ter de 1 a {maximo} caracteres.")
    return valor


def _frase(valor: Any, campo: str, normalizar) -> str:
    """Frase-gatilho: normalizada pelo app e com no máximo 10 palavras."""
    if not isinstance(valor, str) or len(valor) > 200:
        raise ErroRecurso(f"'{campo}' precisa ser um texto curto.")
    frase = normalizar(valor)
    if not _FRASE.match(frase):
        raise ErroRecurso(f"'{campo}': {valor!r} precisa ter de 1 a 10 palavras.")
    return frase


def _lista(valor: Any, maximo: int, campo: str) -> list:
    if not isinstance(valor, list) or not valor or len(valor) > maximo:
        raise ErroRecurso(f"'{campo}' precisa ser uma lista com 1 a {maximo} itens.")
    return valor


def _frases(valor: Any, campo: str, normalizar) -> list[str]:
    saida: list[str] = []
    for i, item in enumerate(_lista(valor, MAX_GATILHOS, campo), start=1):
        frase = _frase(item, f"{campo}[{i}]", normalizar)
        if frase not in saida:
            saida.append(frase)
    return saida


def _palavras(valor: Any, campo: str, normalizar) -> list[str]:
    saida: list[str] = []
    for item in _lista(valor, MAX_PALAVRAS_ITEM, campo):
        if not isinstance(item, str):
            raise ErroRecurso(f"'{campo}' precisa ser uma lista de palavras.")
        for palavra in normalizar(item[:60]).split():
            if _PALAVRA.match(palavra) and palavra not in saida:
                saida.append(palavra)
    return saida


# ---------------------------------------------------------------- compreensao.json
def validar_compreensao(bruto: Any, normalizar) -> dict[str, Any]:
    """
    Valida compreensao.json e devolve tudo JÁ NORMALIZADO. `normalizar` é a
    função do app (recebida como parâmetro para não haver import circular).
    """
    if not isinstance(bruto, dict):
        raise ErroRecurso(f"{ARQUIVO_COMPREENSAO} precisa ser um objeto JSON.")
    conhecidas = {"expressoes", "tipos_pergunta", "autoconhecimento", "fora_de_alcance",
                  "necessidades", "catalogo", "dialogo"}
    sobrando = set(bruto) - conhecidas
    if sobrando:
        raise ErroRecurso(f"{ARQUIVO_COMPREENSAO} tem seções desconhecidas: "
                          f"{', '.join(sorted(sobrando))}.")
    # "dialogo" só entra na saída se vier no arquivo: assim um addon sem ele
    # continua sendo aceito pelas versões anteriores à 0.9.
    saida: dict[str, Any] = {k: [] for k in conhecidas - {"dialogo"}}
    saida["expressoes"] = {}

    expressoes = bruto.get("expressoes") or {}
    if not isinstance(expressoes, dict) or len(expressoes) > MAX_EXPRESSOES:
        raise ErroRecurso(f"'expressoes' precisa ser um objeto com até {MAX_EXPRESSOES} itens.")
    for de, para in expressoes.items():
        de = _frase(de, "expressoes", normalizar)
        para = _frase(para, f"expressoes[{de}]", normalizar)
        if " " not in de:
            raise ErroRecurso(f"A expressão {de!r} precisa ter duas palavras ou mais "
                              "(para uma palavra só, use sinônimos).")
        saida["expressoes"][de] = para

    for i, item in enumerate(bruto.get("tipos_pergunta") or [], start=1):
        campo = f"tipos_pergunta[{i}]"
        if not isinstance(item, dict) or item.get("tipo") not in TIPOS_PERGUNTA:
            raise ErroRecurso(f"'{campo}.tipo' precisa ser um destes: "
                              f"{', '.join(TIPOS_PERGUNTA)}.")
        saida["tipos_pergunta"].append(
            {"tipo": item["tipo"], "gatilhos": _frases(item.get("gatilhos"), f"{campo}.gatilhos",
                                                       normalizar)})

    ids: set[str] = set()
    for i, item in enumerate(bruto.get("autoconhecimento") or [], start=1):
        campo = f"autoconhecimento[{i}]"
        if not isinstance(item, dict):
            raise ErroRecurso(f"'{campo}' precisa ser um objeto JSON.")
        id_ = item.get("id")
        if not isinstance(id_, str) or not _ID.match(id_) or id_ in ids:
            raise ErroRecurso(f"'{campo}.id' precisa ser único (letras minúsculas, números e hífen).")
        ids.add(id_)
        funcao, resposta = item.get("funcao"), item.get("resposta")
        if (funcao is None) == (resposta is None):
            raise ErroRecurso(f"'{campo}' precisa de 'funcao' OU de 'resposta' (um dos dois).")
        if funcao is not None and funcao not in FUNCOES:
            raise ErroRecurso(f"'{campo}.funcao' desconhecida: {funcao!r}. Válidas: "
                              f"{', '.join(FUNCOES)}.")
        novo = {"id": id_, "perguntas": _frases(item.get("perguntas"), f"{campo}.perguntas",
                                                normalizar)}
        if funcao:
            novo["funcao"] = funcao
        else:
            novo["resposta"] = _texto(resposta, MAX_TEXTO, f"{campo}.resposta")
        saida["autoconhecimento"].append(novo)

    for i, item in enumerate(bruto.get("fora_de_alcance") or [], start=1):
        campo = f"fora_de_alcance[{i}]"
        if not isinstance(item, dict):
            raise ErroRecurso(f"'{campo}' precisa ser um objeto JSON.")
        saida["fora_de_alcance"].append({
            "tema": _texto(item.get("tema"), 60, f"{campo}.tema"),
            "gatilhos": _frases(item.get("gatilhos"), f"{campo}.gatilhos", normalizar),
            "resposta": _texto(item.get("resposta"), MAX_TEXTO, f"{campo}.resposta"),
        })

    for i, item in enumerate(bruto.get("necessidades") or [], start=1):
        campo = f"necessidades[{i}]"
        if not isinstance(item, dict):
            raise ErroRecurso(f"'{campo}' precisa ser um objeto JSON.")
        saida["necessidades"].append({
            "gatilhos": _frases(item.get("gatilhos"), f"{campo}.gatilhos", normalizar),
            "palavras": _palavras(item.get("palavras"), f"{campo}.palavras", normalizar),
        })

    catalogo = bruto.get("catalogo") or []
    if not isinstance(catalogo, list) or len(catalogo) > MAX_CATALOGO:
        raise ErroRecurso(f"'catalogo' precisa ser uma lista com até {MAX_CATALOGO} addons.")
    for i, item in enumerate(catalogo, start=1):
        campo = f"catalogo[{i}]"
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) \
                or not _ID.match(item["id"]):
            raise ErroRecurso(f"'{campo}.id' precisa ser o id de um addon.")
        saida["catalogo"].append({
            "id": item["id"],
            "nome": _texto(item.get("nome"), 80, f"{campo}.nome"),
            "descricao": _texto(item.get("descricao") or item.get("nome"), 600,
                                f"{campo}.descricao"),
            "palavras": _palavras(item.get("palavras"), f"{campo}.palavras", normalizar),
        })

    if bruto.get("dialogo"):
        saida["dialogo"] = validar_dialogo(bruto["dialogo"], normalizar)

    for lista in ("tipos_pergunta", "autoconhecimento", "fora_de_alcance", "necessidades"):
        if len(saida[lista]) > MAX_ITENS:
            raise ErroRecurso(f"'{lista}' passa do limite de {MAX_ITENS} itens.")
    if not any(saida.values()):
        raise ErroRecurso(f"{ARQUIVO_COMPREENSAO} está vazio.")
    return saida


def _textos(valor: Any, campo: str) -> list[str]:
    return [_texto(t, MAX_TEXTO, f"{campo}[{i}]")
            for i, t in enumerate(_lista(valor, MAX_RESPOSTAS, campo), start=1)]


def validar_dialogo(bruto: Any, normalizar) -> dict[str, Any]:
    """A seção "dialogo" do compreensao.json (atos de fala e contexto, 0.9+)."""
    if not isinstance(bruto, dict):
        raise ErroRecurso("'dialogo' precisa ser um objeto JSON.")
    conhecidas = {"aberturas", "conversa", "sem_assunto", "continuacoes", "atos"}
    sobrando = set(bruto) - conhecidas
    if sobrando:
        raise ErroRecurso(f"'dialogo' tem chaves desconhecidas: {', '.join(sorted(sobrando))}.")
    saida: dict[str, Any] = {"aberturas": {}, "conversa": [], "sem_assunto": [],
                             "continuacoes": [], "atos": []}

    aberturas = bruto.get("aberturas") or {}
    if not isinstance(aberturas, dict) or len(aberturas) > MAX_ITENS:
        raise ErroRecurso(f"'dialogo.aberturas' precisa ser um objeto com até {MAX_ITENS} itens.")
    for frase, resposta in aberturas.items():
        saida["aberturas"][_frase(frase, "dialogo.aberturas", normalizar)] = \
            _texto(resposta, 120, f"dialogo.aberturas[{frase}]")

    if bruto.get("conversa") is not None:
        saida["conversa"] = _palavras(bruto["conversa"], "dialogo.conversa", normalizar)
    if bruto.get("sem_assunto") is not None:
        saida["sem_assunto"] = _textos(bruto["sem_assunto"], "dialogo.sem_assunto")
    if bruto.get("continuacoes") is not None:
        saida["continuacoes"] = _frases(bruto["continuacoes"], "dialogo.continuacoes", normalizar)

    ids: set[str] = set()
    atos = bruto.get("atos") or []
    if not isinstance(atos, list) or len(atos) > MAX_ITENS:
        raise ErroRecurso(f"'dialogo.atos' precisa ser uma lista com até {MAX_ITENS} itens.")
    for i, item in enumerate(atos, start=1):
        campo = f"dialogo.atos[{i}]"
        if not isinstance(item, dict):
            raise ErroRecurso(f"'{campo}' precisa ser um objeto JSON.")
        id_ = item.get("id")
        if not isinstance(id_, str) or not _ID.match(id_) or id_ in ids:
            raise ErroRecurso(f"'{campo}.id' precisa ser único (letras minúsculas, números e hífen).")
        ids.add(id_)
        if item.get("acao") not in ACOES_DIALOGO:
            raise ErroRecurso(f"'{campo}.acao' precisa ser uma destas: {', '.join(ACOES_DIALOGO)}.")
        novo = {"id": id_, "acao": item["acao"],
                "gatilhos": _frases(item.get("gatilhos"), f"{campo}.gatilhos", normalizar),
                "respostas": _textos(item.get("respostas"), f"{campo}.respostas")}
        for opcional in ("sem_assunto", "assunto_vago"):
            if item.get(opcional) is not None:
                novo[opcional] = _textos(item[opcional], f"{campo}.{opcional}")
        saida["atos"].append(novo)
    if not any(saida.values()):
        raise ErroRecurso("'dialogo' está vazio.")
    return saida


# ---------------------------------------------------------------- lemas.tsv
def validar_lemas(bruto: bytes) -> list[tuple[str, str]]:
    """
    lemas.tsv → [(palavra, lema)], com lema "" quando a palavra não tem lema
    diferente dela mesma. Só aceita palavras já normalizadas (a-z).
    """
    try:
        texto = bruto.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ErroRecurso(f"{ARQUIVO_LEMAS} precisa estar em UTF-8.") from None
    saida: dict[str, str] = {}
    for n, linha in enumerate(texto.splitlines(), start=1):
        if not linha or linha.startswith("#"):
            continue
        palavra, _, lema = linha.partition("\t")
        if not _PALAVRA.match(palavra) or (lema and not _PALAVRA.match(lema)):
            raise ErroRecurso(f"{ARQUIVO_LEMAS}, linha {n}: use só letras minúsculas sem "
                              "acento, no formato palavra<TAB>lema.")
        saida[palavra] = "" if lema == palavra else lema
        if len(saida) > MAX_LEMAS:
            raise ErroRecurso(f"{ARQUIVO_LEMAS} passa do limite de {MAX_LEMAS} palavras.")
    if not saida:
        raise ErroRecurso(f"{ARQUIVO_LEMAS} está vazio.")
    return list(saida.items())


# ---------------------------------------------------------------- vetores.bin
@dataclass
class Vetores:
    """Vetores de palavras lidos de um vetores.bin (já validados)."""

    dimensoes: int
    quantidade: int
    palavras: list[tuple[str, int]] = field(default_factory=list)  # (palavra, nº do vetor)
    dados: bytes = b""                                              # int8 × V × D

    def como_bytes(self) -> bytes:
        """Gera o arquivo vetores.bin (usado pela ferramenta que cria o addon)."""
        bloco = "\n".join(p for p, _ in self.palavras).encode("utf-8")
        return (_CABECALHO.pack(ASSINATURA_VETORES, self.dimensoes, self.quantidade,
                                len(self.palavras), len(bloco))
                + bloco + struct.pack(f"<{len(self.palavras)}H", *(i for _, i in self.palavras))
                + self.dados)


def validar_vetores(bruto: bytes) -> Vetores:
    erro = f"{ARQUIVO_VETORES} está corrompido ou não é um arquivo de vetores do Aprendiz."
    if len(bruto) < _CABECALHO.size:
        raise ErroRecurso(erro)
    assinatura, d, v, p, b = _CABECALHO.unpack_from(bruto)
    if assinatura != ASSINATURA_VETORES:
        raise ErroRecurso(erro)
    if not (8 <= d <= MAX_DIMENSOES and 1 <= v <= MAX_VETORES and 1 <= p <= MAX_PALAVRAS_VETORES):
        raise ErroRecurso(f"{ARQUIVO_VETORES}: tamanhos fora dos limites.")
    esperado = _CABECALHO.size + b + 2 * p + v * d
    if len(bruto) != esperado:
        raise ErroRecurso(erro)
    inicio = _CABECALHO.size
    try:
        palavras = bruto[inicio:inicio + b].decode("utf-8").split("\n")
    except UnicodeDecodeError:
        raise ErroRecurso(erro) from None
    if len(palavras) != p:
        raise ErroRecurso(erro)
    indices = struct.unpack_from(f"<{p}H", bruto, inicio + b)
    vistos: set[str] = set()
    pares: list[tuple[str, int]] = []
    for palavra, indice in zip(palavras, indices):
        if not _PALAVRA.match(palavra) or indice >= v or palavra in vistos:
            raise ErroRecurso(f"{ARQUIVO_VETORES}: palavra ou índice inválido ({palavra!r}).")
        vistos.add(palavra)
        pares.append((palavra, indice))
    return Vetores(dimensoes=d, quantidade=v, palavras=pares,
                   dados=bytes(bruto[inicio + b + 2 * p:]))


def compreensao_como_json(dados: dict[str, Any]) -> str:
    return json.dumps(dados, ensure_ascii=False)
