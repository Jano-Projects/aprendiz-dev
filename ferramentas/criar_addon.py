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
      compreensao.json    interpretação de texto (Aprendiz 0.7+; veja aprendiz/recursos.py)
      lemas.tsv           formas → lemas, junto com compreensao.json
      vetores.bin         vetores de palavras (Aprendiz 0.7+)
      norma.json          norma da língua: grafias, equivalências e regras de gramática
                          (Aprendiz 0.8+; veja aprendiz/normas.py)
      vocabulario.tsv     todas as formas da norma, uma por linha, junto com norma.json
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

    Uma linha L: (Aprendiz 0.8+) diz a VARIEDADE do verbete: uma região
    dentro do país ou uma língua que convive com o português, declarada em
    "regiao.variedades" no manifesto:

        V: macaxeira
        L: nordeste
        T: mandioca
        R: **macaxeira** (Nordeste): mandioca.

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
from aprendiz import normas, recursos  # noqa: E402
from aprendiz.linguagem import normalizar  # noqa: E402

ARQUIVOS_ESPECIAIS = {"manifesto.json", "conhecimentos.json", "linguagem.json",
                      "parametros.json", "personalizacao.json", "compreensao.json",
                      "lemas.tsv", "perguntas.txt", "verbetes.txt", "leia-me.md", "readme.md",
                      "norma.json", "vocabulario.tsv"}


def ler_porque(texto: str, arquivo: str, numero: int) -> dict:
    """ "porque | o verbo concorda com o sujeito | -> concordancia" → dict do porquê."""
    partes = [p.strip() for p in texto.split("|")]
    liga = None
    if partes and partes[-1].startswith("->"):
        liga = partes.pop()[2:].strip() or None
    if not partes or not partes[0]:
        raise SystemExit(f"{arquivo}, linha {numero}: Q: precisa começar pela relação.")
    return {"relacao": partes[0], "texto": " | ".join(partes[1:]), "liga": liga}


def ler_perguntas(caminho: Path) -> list[dict]:
    """
    Lê blocos P:/V:/T:/R: separados por linha em branco.

        P: (ou V:)  a pergunta (ou o termo); linhas P:/V: a mais no MESMO
                    bloco viram "variacoes" (outros jeitos de perguntar)
        T:          traduções do verbete, separadas por vírgula
        L:          variedade do verbete (id declarado em regiao.variedades)
        R:          a resposta (pode continuar nas linhas seguintes)

    Teia de porquês (2.0), opcional, no mesmo bloco e ANTES do R::
        F:          ref do fragmento (id curto: "join-interno")
        A:          assuntos, separados por vírgula
        Q:          um porquê: "relação | explicação | -> ref ligado"
                    (a ligação é opcional; outro addon: "-> addon:ref")
        N: raiz     o fragmento é uma raiz (regra ou conceito de base)

    Dentro da resposta, um bloco de código entre linhas ``` é copiado como
    está: a indentação, as linhas em branco e as linhas com # (como
    #include ou um comentário do Python) são mantidas.
    """
    pares: list[dict] = []
    formas: list[str] = []
    traducoes: list[str] = []
    resposta: list[str] = []
    variedade = ""
    teia: dict = {}
    tipo = "pergunta"
    em_codigo = False   # dentro de um bloco ``` da resposta?

    def fechar():
        nonlocal formas, traducoes, resposta, variedade, teia
        if teia and not teia.get("ref"):
            raise SystemExit(f"{caminho.name}: bloco com A:/Q:/N: sem F: perto de {formas[:1]!r}")
        if formas and resposta:
            item = {"pergunta": formas[0], "conteudo": "\n".join(resposta).strip(), "tipo": tipo}
            if formas[1:]:
                item["variacoes"] = formas[1:]
            if traducoes:
                item["traducoes"] = traducoes
            if variedade:
                item["variedade"] = variedade
            if teia:
                item["teia"] = {"ref": teia["ref"], "assuntos": teia.get("assuntos", []),
                                "porques": teia.get("porques", []), "raiz": teia.get("raiz", False)}
            pares.append(item)
        elif formas or resposta or traducoes:
            raise SystemExit(f"{caminho.name}: bloco incompleto perto de "
                             f"{(formas or resposta or traducoes)[0]!r}")
        formas, traducoes, resposta, variedade, teia = [], [], [], "", {}

    for numero, linha in enumerate(caminho.read_text(encoding="utf-8").splitlines(), 1):
        if em_codigo:
            # Código: copiado como está, sem interpretar #, P:, R: ou linha em branco.
            resposta.append(linha.rstrip())
            em_codigo = linha.count("```") % 2 == 0
            continue
        prefixo = linha[:2].upper()
        if prefixo in ("F:", "A:", "Q:", "N:") and resposta:
            prefixo = ""   # a teia vem ANTES do R:; depois dele, é texto da resposta
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
        elif prefixo == "L:":
            variedade = linha[2:].strip()
        elif prefixo == "F:":
            teia["ref"] = linha[2:].strip()
        elif prefixo == "A:":
            teia.setdefault("assuntos", []).extend(
                a.strip() for a in linha[2:].split(",") if a.strip())
        elif prefixo == "N:":
            teia["raiz"] = linha[2:].strip().lower() == "raiz"
        elif prefixo == "Q:":
            teia.setdefault("porques", []).append(ler_porque(linha[2:], caminho.name, numero))
        elif prefixo == "R:":
            resposta = [linha[2:].strip()]
            em_codigo = resposta[0].count("```") % 2 == 1
        elif resposta:
            resposta.append(linha.strip())  # resposta com mais de uma linha
            em_codigo = linha.count("```") % 2 == 1
        else:
            raise SystemExit(f"{caminho.name}, linha {numero}: esperava 'P:', 'V:', 'T:', "
                             "'L:', 'F:', 'A:', 'Q:', 'N:' ou 'R:'.")
    if em_codigo:
        raise SystemExit(f"{caminho.name}: bloco de código (```) aberto e não fechado.")
    fechar()
    return pares


def criar(pasta: Path, saida: Path | None, junto: list[Path] | None = None) -> None:
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
    if manifesto.get("regiao") and not (pasta / "norma.json").exists():
        # norma.json e vocabulario.tsv são GERADOS (aprendiz-addons/ferramentas/dados_normas.py)
        # e não ficam no git: sem eles, o addon de idioma sai sem a norma do país.
        print(f"[AVISO] {pasta.name}: addon de idioma sem norma.json; gere com dados_normas.py.")
    if conhecimentos and not manifesto.get("recomendado"):
        teste = recomendar(conhecimentos, linguagem, [c.read_bytes() for c in junto or []])
        if teste:
            manifesto["recomendado"] = {k: teste[k] for k in ("busca", "resposta", "acerto")}
            acertos = "  ".join(f"{nome} {valor:.0%}" for nome, valor in teste["acertos"].items())
            print(f"     teste ({teste['perguntas']} perguntas): {acertos}")
            print(f"     recomendado: busca {teste['busca']} · resposta {teste['resposta']}")

    try:
        compreensao = json_opcional("compreensao.json")
        if compreensao is not None:
            compreensao = recursos.validar_compreensao(compreensao, normalizar)
        lemas = (recursos.validar_lemas((pasta / "lemas.tsv").read_bytes())
                 if (pasta / "lemas.tsv").exists() else None)
        vetores = (recursos.validar_vetores((pasta / "vetores.bin").read_bytes())
                   if (pasta / "vetores.bin").exists() else None)
        norma = json_opcional("norma.json")
        if norma is not None:
            normas.validar_norma(norma)          # erro com mensagem clara antes de empacotar
        vocabulario = ((pasta / "vocabulario.tsv").read_bytes()
                       if (pasta / "vocabulario.tsv").exists() else None)
        if vocabulario is not None:
            vocabulario = normas.validar_vocabulario(vocabulario)
        dados = criar_pacote(manifesto, conhecimentos, linguagem,
                             json_opcional("parametros.json"), json_opcional("personalizacao.json"),
                             compreensao, lemas, vetores, norma, vocabulario)
    except (ErroAddon, recursos.ErroRecurso, normas.ErroNorma) as erro:
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
    for secao, itens in p.compreensao.items():
        if itens:
            print(f"     compreensão · {secao}: {len(itens)}")
    if p.lemas:
        print(f"     lemas: {len(p.lemas)} palavras")
    if p.vetores:
        print(f"     vetores: {len(p.vetores.palavras)} palavras, {p.vetores.quantidade} vetores "
              f"de {p.vetores.dimensoes} dimensões")
    if p.norma:
        n = p.norma["norma"]
        print(f"     norma: {n['nome']} ({n['id']}) · ortografia {n['ortografia']} · "
              f"{len(p.norma['regras'])} regras · {len(p.norma['grafias'])} grafias · "
              f"{len(p.norma['equivalencias'])} equivalências · "
              f"{len(p.norma['erros_comuns'])} erros comuns · {len(p.norma['verbos'])} verbos")
    if p.vocabulario:
        print(f"     vocabulário: {len(normas.Vocabulario(p.vocabulario))} formas")
    print(f"     sha256: {p.hash}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria ou confere addons do Aprendiz.")
    parser.add_argument("caminho", type=Path, help="pasta-fonte (criar) ou arquivo .aprendiz (--conferir)")
    parser.add_argument("-o", "--saida", type=Path, help="arquivo .aprendiz a gerar")
    parser.add_argument("--conferir", action="store_true", help="só valida um .aprendiz pronto")
    parser.add_argument("--junto", type=Path, action="append", metavar="ARQ.aprendiz",
                        help="addon instalado antes no teste de recomendação (repita para "
                             "vários); use os essenciais de linguagem para medir como no uso real")
    args = parser.parse_args()
    if args.conferir:
        conferir(args.caminho)
    else:
        criar(args.caminho, args.saida, args.junto)


if __name__ == "__main__":
    main()
