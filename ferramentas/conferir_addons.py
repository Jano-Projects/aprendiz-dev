"""
Confere se vários addons convivem bem antes de publicá-los ou ativá-los juntos.

O Aprendiz 1.0 junta as abreviações e os sinônimos de todos os addons ativos
(veja aprendiz/linguagem/resolucao.py). Quando dois addons explicam o mesmo
termo de jeitos diferentes, o termo deixa de ser trocado até o dono escolher.
Esta ferramenta mostra isso ANTES, para quem cria addons:

    python ferramentas/conferir_addons.py addons/*.aprendiz

Para cada tipo (abreviações, sinônimos) lista:
    • conflitos  → mesmo termo, valores diferentes em addons diferentes
    • cadeias    → a → b → c (resolvidas automaticamente; vale conferir o sentido)
    • ciclos     → a → b → a (resolvidos pelo menor termo; quase sempre é engano)

Sai com código 1 se houver conflitos (útil num CI da loja de addons).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aprendiz.addons import pacote as addons  # noqa: E402
from aprendiz.linguagem.resolucao import resolver  # noqa: E402


def conferir(caminhos: list[Path]) -> int:
    entradas: dict[str, list[tuple[str, str, str]]] = {"abreviacoes": [], "sinonimos": []}
    for caminho in caminhos:
        pacote = addons.ler_pacote(caminho.read_bytes())
        nome = pacote.manifesto["nome"]
        for tipo in entradas:
            entradas[tipo] += [(t, v, nome) for t, v in pacote.linguagem.get(tipo, {}).items()]
    print(f"{len(caminhos)} addon(s) conferido(s).")

    total_conflitos = 0
    for tipo, lista in entradas.items():
        bruto = {}
        for t, v, _ in lista:
            bruto.setdefault(t, v)
        _, conflitos = resolver(lista, {}, encadear=(tipo == "sinonimos"))
        total_conflitos += len(conflitos)
        print(f"\n== {tipo}: {len(lista)} entradas, {len(conflitos)} conflito(s)")
        for c in conflitos:
            opcoes = "; ".join(f"{o['valor']} ({', '.join(o['addons'])})" for o in c["opcoes"])
            print(f"  CONFLITO  {c['termo']} → {opcoes}")
        if tipo == "sinonimos":
            for termo, valor in sorted(bruto.items()):
                if valor in bruto and bruto[valor] != valor:
                    seguinte = bruto[valor]
                    marca = "CICLO " if seguinte == termo else "cadeia"
                    print(f"  {marca}    {termo} → {valor} → {seguinte}")
    return 1 if total_conflitos else 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("addons", nargs="+", type=Path, help="arquivos .aprendiz")
    sys.exit(conferir(p.parse_args().addons))


if __name__ == "__main__":
    main()
