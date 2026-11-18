"""
Addons: pacotes prontos, distribuídos em arquivos .aprendiz.

Um addon amplia o Aprendiz sem que o dono precise ensinar item a item:
alguém prepara um pacote ("Conversões de medidas", "Atalhos do Linux"…),
publica, e qualquer pessoa importa pelo app. O próprio app também EXPORTA
o que o dono ensinou como addon (veja core/exportacao.py).

O formato (versão 2)
--------------------
Um arquivo .aprendiz é um ZIP comum com arquivos JSON:

    manifesto.json       (obrigatório) quem é o addon e o que ele traz
    conhecimentos.json   classificação "memoria"        → perguntas e notas
    linguagem.json       classificação "linguagem"      → sinônimos e abreviações
    parametros.json      classificação "parametros"     → limiares, algoritmos padrão…
    personalizacao.json  classificação "personalizacao" → nome, cor, boas-vindas

    manifesto.json:
        {
          "formato": 2,
          "id": "conversoes-medidas",        ← letras minúsculas, números e hífen
          "nome": "Conversões de medidas",
          "versao": "1.1.0",
          "autor": "Jano Projects",
          "descricao": "Cozinha, distância, peso e temperatura.",
          "licenca": "CC-BY-4.0",
          "site": "https://exemplo.org/addons",           (opcional)
          "origem": "oficial",               ← "oficial" (Jano) ou "terceiros"
          "editor": "Jano Projects",                       (opcional)
          "classificacao": ["memoria", "linguagem"],
          "app": {"criado_com": "0.4.0", "versao_minima": "0.4.0"},
          "dependencias": [
            {"id": "atalhos-linux", "versao": "1.0.0", "nome": "Atalhos do Linux"}
          ],
          "recomendado": {"busca": "bm25", "resposta": "direta", "acerto": 0.97}
        }

    "recomendado" (opcional, Aprendiz 0.5+): o algoritmo de busca e o montador
    de resposta que funcionam melhor com este conteúdo, medidos por um teste
    com os próprios itens (veja core/recomendacao.py). O app mostra a
    recomendação ao instalar e agrupa addons que pedem o mesmo padrão.

    conhecimentos.json:
        [
          {"pergunta": "quantos ml tem uma xícara", "conteudo": "Cerca de 240 ml."},
          {"conteudo": "Um texto solto vira uma nota."},
          {"tipo": "verbete", "pergunta": "bué", "conteudo": "Muito, bastante."}
        ]

        "verbete" (Aprendiz 0.4.1+) é uma entrada de dicionário: só responde
        quando a pergunta é a palavra sozinha ou "o que significa <palavra>".
        Numa frase com outras palavras, é ignorado.

    linguagem.json (todas as chaves são opcionais):
        {"sinonimos":   {"chicara": "xicara"},
         "abreviacoes": {"pol": "polegada"},
         "stopwords":   ["significa", "significado"],          (Aprendiz 0.4.1+)
         "intencoes":   {"saudacao": ["e ai firmeza"]}}         (Aprendiz 0.4.1+)

    parametros.json / personalizacao.json:
        {"limiar.bm25": 0.6}  /  {"personalizacao.cor": "#0f766e"}
        Só chaves da lista fechada de aprendiz/configuracoes.py.

Classificação
-------------
Diz o que o addon MEXE no Aprendiz. Precisa bater com os arquivos presentes:

    memoria         alimenta a memória (conhecimentos)       ✔ aceito
    linguagem       amplia o banco de linguagem              ✔ aceito
    parametros      ajusta parâmetros dos algoritmos         ✔ aceito
    personalizacao  customiza nome, cor e boas-vindas        ✔ aceito
    algoritmo       habilita um novo algoritmo (código)      ✘ recusado
    aplicacao       modifica a aplicação (código)            ✘ recusado

Os dois últimos fazem parte do formato, mas o Aprendiz recusa qualquer
addon que traga código: só addons de dados são instalados.

Origem
------
"oficial" = publicado pela Jano Projects; "terceiros" = qualquer outra
pessoa (inclusive toda exportação feita pelo app). É uma DECLARAÇÃO do
arquivo: o app não tem como confirmar quem o publicou.

Formato 1
---------
Arquivos do formato 1 (manifesto sem origem/classificação/app) continuam
sendo lidos: a classificação é deduzida dos arquivos e a origem vira
"terceiros".

Segurança
---------
Addons vêm da internet, então são tratados como dados NÃO confiáveis:

  • Só contêm DADOS (JSON). Nada é executado — não existe código em addon.
  • Só lemos os nomes conhecidos de dentro do ZIP; nada é extraído para
    o disco (sem risco de "path traversal").
  • Há limites de tamanho do arquivo, do conteúdo descompactado (proteção
    contra "zip bombs") e de quantidade de itens.
  • Cada campo é validado e caracteres de controle são removidos.
  • Parâmetros e personalização só aceitam chaves de uma lista fechada.
  • Na interface, todo texto é exibido escapado (sem risco de HTML/JS).
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from typing import Any

from aprendiz import __version__
from aprendiz import configuracoes as cfg
from aprendiz.linguagem import normalizar
from aprendiz.memoria.sementes import INTENCOES

FORMATO = 2
FORMATOS_LIDOS = (1, 2)
EXTENSAO = ".aprendiz"

# Limites de segurança.
MAX_ARQUIVO = 50 * 1024 * 1024           # 50 MB compactado
MAX_DESCOMPACTADO = 200 * 1024 * 1024    # 200 MB somando os JSON
MAX_CONHECIMENTOS = 100_000
MAX_LINGUAGEM = 5_000                    # por tipo
MAX_CONTEUDO = 20_000                    # caracteres por conhecimento
MAX_PERGUNTA = 500
MAX_DEPENDENCIAS = 50

PADRAO_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
PADRAO_NOME_ALGORITMO = re.compile(r"^[a-z0-9_-]{1,30}$")
PADRAO_VERSAO = re.compile(r"^\d+(\.\d+){0,3}$")
_CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

CAMPOS_MANIFESTO = {  # campo: (obrigatório, tamanho máximo)
    "nome": (True, 80),
    "versao": (True, 20),
    "autor": (False, 80),
    "descricao": (False, 500),
    "licenca": (False, 40),
    "site": (False, 200),
    "editor": (False, 80),
    "criado_em": (False, 10),     # data AAAA-MM-DD em que o arquivo foi gerado
}

ORIGENS = {"oficial": "Oficial Jano", "terceiros": "Terceiros"}
EDITOR_OFICIAL = "Jano Projects"

# classificação → (título, arquivo, aceita nesta versão?)
CLASSIFICACOES: dict[str, tuple[str, str | None, bool]] = {
    "memoria": ("Alimenta a memória", "conhecimentos.json", True),
    "linguagem": ("Amplia a linguagem", "linguagem.json", True),
    "parametros": ("Ajusta parâmetros", "parametros.json", True),
    "personalizacao": ("Customiza a interface", "personalizacao.json", True),
    "algoritmo": ("Habilita um novo algoritmo", None, False),
    "aplicacao": ("Modifica a aplicação", None, False),
}


class ErroAddon(ValueError):
    """Arquivo de addon inválido. A mensagem é mostrada ao usuário."""


@dataclass
class Pacote:
    manifesto: dict[str, Any]
    conhecimentos: list[dict[str, Any]] = field(default_factory=list)
    linguagem: dict[str, dict[str, str]] = field(default_factory=dict)
    parametros: dict[str, Any] = field(default_factory=dict)
    personalizacao: dict[str, Any] = field(default_factory=dict)
    hash: str = ""

    @property
    def configuracoes(self) -> dict[str, Any]:
        """Parâmetros + personalização juntos (é assim que o banco guarda)."""
        return {**self.parametros, **self.personalizacao}


# ---------------------------------------------------------------- versões
def comparar_versoes(a: str, b: str) -> int:
    """-1 se a < b, 0 se iguais, 1 se a > b. "0.4" == "0.4.0"."""
    def partes(v: str) -> list[int]:
        numeros = [int(p) for p in re.findall(r"\d+", v or "0")[:4]]
        return numeros + [0] * (4 - len(numeros))
    pa, pb = partes(a), partes(b)
    return (pa > pb) - (pa < pb)


# ---------------------------------------------------------------- validação
def _limpar(texto: Any, maximo: int, campo: str) -> str:
    if not isinstance(texto, str):
        raise ErroAddon(f"O campo '{campo}' precisa ser texto.")
    texto = _CONTROLE.sub("", texto).strip()
    if len(texto) > maximo:
        raise ErroAddon(f"O campo '{campo}' passa de {maximo} caracteres.")
    return texto


def _versao(valor: Any, campo: str) -> str:
    valor = _limpar(valor, 20, campo)
    if not PADRAO_VERSAO.match(valor):
        raise ErroAddon(f"'{campo}' precisa ser uma versão como 1.0.0 (veio {valor!r}).")
    return valor


def _ler_json(zip_: zipfile.ZipFile, nome: str, obrigatorio: bool) -> Any:
    try:
        info = zip_.getinfo(nome)
    except KeyError:
        if obrigatorio:
            raise ErroAddon(f"O addon não tem o arquivo '{nome}'.") from None
        return None
    with zip_.open(info) as f:
        # Lemos no máximo o limite + 1 byte: se vier mais, o arquivo mentiu
        # sobre o próprio tamanho (ou é uma zip bomb).
        bruto = f.read(MAX_DESCOMPACTADO + 1)
    if len(bruto) > MAX_DESCOMPACTADO:
        raise ErroAddon("O conteúdo do addon é grande demais.")
    try:
        return json.loads(bruto.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as erro:
        raise ErroAddon(f"'{nome}' não é um JSON válido ({erro}).") from None


def validar_classificacao(bruto: Any) -> list[str]:
    if not isinstance(bruto, list) or not bruto:
        raise ErroAddon("A 'classificacao' precisa ser uma lista com pelo menos um tipo.")
    saida: list[str] = []
    for tipo in bruto:
        if tipo not in CLASSIFICACOES:
            raise ErroAddon(f"Classificação desconhecida: {tipo!r}. Tipos válidos: "
                            f"{', '.join(CLASSIFICACOES)}.")
        titulo, _, aceito = CLASSIFICACOES[tipo]
        if not aceito:
            raise ErroAddon(f"Este addon é do tipo \"{titulo}\" e traria código. Esta versão "
                            "do Aprendiz só aceita addons de dados (memória, linguagem, "
                            "parâmetros e personalização).")
        if tipo not in saida:
            saida.append(tipo)
    return saida


def validar_dependencias(bruto: Any) -> list[dict[str, Any]]:
    if bruto is None:
        return []
    if not isinstance(bruto, list) or len(bruto) > MAX_DEPENDENCIAS:
        raise ErroAddon(f"'dependencias' precisa ser uma lista de até {MAX_DEPENDENCIAS} itens.")
    saida = []
    for i, dep in enumerate(bruto, start=1):
        if not isinstance(dep, dict):
            raise ErroAddon(f"A dependência nº {i} precisa ser um objeto JSON.")
        id_ = dep.get("id")
        if not isinstance(id_, str) or not PADRAO_ID.match(id_):
            raise ErroAddon(f"A dependência nº {i} tem um 'id' inválido.")
        saida.append({
            "id": id_,
            "versao": _versao(dep.get("versao") or "0", f"dependencias[{i}].versao"),
            "nome": _limpar(dep.get("nome") or id_, 80, f"dependencias[{i}].nome"),
        })
    return saida


def validar_recomendado(bruto: Any) -> dict[str, Any] | None:
    """
    Algoritmos recomendados. Nomes desconhecidos NÃO são recusados (o addon
    pode ter sido feito numa versão com algoritmos novos): a tela de
    instalação avisa que aquele algoritmo não existe nesta versão.
    """
    if bruto is None:
        return None
    if not isinstance(bruto, dict):
        raise ErroAddon("'recomendado' precisa ser um objeto JSON.")
    saida: dict[str, Any] = {}
    for campo in ("busca", "resposta"):
        valor = bruto.get(campo)
        if not isinstance(valor, str) or not PADRAO_NOME_ALGORITMO.match(valor):
            raise ErroAddon(f"'recomendado.{campo}' precisa ser o nome de um algoritmo "
                            "(ex.: bm25, direta).")
        saida[campo] = valor
    acerto = bruto.get("acerto")
    if acerto is not None:
        if isinstance(acerto, bool) or not isinstance(acerto, (int, float)) or not 0 <= acerto <= 1:
            raise ErroAddon("'recomendado.acerto' precisa ser um número de 0 a 1.")
        saida["acerto"] = round(float(acerto), 3)
    return saida


def chave_de_grupo(manifesto: dict[str, Any], parametros: dict[str, Any] | None = None) -> str | None:
    """
    Addons que pedem o mesmo padrão de busca e resposta formam um GRUPO, que
    pode ser ativado de uma vez. A chave vem da recomendação do manifesto ou,
    se não houver, dos parâmetros busca.padrao/resposta.padrao que o addon traz.
    Addons só de personalização não entram em grupo (None).
    """
    rec = manifesto.get("recomendado") or {}
    parametros = parametros or {}
    busca = rec.get("busca") or parametros.get("busca.padrao")
    resposta = rec.get("resposta") or parametros.get("resposta.padrao")
    if not busca:
        return None
    return f"{busca}+{resposta or 'direta'}"


def validar_app(bruto: Any) -> dict[str, str | None]:
    if bruto is None:
        return {"criado_com": None, "versao_minima": None}
    if not isinstance(bruto, dict):
        raise ErroAddon("'app' precisa ser um objeto JSON.")
    saida: dict[str, str | None] = {}
    for campo in ("criado_com", "versao_minima"):
        valor = bruto.get(campo)
        saida[campo] = _versao(valor, f"app.{campo}") if valor else None
    return saida


def validar_manifesto(bruto: Any) -> dict[str, Any]:
    """
    Valida e NORMALIZA o manifesto: o resultado tem sempre os campos do
    formato 2, mesmo que o arquivo seja do formato 1.
    """
    if not isinstance(bruto, dict):
        raise ErroAddon("manifesto.json precisa ser um objeto JSON.")
    formato = bruto.get("formato")
    if formato not in FORMATOS_LIDOS:
        raise ErroAddon(f"Formato de addon não suportado: {formato!r} (esta versão do "
                        f"Aprendiz lê os formatos {', '.join(map(str, FORMATOS_LIDOS))}). "
                        "Talvez seja preciso atualizar o Aprendiz.")
    id_ = bruto.get("id")
    if not isinstance(id_, str) or not PADRAO_ID.match(id_):
        raise ErroAddon("O 'id' do addon deve ter de 2 a 63 caracteres: letras minúsculas, "
                        "números e hífen (ex.: conversoes-medidas).")
    manifesto: dict[str, Any] = {"formato": FORMATO, "id": id_}
    for campo, (obrigatorio, maximo) in CAMPOS_MANIFESTO.items():
        valor = bruto.get(campo)
        if valor is None or valor == "":
            if obrigatorio:
                raise ErroAddon(f"O manifesto precisa do campo '{campo}'.")
            manifesto[campo] = None
            continue
        manifesto[campo] = _limpar(valor, maximo, campo)
    if manifesto["site"] and not manifesto["site"].startswith(("https://", "http://")):
        raise ErroAddon("O 'site' do addon precisa começar com https://")

    if formato == 1:
        # Formato 1 não tinha esses campos: a classificação é deduzida depois,
        # pelos arquivos presentes (ver ler_pacote).
        manifesto.update(origem="terceiros", classificacao=None,
                         app={"criado_com": None, "versao_minima": None}, dependencias=[],
                         recomendado=None)
        return manifesto

    origem = bruto.get("origem", "terceiros")
    if origem not in ORIGENS:
        raise ErroAddon("A 'origem' precisa ser \"oficial\" ou \"terceiros\".")
    manifesto["origem"] = origem
    manifesto["classificacao"] = validar_classificacao(bruto.get("classificacao"))
    manifesto["app"] = validar_app(bruto.get("app"))
    manifesto["dependencias"] = validar_dependencias(bruto.get("dependencias"))
    manifesto["recomendado"] = validar_recomendado(bruto.get("recomendado"))
    if any(d["id"] == id_ for d in manifesto["dependencias"]):
        raise ErroAddon("Um addon não pode depender de si mesmo.")

    minima = manifesto["app"]["versao_minima"]
    if minima and comparar_versoes(minima, __version__) > 0:
        raise ErroAddon(f"Este addon precisa do Aprendiz {minima} ou mais novo "
                        f"(você está usando o {__version__}).")
    return manifesto


def validar_conhecimentos(bruto: Any) -> list[dict[str, Any]]:
    if not isinstance(bruto, list):
        raise ErroAddon("conhecimentos.json precisa ser uma lista.")
    if not bruto:
        raise ErroAddon("O addon não tem nenhum conhecimento.")
    if len(bruto) > MAX_CONHECIMENTOS:
        raise ErroAddon(f"O addon passa do limite de {MAX_CONHECIMENTOS} conhecimentos.")
    saida = []
    for i, item in enumerate(bruto, start=1):
        if not isinstance(item, dict):
            raise ErroAddon(f"O conhecimento nº {i} precisa ser um objeto JSON.")
        conteudo = _limpar(item.get("conteudo", ""), MAX_CONTEUDO, f"conteudo (nº {i})")
        if not conteudo:
            raise ErroAddon(f"O conhecimento nº {i} está sem 'conteudo'.")
        pergunta = item.get("pergunta")
        pergunta = _limpar(pergunta, MAX_PERGUNTA, f"pergunta (nº {i})") or None if pergunta else None
        tipo = item.get("tipo") or ("pergunta" if pergunta else "nota")
        if tipo not in ("pergunta", "nota", "trecho", "verbete"):
            raise ErroAddon(f"Tipo inválido no conhecimento nº {i}: {tipo!r}.")
        if tipo == "verbete" and not pergunta:
            raise ErroAddon(f"O verbete nº {i} precisa da palavra em 'pergunta'.")
        saida.append({"pergunta": pergunta, "conteudo": conteudo, "tipo": tipo})
    return saida


def validar_linguagem(bruto: Any) -> dict[str, dict[str, str]]:
    """
    Valida linguagem.json e devolve tudo no formato "termo → valor" usado pelo
    banco (tabela addon_linguagem):

        abreviacoes / sinonimos → termo → valor
        stopwords               → palavra → ""
        intencoes               → frase → nome da intenção
    """
    if bruto is None:
        return {}
    if not isinstance(bruto, dict):
        raise ErroAddon("linguagem.json precisa ser um objeto JSON.")
    saida: dict[str, dict[str, str]] = {}

    # Stopwords: palavras soltas que a BUSCA deve ignorar enquanto o addon
    # estiver ativo (ex.: "significa" num dicionário de gírias).
    palavras = bruto.get("stopwords") or []
    if not isinstance(palavras, list) or len(palavras) > MAX_LINGUAGEM:
        raise ErroAddon("'stopwords' em linguagem.json precisa ser uma lista de palavras.")
    limpas = {}
    for palavra in palavras:
        if not isinstance(palavra, str):
            raise ErroAddon("As stopwords precisam ser texto.")
        palavra = normalizar(palavra[:40])
        if " " in palavra:
            raise ErroAddon(f"Stopword deve ser uma palavra só: {palavra!r}.")
        if palavra:
            limpas[palavra] = ""
    if limpas:
        saida["stopwords"] = limpas

    # Intenções: frases de exemplo que treinam o classificador. Só as
    # intenções que o Aprendiz já conhece (saudação, despedida…).
    intencoes = bruto.get("intencoes") or {}
    if not isinstance(intencoes, dict):
        raise ErroAddon("'intencoes' em linguagem.json precisa ser um objeto JSON.")
    frases: dict[str, str] = {}
    for intencao, lista in intencoes.items():
        if intencao not in INTENCOES:
            raise ErroAddon(f"Intenção desconhecida: {intencao!r}. Válidas: "
                            f"{', '.join(INTENCOES)}.")
        if not isinstance(lista, list):
            raise ErroAddon(f"As frases da intenção '{intencao}' precisam estar numa lista.")
        for frase in lista:
            if not isinstance(frase, str):
                raise ErroAddon(f"As frases da intenção '{intencao}' precisam ser texto.")
            frase = normalizar(frase[:200])
            if frase:
                frases[frase] = intencao
    if len(frases) > MAX_LINGUAGEM:
        raise ErroAddon("'intencoes' em linguagem.json tem frases demais.")
    if frases:
        saida["intencoes"] = frases

    for tipo in ("abreviacoes", "sinonimos"):
        mapa = bruto.get(tipo) or {}
        if not isinstance(mapa, dict) or len(mapa) > MAX_LINGUAGEM:
            raise ErroAddon(f"'{tipo}' em linguagem.json é inválido ou grande demais.")
        limpo = {}
        for termo, valor in mapa.items():
            if not isinstance(termo, str) or not isinstance(valor, str):
                raise ErroAddon(f"Entradas de '{tipo}' precisam ser texto.")
            # Mesma normalização usada no banco de linguagem do dono.
            termo, valor = normalizar(termo[:80]), normalizar(valor[:200])
            if termo and valor:
                limpo[termo] = valor
        if limpo:
            saida[tipo] = limpo
    return saida


def validar_configuracoes(tipo: str, bruto: Any) -> dict[str, Any]:
    """parametros.json ou personalizacao.json: só chaves da lista fechada."""
    if bruto is None:
        return {}
    try:
        return cfg.validar_bloco(tipo, bruto)
    except ValueError as erro:
        raise ErroAddon(f"{tipo}.json inválido: {erro}.") from None


def classificacao_de(pacote: Pacote) -> list[str]:
    """Os tipos que os ARQUIVOS do pacote realmente trazem."""
    return [tipo for tipo, tem in (
        ("memoria", pacote.conhecimentos), ("linguagem", pacote.linguagem),
        ("parametros", pacote.parametros), ("personalizacao", pacote.personalizacao),
    ) if tem]


def ler_pacote(dados: bytes) -> Pacote:
    """Lê e valida um arquivo .aprendiz. Lança ErroAddon com mensagem amigável."""
    if len(dados) > MAX_ARQUIVO:
        raise ErroAddon("O arquivo é grande demais (limite de 50 MB).")
    try:
        zip_ = zipfile.ZipFile(io.BytesIO(dados))
    except zipfile.BadZipFile:
        raise ErroAddon("Este arquivo não é um addon do Aprendiz (.aprendiz).") from None
    with zip_:
        if sum(i.file_size for i in zip_.infolist()) > MAX_DESCOMPACTADO:
            raise ErroAddon("O conteúdo do addon é grande demais.")
        bruto = _ler_json(zip_, "manifesto.json", True)
        manifesto = validar_manifesto(bruto)
        v1 = bruto.get("formato") == 1
        brutos_k = _ler_json(zip_, "conhecimentos.json", v1)  # obrigatório só no formato 1
        pacote = Pacote(
            manifesto=manifesto,
            conhecimentos=validar_conhecimentos(brutos_k) if brutos_k is not None else [],
            linguagem=validar_linguagem(_ler_json(zip_, "linguagem.json", False)),
            parametros=validar_configuracoes(
                "parametros", None if v1 else _ler_json(zip_, "parametros.json", False)),
            personalizacao=validar_configuracoes(
                "personalizacao", None if v1 else _ler_json(zip_, "personalizacao.json", False)),
            hash=hashlib.sha256(dados).hexdigest(),
        )

    presentes = classificacao_de(pacote)
    if not presentes:
        raise ErroAddon("O addon está vazio: não traz conhecimentos, linguagem, "
                        "parâmetros nem personalização.")
    if v1:
        manifesto["classificacao"] = presentes
    else:
        # A classificação declarada precisa bater com o conteúdo: o usuário
        # decide se instala olhando para ela.
        declarada = set(manifesto["classificacao"])
        faltando = [CLASSIFICACOES[t][1] for t in declarada - set(presentes)]
        sobrando = [t for t in presentes if t not in declarada]
        if faltando:
            raise ErroAddon(f"A classificação promete conteúdo que não está no arquivo "
                            f"(falta {', '.join(sorted(faltando))}).")
        if sobrando:
            raise ErroAddon(f"O addon traz conteúdo que a classificação não declara: "
                            f"{', '.join(sobrando)}.")
    return pacote


def criar_pacote(manifesto: dict[str, Any], conhecimentos: list[dict[str, Any]] | None = None,
                 linguagem: dict[str, dict[str, str]] | None = None,
                 parametros: dict[str, Any] | None = None,
                 personalizacao: dict[str, Any] | None = None) -> bytes:
    """
    Gera os bytes de um arquivo .aprendiz (formato 2). Preenche o que der
    para deduzir (classificação, versão do app) e valida tudo com as mesmas
    regras da importação: um addon criado aqui sempre importa.
    """
    conhecimentos = conhecimentos or []
    linguagem = linguagem or {}
    parametros = parametros or {}
    personalizacao = personalizacao or {}
    provisorio = Pacote({}, conhecimentos, linguagem, parametros, personalizacao)
    manifesto = {
        "formato": FORMATO,
        "origem": "terceiros",
        "classificacao": classificacao_de(provisorio),
        "dependencias": [],
        **manifesto,
    }
    manifesto["app"] = {"criado_com": __version__, "versao_minima": __version__,
                        **(manifesto.get("app") or {})}

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zip_:
        def gravar(nome: str, dados: Any) -> None:
            zip_.writestr(nome, json.dumps(dados, ensure_ascii=False, indent=2))
        gravar("manifesto.json", {k: v for k, v in manifesto.items() if v is not None})
        if conhecimentos:
            gravar("conhecimentos.json", conhecimentos)
        if linguagem:
            gravar("linguagem.json", linguagem)
        if parametros:
            gravar("parametros.json", parametros)
        if personalizacao:
            gravar("personalizacao.json", personalizacao)
    dados = buffer.getvalue()
    ler_pacote(dados)  # garante que o que geramos é um addon válido
    return dados


def resumo(pacote: Pacote) -> dict[str, Any]:
    """O que a interface mostra ANTES de instalar (tela de confirmação)."""
    m = pacote.manifesto
    return {
        "manifesto": m,
        "origem_titulo": ORIGENS[m["origem"]],
        "classificacao": [{"tipo": t, "titulo": CLASSIFICACOES[t][0]}
                          for t in m["classificacao"]],
        "totais": {
            "conhecimentos": len(pacote.conhecimentos),
            "linguagem": sum(len(v) for v in pacote.linguagem.values()),
            "parametros": len(pacote.parametros),
            "personalizacao": len(pacote.personalizacao),
        },
        "configuracoes": [{"chave": k, "titulo": cfg.DEFINICOES[k].titulo, "valor": v}
                          for k, v in pacote.configuracoes.items()],
        "amostra": [k["pergunta"] or k["conteudo"][:80] for k in pacote.conhecimentos[:5]],
        "hash": pacote.hash,
    }


def dividir_em_trechos(texto: str, tamanho_maximo: int = 800) -> list[str]:
    """
    Divide um texto longo em "trechos" (por parágrafo), usados na busca.
    Parágrafos muito curtos são juntados; muito longos são cortados entre frases.
    Usado ao importar arquivos .txt/.md e ao criar addons a partir de textos.
    """
    paragrafos = [p.strip() for p in re.split(r"\n\s*\n", texto) if p.strip()]
    trechos: list[str] = []
    atual = ""
    for p in paragrafos:
        if len(atual) + len(p) < tamanho_maximo:
            atual = f"{atual}\n\n{p}".strip()
            continue
        if atual:
            trechos.append(atual)
        while len(p) > tamanho_maximo:
            corte = p.rfind(". ", 0, tamanho_maximo)
            corte = corte + 1 if corte > 0 else tamanho_maximo
            trechos.append(p[:corte].strip())
            p = p[corte:].strip()
        atual = p
    if atual:
        trechos.append(atual)
    return trechos
