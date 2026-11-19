"""
Treina a busca Calibrada (aprendiz/algoritmos/busca/calibrado.py).

    pip install -r requirements-treino.txt       # scikit-learn (só para treinar)
    python ferramentas/treinar_calibrado.py ../aprendiz-addons
    python ferramentas/treinar_calibrado.py ../aprendiz-addons --so-medir

O que ele faz:

1. Instala os addons da homologação num banco temporário.
2. Monta o CONJUNTO ROTULADO a partir das variações dos addons: de cada
   fragmento com variações, UMA variação é separada e vira pergunta; ela sai
   do índice, para o fragmento não ser achado pela própria frase. Assim a
   pergunta é "dita de outro jeito", como faria uma pessoa.
3. Parte dos fragmentos é removida inteira do índice: as perguntas deles não
   têm resposta, e o certo é recusar. Isso ensina o modelo a não inventar.
4. Divide em TREINO (70%) e TESTE (30%) pelo fragmento, e nunca pela
   pergunta: o mesmo fragmento não aparece nos dois lados.
5. Mede os sinais de cada candidato e treina uma regressão logística
   (scikit-learn), escolhendo a regularização por validação cruzada.
6. Mede no TESTE o Calibrado contra BM25 e Híbrido e grava
   aprendiz/algoritmos/busca/calibrado_pesos.py e o conjunto em
   benchmarks/conjunto_calibrado.json.

Tudo é determinístico: a separação usa um hash do fragmento, não sorteio.
A homologação (ferramentas/homologar.py) não entra no treino; ela é a
medida independente.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "ferramentas"))

from aprendiz import __version__  # noqa: E402
from aprendiz.algoritmos import BUSCAS  # noqa: E402
from aprendiz.algoritmos.busca.calibrado import SINAIS_DA_DECISAO, sinais_da_decisao  # noqa: E402
from aprendiz.core import Assistente  # noqa: E402
from aprendiz.linguagem.normalizador import normalizar  # noqa: E402
from aprendiz.memoria import Banco  # noqa: E402
from aprendiz.memoria.banco import lista_json  # noqa: E402
from homologar import ADDONS  # noqa: E402

PESOS = RAIZ / "aprendiz" / "algoritmos" / "busca" / "calibrado_pesos.py"
CONJUNTO = RAIZ / "benchmarks" / "conjunto_calibrado.json"
FRACAO_TESTE = 3    # em 10
FRACAO_FORA = 1     # em 10: fragmentos removidos (perguntas sem resposta)
REGULARIZACOES = [0.03, 0.1, 0.3, 1.0, 3.0]


def _hash(texto: str) -> int:
    return int(hashlib.sha1(texto.encode()).hexdigest(), 16)


def montar_banco(loja: Path) -> Assistente:
    assistente = Assistente(Banco(str(Path(tempfile.mkdtemp()) / "treino.db")))
    for id_ in ADDONS:
        assistente.instalar_addon((loja / "addons" / f"{id_}.aprendiz").read_bytes())
    return assistente


def montar_conjunto(assistente: Assistente) -> list[dict]:
    """Separa as perguntas e ajusta o índice (variações separadas e fragmentos removidos)."""
    banco = assistente.banco
    docs = [d for d in banco.todos_conhecimentos()
            if d.get("addon_id") and d.get("pergunta") and d.get("tipo") != "verbete"
            and lista_json(d, "variacoes")]
    casos = []
    for doc in sorted(docs, key=lambda d: (d["addon_id"], d["pergunta"])):
        chave = f"{doc['addon_id']}:{doc['pergunta']}"
        h = _hash(chave)
        grupo = "teste" if h % 10 < FRACAO_TESTE else "treino"
        fora = (h // 10) % 10 < FRACAO_FORA
        variacoes = sorted(lista_json(doc, "variacoes"))
        separada = variacoes[(h // 100) % len(variacoes)]
        if fora:
            banco.remover_conhecimento(doc["id"])
            for pergunta in dict.fromkeys([doc["pergunta"], separada]):
                casos.append({"pergunta": pergunta, "esperado": None, "fragmento": chave,
                              "grupo": grupo})
            continue
        restantes = [v for v in lista_json(doc, "variacoes") if v != separada]
        banco._executar("UPDATE conhecimentos SET variacoes = ? WHERE id = ?",
                        (json.dumps(restantes, ensure_ascii=False), doc["id"]))
        casos.append({"pergunta": separada, "esperado": chave, "fragmento": chave,
                      "grupo": grupo, "id": doc["id"]})
    banco._con.commit()
    assistente.reindexar()
    return casos


def preparar(assistente: Assistente, pergunta: str):
    """A consulta como o pipeline a vê na hora da busca (inclui o "o que é X?")."""
    consulta = assistente.linguagem.processar(pergunta)
    analise = (assistente.compreensao.analisar(consulta, pergunta)
               if assistente.compreensao.ativa else None)
    assistente._assunto_definicao = (
        set(normalizar(analise.assunto).split())
        if analise and analise.tipo == "definicao" and analise.assunto else set())
    return consulta


def coletar(assistente: Assistente, casos: list[dict]) -> list[dict]:
    """Os sinais de cada candidato de cada pergunta, com o rótulo (1 = certo)."""
    calibrado = BUSCAS["calibrado"]
    linhas = []
    for n, caso in enumerate(casos):
        consulta = preparar(assistente, caso["pergunta"])
        for doc, sinais in calibrado.sinais(consulta, assistente.contexto):
            linhas.append({"caso": n, "grupo": caso["grupo"], "sinais": sinais,
                           "rotulo": int(doc["id"] == caso.get("id"))})
    return linhas


def treinar(linhas: list[dict]):
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold, cross_val_predict, cross_val_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    nomes = sorted(linhas[0]["sinais"])
    treino = [l for l in linhas if l["grupo"] == "treino"]
    X = np.array([[l["sinais"][s] for s in nomes] for l in treino])
    y = np.array([l["rotulo"] for l in treino])
    grupos = np.array([l["caso"] for l in treino])

    melhor_c, melhor_nota = None, -math.inf
    for c in REGULARIZACOES:
        modelo = make_pipeline(StandardScaler(), LogisticRegression(C=c, max_iter=2000))
        nota = cross_val_score(modelo, X, y, groups=grupos, cv=GroupKFold(5),
                               scoring="neg_log_loss").mean()
        print(f"  C={c:<5} log-loss médio (validação cruzada) = {-nota:.4f}")
        if nota > melhor_nota:
            melhor_c, melhor_nota = c, nota

    modelo = make_pipeline(StandardScaler(), LogisticRegression(C=melhor_c, max_iter=2000))
    modelo.fit(X, y)
    escala, reg = modelo[0], modelo[1]

    # 2ª etapa: a DECISÃO de responder. A 1ª etapa diz a chance de cada
    # candidato; aqui se aprende a chance de o 1º lugar estar certo, olhando
    # a nota dele e a distância para o 2º. As notas vêm de validação cruzada
    # (cada pergunta pontuada por um modelo que não a viu), para a 2ª etapa
    # não aprender com notas otimistas demais.
    fora_da_dobra = cross_val_predict(
        make_pipeline(StandardScaler(), LogisticRegression(C=melhor_c, max_iter=2000)),
        X, y, groups=grupos, cv=GroupKFold(5), method="predict_proba")[:, 1]
    por_caso: dict[int, list[tuple[float, int]]] = {}
    for caso, prob, rotulo in zip(grupos, fora_da_dobra, y):
        por_caso.setdefault(int(caso), []).append((float(prob), int(rotulo)))
    # Perguntas sem nenhum candidato não entram: a busca já recusa sozinha.
    Xd, yd = [], []
    for caso in sorted(set(l["caso"] for l in treino)):
        notas = sorted(por_caso.get(caso, []), reverse=True)
        if notas:
            Xd.append(sinais_da_decisao([p for p, _ in notas]))
            yd.append(notas[0][1])
    decisao = LogisticRegression(C=1.0, max_iter=2000).fit(np.array(Xd), np.array(yd))
    return {
        "sinais": nomes,
        "media": [round(float(v), 6) for v in escala.mean_],
        "desvio": [round(float(v), 6) for v in escala.scale_],
        "pesos": [round(float(v), 6) for v in reg.coef_[0]],
        "vies": round(float(reg.intercept_[0]), 6),
        "regularizacao": melhor_c,
        "decisao": {"sinais": list(SINAIS_DA_DECISAO),
                    "pesos": [round(float(v), 6) for v in decisao.coef_[0]],
                    "vies": round(float(decisao.intercept_[0]), 6)},
    }


def medir(assistente: Assistente, casos: list[dict], buscas: list[str]) -> dict:
    """Acerto, recusa indevida e invenção de cada busca nas perguntas do TESTE."""
    teste = [c for c in casos if c["grupo"] == "teste"]
    resultado = {}
    for nome in buscas:
        certo = recusa = errado = inventou = recusou_bem = 0
        inicio = time.perf_counter()
        for caso in teste:
            consulta = preparar(assistente, caso["pergunta"])
            _, aceitos, _ = assistente.buscar(consulta, nome)
            topo = aceitos[0].id if aceitos else None
            if caso["esperado"] is None:
                inventou += topo is not None
                recusou_bem += topo is None
            elif topo is None:
                recusa += 1
            elif topo == caso["id"]:
                certo += 1
            else:
                errado += 1
        com_resposta = sum(c["esperado"] is not None for c in teste)
        sem_resposta = len(teste) - com_resposta
        resultado[nome] = {
            "acerto": round(certo / com_resposta, 3),
            "errou": round(errado / com_resposta, 3),
            "recusou": round(recusa / com_resposta, 3),
            "inventou": round(inventou / sem_resposta, 3) if sem_resposta else 0.0,
            "ms_por_pergunta": round((time.perf_counter() - inicio) * 1000 / len(teste), 1),
        }
    return resultado


def gravar_pesos(modelo: dict, info: dict) -> None:
    corpo = json.dumps({**modelo, "treino": info}, ensure_ascii=False, indent=4)
    PESOS.write_text(
        '"""\n'
        "Pesos da busca Calibrada. ARQUIVO GERADO por ferramentas/treinar_calibrado.py:\n"
        "não edite à mão; treine de novo.\n"
        '"""\n\n'
        f"MODELO = {corpo}\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("loja", type=Path, help="pasta do repositório aprendiz-addons")
    ap.add_argument("--so-medir", action="store_true",
                    help="não treina: mede os pesos atuais no conjunto de teste")
    args = ap.parse_args()

    print("Instalando os addons…")
    assistente = montar_banco(args.loja)
    casos = montar_conjunto(assistente)
    treino = sum(c["grupo"] == "treino" for c in casos)
    print(f"{len(casos)} perguntas: {treino} de treino e {len(casos) - treino} de teste "
          f"({sum(c['esperado'] is None for c in casos)} sem resposta)")

    if not args.so_medir:
        print("Medindo os sinais…")
        linhas = coletar(assistente, casos)
        no_conjunto = sum(1 for n, c in enumerate(casos) if c["esperado"] and any(
            l["caso"] == n and l["rotulo"] for l in linhas))
        com_resposta = sum(c["esperado"] is not None for c in casos)
        print(f"  a resposta certa está entre os candidatos em {no_conjunto}/{com_resposta}")
        print("Treinando…")
        modelo = treinar(linhas)
        gravar_pesos(modelo, {})
        import importlib
        from aprendiz.algoritmos.busca import calibrado_pesos
        importlib.reload(calibrado_pesos)

    print("Medindo no TESTE…")
    medidas = medir(assistente, casos, ["bm25", "hibrido", "calibrado"])
    for nome, m in medidas.items():
        print(f"  {nome:10} acerto {m['acerto']:.1%}  errou {m['errou']:.1%}  "
              f"recusou {m['recusou']:.1%}  inventou {m['inventou']:.1%}  "
              f"({m['ms_por_pergunta']} ms/pergunta)")

    if not args.so_medir:
        info = {
            "data": date.today().isoformat(),
            "versao_app": __version__,
            "perguntas_treino": treino,
            "perguntas_teste": len(casos) - treino,
            "addons": {a["id"]: a["versao"] for a in assistente.banco.listar_addons()},
            "teste": medidas,
        }
        gravar_pesos(modelo, info)
        CONJUNTO.write_text(json.dumps(
            [{k: c[k] for k in ("pergunta", "esperado", "grupo")} for c in casos],
            ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"Gravado: {PESOS.relative_to(RAIZ)} e {CONJUNTO.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
