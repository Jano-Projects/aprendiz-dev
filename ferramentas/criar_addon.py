"""
Cria (ou confere) um addon do Aprendiz — um arquivo .aprendiz.

CRIAR a partir de uma pasta-fonte:

    python ferramentas/criar_addon.py exemplos/addons/conversoes-medidas

    A pasta pode ter:
      manifesto.json      (obrigatório) id, nome, versao, autor, descricao, licenca, site
      perguntas.txt       pares no formato abaixo (o jeito mais fácil de escrever)
      conhecimentos.json  lista [{"pergunta": "...", "conteudo": "..."}] (para quem gera por programa)
      linguagem.json      {"sinonimos": {...}, "abreviacoes": {...}}
      *.md / *.txt        textos livres, divididos automaticamente em trechos

    Formato do perguntas.txt (blocos separados por linha em branco):

        P: quantos ml tem uma xícara
        R: Uma xícara de chá tem cerca de 240 ml.

        P: quanto vale uma polegada
        R: 1 polegada = 2,54 cm.

    Linhas começando com # são comentários.

CONFERIR um addon pronto (o mesmo teste que o app faz ao importar):

    python ferramentas/criar_addon.py --conferir conversoes-medidas.aprendiz
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aprendiz.addons import (  # noqa: E402
    EXTENSAO, ErroAddon, criar_pacote, dividir_em_trechos, ler_pacote,
)

ARQUIVOS_ESPECIAIS = {"manifesto.json", "conhecimentos.json", "linguagem.json",
                      "perguntas.txt", "leia-me.md", "readme.md"}


def ler_perguntas(caminho: Path) -> list[dict]:
    pares, pergunta, resposta = [], None, []
    def fechar():
        nonlocal pergunta, resposta
        if pergunta and resposta:
            pares.append({"pergunta": pergunta, "conteudo": "\n".join(resposta).strip()})
        elif pergunta or resposta:
            raise SystemExit(f"{caminho.name}: bloco incompleto perto de {pergunta or resposta!r}")
        pergunta, resposta = None, []

    for numero, linha in enumerate(caminho.read_text(encoding="utf-8").splitlines(), 1):
        if linha.lstrip().startswith("#"):
            continue
        if not linha.strip():
            fechar()
        elif linha[:2].upper() == "P:":
            fechar()
            pergunta = linha[2:].strip()
        elif linha[:2].upper() == "R:":
            resposta = [linha[2:].strip()]
        elif resposta:
            resposta.append(linha.strip())  # resposta com mais de uma linha
        else:
            raise SystemExit(f"{caminho.name}, linha {numero}: esperava 'P:' ou 'R:'.")
    fechar()
    return pares


def criar(pasta: Path, saida: Path | None) -> None:
    manifesto_arq = pasta / "manifesto.json"
    if not manifesto_arq.exists():
        raise SystemExit(f"Falta {manifesto_arq}")
    manifesto = json.loads(manifesto_arq.read_text(encoding="utf-8"))
    manifesto.pop("formato", None)

    conhecimentos: list[dict] = []
    if (pasta / "perguntas.txt").exists():
        conhecimentos += ler_perguntas(pasta / "perguntas.txt")
    if (pasta / "conhecimentos.json").exists():
        conhecimentos += json.loads((pasta / "conhecimentos.json").read_text(encoding="utf-8"))
    for arquivo in sorted(pasta.iterdir()):
        if arquivo.suffix.lower() in (".md", ".txt") and arquivo.name.lower() not in ARQUIVOS_ESPECIAIS:
            for trecho in dividir_em_trechos(arquivo.read_text(encoding="utf-8")):
                conhecimentos.append({"conteudo": trecho, "tipo": "trecho"})

    linguagem = None
    if (pasta / "linguagem.json").exists():
        linguagem = json.loads((pasta / "linguagem.json").read_text(encoding="utf-8"))

    try:
        dados = criar_pacote(manifesto, conhecimentos, linguagem)
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
    print(f"     autor: {m.get('autor') or '-'} · licença: {m.get('licenca') or '-'}")
    print(f"     conhecimentos: {len(p.conhecimentos)} {tipos}")
    for tipo, mapa in p.linguagem.items():
        print(f"     {tipo}: {len(mapa)}")
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
