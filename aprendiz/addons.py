"""
Addons: pacotes de conhecimento prontos, distribuídos em arquivos .aprendiz.

Um addon amplia o que o Aprendiz sabe sem que o dono precise ensinar item a
item: alguém prepara um pacote ("Conversões de medidas", "Atalhos do Linux"…),
publica, e qualquer pessoa importa pelo app.

O formato
---------
Um arquivo .aprendiz é um ZIP comum com até três arquivos JSON:

    manifesto.json      (obrigatório) quem é o addon
    conhecimentos.json  (obrigatório) a lista de conhecimentos
    linguagem.json      (opcional)    sinônimos e abreviações extras

    manifesto.json:
        {
          "formato": 1,
          "id": "conversoes-medidas",        ← letras minúsculas, números e hífen
          "nome": "Conversões de medidas",
          "versao": "1.0.0",
          "autor": "Fulano",
          "descricao": "Cozinha, distância, peso e temperatura.",
          "licenca": "CC-BY-4.0",
          "site": "https://exemplo.org/addons"   (opcional)
        }

    conhecimentos.json:
        [
          {"pergunta": "quantos ml tem uma xícara", "conteudo": "Cerca de 240 ml."},
          {"conteudo": "Um texto solto vira uma nota."}
        ]

    linguagem.json:
        {"sinonimos": {"chicara": "xicara"}, "abreviacoes": {"pol": "polegada"}}

Segurança
---------
Addons vêm da internet, então são tratados como dados NÃO confiáveis:

  • Só contêm DADOS (JSON). Nada é executado — não existe código em addon.
  • Só lemos os três nomes conhecidos de dentro do ZIP; nada é extraído para
    o disco (sem risco de "path traversal").
  • Há limites de tamanho do arquivo, do conteúdo descompactado (proteção
    contra "zip bombs") e de quantidade de itens.
  • Cada campo é validado e caracteres de controle são removidos.
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

from aprendiz.linguagem import normalizar

FORMATO = 1
EXTENSAO = ".aprendiz"

# Limites de segurança.
MAX_ARQUIVO = 50 * 1024 * 1024           # 50 MB compactado
MAX_DESCOMPACTADO = 200 * 1024 * 1024    # 200 MB somando os JSON
MAX_CONHECIMENTOS = 100_000
MAX_LINGUAGEM = 5_000                    # por tipo
MAX_CONTEUDO = 20_000                    # caracteres por conhecimento
MAX_PERGUNTA = 500

PADRAO_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
_CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

CAMPOS_MANIFESTO = {  # campo: (obrigatório, tamanho máximo)
    "nome": (True, 80),
    "versao": (True, 20),
    "autor": (False, 80),
    "descricao": (False, 500),
    "licenca": (False, 40),
    "site": (False, 200),
}


class ErroAddon(ValueError):
    """Arquivo de addon inválido. A mensagem é mostrada ao usuário."""


@dataclass
class Pacote:
    manifesto: dict[str, Any]
    conhecimentos: list[dict[str, Any]]
    linguagem: dict[str, dict[str, str]] = field(default_factory=dict)
    hash: str = ""


def _limpar(texto: Any, maximo: int, campo: str) -> str:
    if not isinstance(texto, str):
        raise ErroAddon(f"O campo '{campo}' precisa ser texto.")
    texto = _CONTROLE.sub("", texto).strip()
    if len(texto) > maximo:
        raise ErroAddon(f"O campo '{campo}' passa de {maximo} caracteres.")
    return texto


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


def validar_manifesto(bruto: Any) -> dict[str, Any]:
    if not isinstance(bruto, dict):
        raise ErroAddon("manifesto.json precisa ser um objeto JSON.")
    if bruto.get("formato") != FORMATO:
        raise ErroAddon(f"Formato de addon não suportado: {bruto.get('formato')!r} "
                        f"(esta versão do Aprendiz lê o formato {FORMATO}).")
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
        if tipo not in ("pergunta", "nota", "trecho"):
            raise ErroAddon(f"Tipo inválido no conhecimento nº {i}: {tipo!r}.")
        saida.append({"pergunta": pergunta, "conteudo": conteudo, "tipo": tipo})
    return saida


def validar_linguagem(bruto: Any) -> dict[str, dict[str, str]]:
    if bruto is None:
        return {}
    if not isinstance(bruto, dict):
        raise ErroAddon("linguagem.json precisa ser um objeto JSON.")
    saida: dict[str, dict[str, str]] = {}
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
        manifesto = validar_manifesto(_ler_json(zip_, "manifesto.json", True))
        conhecimentos = validar_conhecimentos(_ler_json(zip_, "conhecimentos.json", True))
        linguagem = validar_linguagem(_ler_json(zip_, "linguagem.json", False))
    return Pacote(manifesto, conhecimentos, linguagem, hashlib.sha256(dados).hexdigest())


def criar_pacote(manifesto: dict[str, Any], conhecimentos: list[dict[str, Any]],
                 linguagem: dict[str, dict[str, str]] | None = None) -> bytes:
    """
    Gera os bytes de um arquivo .aprendiz. Valida tudo antes, com as mesmas
    regras usadas na importação: um addon criado aqui sempre importa.
    """
    manifesto = {"formato": FORMATO, **manifesto}
    validar_manifesto(manifesto)
    validar_conhecimentos(conhecimentos)
    validar_linguagem(linguagem)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zip_:
        def gravar(nome: str, dados: Any) -> None:
            zip_.writestr(nome, json.dumps(dados, ensure_ascii=False, indent=2))
        gravar("manifesto.json", manifesto)
        gravar("conhecimentos.json", conhecimentos)
        if linguagem:
            gravar("linguagem.json", linguagem)
    return buffer.getvalue()


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
