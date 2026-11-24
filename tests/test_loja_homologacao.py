"""
Homologação contra os addons REAIS da loja, como teste automático.

Opcional e lento (~2 min). Roda só quando a loja é informada:

    pytest --loja ../aprendiz-addons
    APRENDIZ_LOJA=../aprendiz-addons pytest

São 249 perguntas de gente de verdade (ferramentas/homologar.py). Cada busca
tem um PISO: o número de acertos da 2.5.1. Uma mudança que derrube o piso
é regressão; uma que suba, atualize o piso aqui e nos documentos.
"""

import importlib.util
import random
import shutil
import unicodedata
from pathlib import Path

import pytest

from aprendiz.core import Assistente
from aprendiz.memoria import Banco

pytestmark = pytest.mark.loja

PISOS = {"hibrido": 237, "bm25": 227, "calibrado": 236, "tfidf": 211, "fuzzy": 162}
# Base pessoal (2.7, homologar.py --pessoal), na busca padrão: acertos mínimos
# e o máximo de perguntas sem resposta em que pode inventar.
PISO_PESSOAL = {"busca": "calibrado", "acertos": 41, "inventou": 1}

# Fração mínima de perguntas que continuam certas depois de cada transformação
# (busca Híbrida). Medido na 2.5.1: 100% em quase todas; erros de digitação, 98%.
PISOS_METAMORFICOS = {
    "maiusculas": 1.0, "pontuacao": 1.0, "por_favor": 1.0, "me_explica": 1.0,
    "espacos": 1.0, "abrev": 1.0, "sem_acento": 0.98, "digitacao": 0.97,
}


def carregar_homologar():
    caminho = Path(__file__).resolve().parent.parent / "ferramentas" / "homologar.py"
    spec = importlib.util.spec_from_file_location("homologar", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def homologar():
    return carregar_homologar()


@pytest.fixture(scope="module")
def banco_da_loja(homologar, pasta_loja, tmp_path_factory):
    """Instala os addons uma vez; cada teste recebe uma CÓPIA limpa do banco."""
    caminho = tmp_path_factory.mktemp("loja") / "base.db"
    banco = Banco(caminho)
    a = Assistente(banco)
    for id_ in homologar.ADDONS:
        a.instalar_addon((pasta_loja / "addons" / f"{id_}.aprendiz").read_bytes())
    banco.fechar()
    return caminho


@pytest.fixture
def com_loja(banco_da_loja, tmp_path):
    copia = tmp_path / "homologacao.db"
    shutil.copy(banco_da_loja, copia)
    banco = Banco(copia)
    yield Assistente(banco)
    banco.fechar()


def acertos(h, a, busca):
    certos, conversa = 0, None
    for _, pergunta, esperado in h.CASOS:
        if pergunta not in h.SEGUIR:
            conversa = None
        r = a.responder(pergunta, conversa_id=conversa, busca=busca, resposta="trabalhada")
        conversa = r["conversa_id"]
        certos += h.confere(r, esperado)
    return certos


@pytest.mark.parametrize("busca", sorted(PISOS))
def test_homologacao_nao_cai_abaixo_do_piso(homologar, com_loja, busca):
    obtido = acertos(homologar, com_loja, busca)
    assert obtido >= PISOS[busca], f"{busca}: {obtido}/{len(homologar.CASOS)} (piso {PISOS[busca]})"


# ------------------------------------------------------------ metamórficos
def _sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _digitacao(s, rnd):
    ps = s.split()
    idx = [i for i, p in enumerate(ps) if len(p) >= 6 and p.isalpha()]
    if not idx:
        return None
    i = rnd.choice(idx)
    p = ps[i]
    j = rnd.randrange(1, len(p) - 2)
    ps[i] = p[:j] + p[j + 1] + p[j] + p[j + 2:]
    return " ".join(ps)


def _abrev(s, _):
    if not any(x in s for x in ("você", "porque", "por que", "que ")):
        return None
    return s.replace("você", "vc").replace("porque", "pq").replace("por que", "pq").replace("que ", "q ")


TRANSFORMACOES = {
    "maiusculas": lambda s, r: s.upper(),
    "sem_acento": lambda s, r: _sem_acento(s),
    "pontuacao": lambda s, r: s.rstrip("?!.") + "???",
    "por_favor": lambda s, r: "por favor, " + s,
    "me_explica": lambda s, r: "me explica " + s,
    "espacos": lambda s, r: "  " + s.replace(" ", "   ") + "  ",
    "digitacao": _digitacao,
    "abrev": _abrev,
}


def test_metamorficos_na_loja(homologar, com_loja):
    h, a = homologar, com_loja
    rnd = random.Random(42)
    certos = {k: 0 for k in TRANSFORMACOES}
    total = {k: 0 for k in TRANSFORMACOES}
    for grupo, pergunta, esperado in h.CASOS:
        if (pergunta in h.SEGUIR or esperado in ("fundo", "panorama")
                or esperado.startswith(("tipo:", "!q:", "texto:"))
                or grupo in ("contexto", "conversa")):
            continue
        if not h.confere(a.responder(pergunta, busca="hibrido"), esperado):
            continue
        for nome, transformar in TRANSFORMACOES.items():
            nova = transformar(pergunta, rnd)
            if not nova or nova == pergunta:
                continue
            total[nome] += 1
            certos[nome] += h.confere(a.responder(nova, busca="hibrido"), esperado)
    abaixo = {k: f"{certos[k]}/{total[k]}" for k in TRANSFORMACOES
              if total[k] and certos[k] / total[k] < PISOS_METAMORFICOS[k]}
    assert not abaixo, abaixo


def test_base_pessoal_nao_cai_abaixo_do_piso(homologar, com_loja):
    """O uso principal: o dono ensina e pergunta (ferramentas/dados/base_pessoal.json)."""
    import json
    base = json.loads(homologar.BASE_PESSOAL.read_text(encoding="utf-8"))
    for fato in base["fatos"]:
        com_loja.ensinar(fato["conteudo"], pergunta=fato["pergunta"])
    certos, inventou = 0, 0
    for grupo, pergunta, esperado in base["casos"]:
        ok = homologar.confere(com_loja.responder(pergunta, busca=PISO_PESSOAL["busca"],
                                                  resposta="trabalhada"), esperado)
        certos += ok
        inventou += grupo == "sem resposta" and not ok
    assert certos >= PISO_PESSOAL["acertos"], f"base pessoal: {certos}/{len(base['casos'])}"
    assert inventou <= PISO_PESSOAL["inventou"], f"inventou em {inventou} perguntas sem resposta"
