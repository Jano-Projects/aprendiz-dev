"""
Benchmark: compara os algoritmos de busca num mesmo conjunto de perguntas.

Uso:
    python ferramentas/comparar.py
    python ferramentas/comparar.py --dados ferramentas/dados/meus_dados.json

Para cada algoritmo, mede:
    • acerto@1   → a resposta aceita foi o conhecimento esperado
    • recusas    → disse "não sei" para perguntas que TÊM resposta (ruim)
    • estrito    → disse "não sei" para perguntas SEM resposta na base (bom)
    • tempo      → média por pergunta, em milissegundos

O arquivo de dados tem duas listas:
    "conhecimentos": [{"id": "...", "pergunta": "...", "conteudo": "..."}]
    "testes":        [{"pergunta": "...", "esperado": "id" ou null}]
    (esperado = null significa que o assistente DEVE dizer que não sabe)

Experimente: mude limiares, troque o radicalizador, adicione sinônimos...
e rode de novo para ver o efeito. É o melhor jeito de aprender como cada
técnica se comporta.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aprendiz.algoritmos import BUSCAS  # noqa: E402
from aprendiz.core import Assistente  # noqa: E402
from aprendiz.memoria import Banco  # noqa: E402


def rodar(caminho_dados: Path) -> None:
    dados = json.loads(caminho_dados.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as pasta:
        banco = Banco(Path(pasta) / "bench.db")
        assistente = Assistente(banco)
        for c in dados["conhecimentos"]:
            assistente.ensinar(c["conteudo"], pergunta=c.get("pergunta"), id=c["id"])

        testes = dados["testes"]
        com_resposta = [t for t in testes if t["esperado"]]
        sem_resposta = [t for t in testes if not t["esperado"]]

        print(f"\n{len(dados['conhecimentos'])} conhecimentos · {len(com_resposta)} perguntas com "
              f"resposta · {len(sem_resposta)} sem resposta\n")
        cabecalho = f"{'algoritmo':<26}{'acerto@1':>10}{'recusas':>10}{'estrito':>10}{'tempo (ms)':>12}"
        print(cabecalho)
        print("-" * len(cabecalho))

        for nome, algoritmo in BUSCAS.items():
            acertos = recusas = estrito_ok = 0
            tempos = []
            erros = []
            for t in testes:
                consulta = assistente.linguagem.processar(t["pergunta"])
                inicio = time.perf_counter()
                candidatos = algoritmo.buscar(consulta, assistente.contexto, limite=5)
                tempos.append((time.perf_counter() - inicio) * 1000)
                aceitos = [c for c in candidatos if c.confianca >= algoritmo.limiar]
                escolhido = aceitos[0].id if aceitos else None

                if t["esperado"]:
                    if escolhido == t["esperado"]:
                        acertos += 1
                    elif escolhido is None:
                        recusas += 1
                        erros.append(f"  recusou: {t['pergunta']}")
                    else:
                        erros.append(f"  errou:   {t['pergunta']}  →  {escolhido}")
                elif escolhido is None:
                    estrito_ok += 1
                else:
                    erros.append(f"  inventou: {t['pergunta']}  →  {escolhido}")

            print(f"{algoritmo.titulo:<26}"
                  f"{acertos / len(com_resposta):>10.0%}"
                  f"{recusas:>10}"
                  f"{f'{estrito_ok}/{len(sem_resposta)}':>10}"
                  f"{statistics.mean(tempos):>12.2f}")
            if erros and ARGS.detalhes:
                print("\n".join(erros))

        banco.fechar()
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--dados", type=Path,
                        default=Path(__file__).parent / "dados" / "dados_exemplo.json")
    parser.add_argument("--detalhes", action="store_true", help="lista cada erro")
    ARGS = parser.parse_args()
    rodar(ARGS.dados)
