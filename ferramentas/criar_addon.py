"""
Cria (ou confere) um addon do Aprendiz — um arquivo .aprendiz.

CRIAR a partir de uma pasta-fonte:

    python ferramentas/criar_addon.py exemplos/addons/conversoes-medidas

    A pasta pode ter:
      manifesto.json      (obrigatório) id, nome, versao, autor, descricao, licenca, site,
                          origem ("oficial" só para a Jano Projects; o padrão é "terceiros"),
                          editor, dependencias, app.versao_minima
      perguntas.txt       pares no formato abaixo (o jeito mais fácil de escrever)
      verbetes.txt        dicionário: blocos V:/R: (veja abaixo)
      conhecimentos.json  lista [{"pergunta": "...", "conteudo": "..."}] (para quem gera por programa)
      linguagem.json      {"sinonimos": {...}, "abreviacoes": {...}}
      parametros.json     {"limiar.bm25": 0.6, ...}         (chaves de aprendiz/configuracoes.py)
      personalizacao.json {"personalizacao.cor": "#0f766e", ...}
      *.md / *.txt        textos livres, divididos automaticamente em trechos

    A "classificacao" e o "app.criado_com" são preenchidos sozinhos a partir
    do conteúdo e da versão do Aprendiz que gerou o arquivo (formato 2).

    O "recomendado" (melhor busca e melhor resposta) também: a ferramenta
    testa os quatro algoritmos de busca com os próprios itens e mostra o
    resultado. Para fixar outra escolha, escreva no manifesto.json:
        "recomendado": {"busca": "hibrido", "resposta": "extrativa"}

    Formato do perguntas.txt (blocos separados por linha em branco):

        P: quantos ml tem uma xícara
        R: Uma xícara de chá tem cerca de 240 ml.

        P: quanto vale uma polegada
        P: 1 polegada tem quantos centímetros
        P: converter polegada para cm
        R: 1 polegada = 2,54 cm.

    Várias linhas P: no mesmo bloco são VARIAÇÕES: jeitos diferentes de
    perguntar a mesma coisa, que levam à mesma resposta (Aprendiz 0.6+).
    Linhas começando com # são comentários.

    Dicionários (gírias, termos regionais) usam "V:" no lugar de "P:". Cada
    bloco vira um VERBETE, que só responde quando a pessoa digita a palavra
    sozinha ou pergunta "o que significa <palavra>" (Aprendiz 0.4.1+):

        V: bué
        V: bue
        T: muito, bastante
        R: Muito, bastante. Ex.: "Gostei bué."

    Linhas V: a mais são outras grafias do termo; a linha T: traz o
    equivalente em português padrão, para a busca inversa ("como se diz
    muito em Angola?"). No manifesto.json do dicionário, declare a região:
        "regiao": {"nome": "Angola", "termos": ["angola", "angolano", "angolanos"]}

    Num dicionário, coloque em linguagem.json as stopwords "significa",
    "significado", "quer" e "dizer" (veja os addons de gírias da loja).

CONFERIR um addon pronto (o mesmo teste que o app faz ao importar):

    python ferramentas/criar_addon.py --conferir conversoes-medidas.aprendiz
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aprendiz.core.recomendacao import recomendar  # noqa: E402

from aprendiz.addons import (  # noqa: E402
    EXTENSAO, ORIGENS, ErroAddon, criar_pacote, dividir_em_trechos, ler_pacote,
)

ARQUIVOS_ESPECIAIS = {"manifesto.json", "conhecimentos.json", "linguagem.json",
                      "parametros.json", "personalizacao.json",
                      "perguntas.txt", "verbetes.txt", "leia-me.md", "readme.md"}


def ler_perguntas(caminho: Path) -> list[dict]:
    """
    Lê blocos P:/V:/T:/R: separados por linha em branco.

        P: (ou V:)  a pergunta (ou o termo); linhas P:/V: a mais no MESMO
                    bloco viram "variacoes" (outros jeitos de perguntar)
        T:          traduções do verbete, separadas por vírgula
        R:          a resposta (pode continuar nas linhas seguintes)
    """
    pares: list[dict] = []
    formas: list[str] = []
    traducoes: list[str] = []
    resposta: list[str] = []
    tipo = "pergunta"

    def fechar():
        nonlocal formas, traducoes, resposta
        if formas and resposta:
            item = {"pergunta": formas[0], "conteudo": "\n".join(resposta).strip(), "tipo": tipo}
            if formas[1:]:
                item["variacoes"] = formas[1:]
            if traducoes:
                item["traducoes"] = traducoes
            pares.append(item)
        elif formas or resposta or traducoes:
            raise SystemExit(f"{caminho.name}: bloco incompleto perto de "
                             f"{(formas or resposta or traducoes)[0]!r}")
        formas, traducoes, resposta = [], [], []

    for numero, linha in enumerate(caminho.read_text(encoding="utf-8").splitlines(), 1):
        prefixo = linha[:2].upper()
        if linha.lstrip().startswith("#"):
            continue
        if not linha.strip():
            fechar()
        elif prefixo in ("P:", "V:"):
            if resposta:          # P: depois de R: sem linha em branco = novo bloco
                fechar()
            if not formas:
                tipo = "verbete" if prefixo == "V:" else "pergunta"
            formas.append(linha[2:].strip())
        elif prefixo == "T:":
            traducoes += [t.strip() for t in linha[2:].split(",") if t.strip()]
        elif prefixo == "R:":
            resposta = [linha[2:].strip()]
        elif resposta:
            resposta.append(linha.strip())  # resposta com mais de uma linha
        else:
            raise SystemExit(f"{caminho.name}, linha {numero}: esperava 'P:', 'V:', 'T:' ou 'R:'.")
    fechar()
    return pares


def criar(pasta: Path, saida: Path | None) -> None:
    manifesto_arq = pasta / "manifesto.json"
    if not manifesto_arq.exists():
        raise SystemExit(f"Falta {manifesto_arq}")
    manifesto = json.loads(manifesto_arq.read_text(encoding="utf-8"))
    manifesto.pop("formato", None)
    manifesto.pop("classificacao", None)  # sempre recalculada a partir dos arquivos

    conhecimentos: list[dict] = []
    for nome in ("perguntas.txt", "verbetes.txt"):  # mesmo formato; P: e V: valem nos dois
        if (pasta / nome).exists():
            conhecimentos += ler_perguntas(pasta / nome)
    if (pasta / "conhecimentos.json").exists():
        conhecimentos += json.loads((pasta / "conhecimentos.json").read_text(encoding="utf-8"))
    for arquivo in sorted(pasta.iterdir()):
        if arquivo.suffix.lower() in (".md", ".txt") and arquivo.name.lower() not in ARQUIVOS_ESPECIAIS:
            for trecho in dividir_em_trechos(arquivo.read_text(encoding="utf-8")):
                conhecimentos.append({"conteudo": trecho, "tipo": "trecho"})

    def json_opcional(nome: str):
        arquivo = pasta / nome
        return json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else None

    linguagem = json_opcional("linguagem.json")
    if conhecimentos and not manifesto.get("recomendado"):
        teste = recomendar(conhecimentos, linguagem)
        if teste:
            manifesto["recomendado"] = {k: teste[k] for k in ("busca", "resposta", "acerto")}
            acertos = "  ".join(f"{nome} {valor:.0%}" for nome, valor in teste["acertos"].items())
            print(f"     teste ({teste['perguntas']} perguntas): {acertos}")
            print(f"     recomendado: busca {teste['busca']} · resposta {teste['resposta']}")

    try:
        dados = criar_pacote(manifesto, conhecimentos, linguagem,
                             json_opcional("parametros.json"), json_opcional("personalizacao.json"))
    except ErroAddon as erro:
        raise SystemExit(f"Addon inválido: {erro}")

    saida = saida or pasta.parent / f"{manifesto['id']}{EXTENSAO}"
    saida.write_bytes(dados)
    print(f"[OK] {saida}  ({len(conhecimentos)} conhecimentos, {len(dados) / 1024:.1f} KB)")


def conferir(arquivo: Path) -> None:
    try:
        p = ler_pacote(arquivo.read_bytes())
    except ErroAddon as erro:
        raise SystemExit(f"[X] {arquivo.name}: {erro}")
    m = p.manifesto
    tipos: dict[str, int] = {}
    for k in p.conhecimentos:
        tipos[k["tipo"]] = tipos.get(k["tipo"], 0) + 1
    print(f"[OK] {m['nome']} {m['versao']}  (id: {m['id']})")
    print(f"     origem: {ORIGENS[m['origem']]}" + (f" · editor: {m['editor']}" if m.get("editor") else ""))
    print(f"     classificação: {', '.join(m['classificacao'])}")
    print(f"     autor: {m.get('autor') or '-'} · licença: {m.get('licenca') or '-'}")
    app = m["app"]
    print(f"     app: criado com {app['criado_com'] or '?'} · exige {app['versao_minima'] or '-'}")
    if m.get("recomendado"):
        r = m["recomendado"]
        acerto = f" (acerto {r['acerto']:.0%} no teste)" if r.get("acerto") is not None else ""
        print(f"     recomendado: busca {r['busca']} · resposta {r['resposta']}{acerto}")
    for dep in m["dependencias"]:
        print(f"     depende de: {dep['nome']} ({dep['id']}) {dep['versao']}")
    print(f"     conhecimentos: {len(p.conhecimentos)} {tipos}")
    for tipo, mapa in p.linguagem.items():
        print(f"     {tipo}: {len(mapa)}")
    for chave, valor in p.configuracoes.items():
        print(f"     {chave} = {valor}")
    print(f"     sha256: {p.hash}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria ou confere addons do Aprendiz.")
    parser.add_argument("caminho", type=Path, help="pasta-fonte (criar) ou arquivo .aprendiz (--conferir)")
    parser.add_argument("-o", "--saida", type=Path, help="arquivo .aprendiz a gerar")
    parser.add_argument("--conferir", action="store_true", help="só valida um .aprendiz pronto")
    args = parser.parse_args()
    if args.conferir:
        conferir(args.caminho)
    else:
        criar(args.caminho, args.saida)


if __name__ == "__main__":
    main()
