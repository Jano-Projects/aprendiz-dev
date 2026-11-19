"""Teia de porquês (2.0): leitura no perguntas.txt, validação e gravação."""

import importlib.util
import json
from pathlib import Path

import pytest

from aprendiz.addons import ErroAddon, criar_pacote, validar_conhecimentos
from aprendiz.memoria.banco import teia_de

MANIFESTO = {"id": "sql-teia", "nome": "SQL teia", "versao": "1.0.0", "autor": "Teste"}
PERGUNTAS = """\
F: where
A: where, filtro
Q: porque | filtra as linhas antes de agrupar | -> group-by
Q: diferente-de | o HAVING filtra depois de agrupar | -> having
P: para que serve o where
R: O WHERE filtra as linhas.
N: isto aqui é texto da resposta, não da teia

F: having
Q: porque | os totais só existem depois do GROUP BY | -> group-by
P: para que serve o having
R: O HAVING filtra os grupos.

F: group-by
N: raiz
Q: regra | junta linhas com o mesmo valor | -> prog-banco-dados:agregacao
P: o que faz o group by
R: O GROUP BY agrupa linhas iguais.
"""


def criar_addon():
    caminho = Path(__file__).resolve().parent.parent / "ferramentas" / "criar_addon.py"
    spec = importlib.util.spec_from_file_location("criar_addon", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def itens(tmp_path):
    arquivo = tmp_path / "perguntas.txt"
    arquivo.write_text(PERGUNTAS, encoding="utf-8")
    return criar_addon().ler_perguntas(arquivo)


def test_le_a_teia_do_perguntas_txt(itens):
    where = itens[0]["teia"]
    assert where["ref"] == "where" and where["assuntos"] == ["where", "filtro"]
    assert where["porques"][1] == {"relacao": "diferente-de",
                                   "texto": "o HAVING filtra depois de agrupar", "liga": "having"}
    assert itens[0]["conteudo"].endswith("não da teia")   # N: depois do R: é resposta
    assert itens[2]["teia"]["raiz"] is True


def test_validacao_aceita_e_confere_ligacoes(itens):
    validados = validar_conhecimentos(itens)
    assert validados[2]["teia"]["porques"][0]["liga"] == "prog-banco-dados:agregacao"


@pytest.mark.parametrize("estrago, erro", [
    (lambda i: i[0]["teia"]["porques"][0].update(liga="nao-existe"), "não existem"),
    (lambda i: i[1]["teia"].update(ref="where"), "repetidos"),
    (lambda i: i[0]["teia"]["porques"][0].update(relacao="talvez"), "relação"),
    (lambda i: i[0]["teia"].update(ref="Com Espaço"), "ref"),
])
def test_validacao_recusa_teia_quebrada(itens, estrago, erro):
    estrago(itens)
    with pytest.raises(ErroAddon, match=erro):
        validar_conhecimentos(itens)


def test_teia_gravada_e_assuntos_na_busca(assistente, itens):
    assistente.instalar_addon(criar_pacote(MANIFESTO, itens, {}))
    linhas = assistente.banco._consultar(
        "SELECT * FROM conhecimentos WHERE addon_id = 'sql-teia' ORDER BY pergunta")
    teias = {teia_de(l)["ref"]: teia_de(l) for l in linhas}
    assert set(teias) == {"where", "having", "group-by"}
    assert "filtr" in next(l for l in linhas if teia_de(l)["ref"] == "where")["texto_busca"]
    assert json.loads(linhas[0]["teia"])["porques"]


# --------------------------------------------------------------- percurso
OUTRO = """\
F: agregacao
N: raiz
Q: definicao | resumir várias linhas num valor (soma, média, contagem)
P: o que é agregação em banco de dados
R: Agregação resume várias linhas num valor.

F: indices
Q: porque | aceleram a busca por uma coluna
P: o que é um índice
R: Índice acelera buscas.
"""


@pytest.fixture
def com_teia(assistente, tmp_path):
    for id_, texto in (("sql-teia", PERGUNTAS), ("prog-banco-dados", OUTRO)):
        arquivo = tmp_path / f"{id_}.txt"
        arquivo.write_text(texto, encoding="utf-8")
        itens = criar_addon().ler_perguntas(arquivo)
        assistente.instalar_addon(criar_pacote({**MANIFESTO, "id": id_}, itens, {}))
    return assistente


def doc_por_ref(assistente, ref):
    linhas = assistente.banco._consultar("SELECT * FROM conhecimentos WHERE teia IS NOT NULL")
    return next(l for l in linhas if teia_de(l)["ref"] == ref)


def test_percurso_desce_ate_a_raiz_de_outro_addon(com_teia):
    caminho = com_teia.teia.percorrer(doc_por_ref(com_teia, "where"), ["where"])
    passos = [p.como_texto().strip() for p in caminho.passos]
    assert passos[0] == "where —porque → group-by (raiz)"      # causa antes do contraste
    assert passos[1] == "where —diferente-de → having"
    assert len(passos) == 2     # não desce além da raiz; o contraste (lateral) não se desdobra
    # Partindo do group-by, a regra atravessa para a raiz de OUTRO addon.
    outro = com_teia.teia.percorrer(doc_por_ref(com_teia, "group-by"), ["group"])
    assert [p.como_texto() for p in outro.passos] == ["group-by —regra → agregacao (raiz)"]


def test_addon_desativado_corta_a_ligacao(com_teia):
    com_teia.definir_addon_ativo("prog-banco-dados", False)
    caminho = com_teia.teia.percorrer(doc_por_ref(com_teia, "group-by"), ["group"])
    assert caminho.passos[0].cortado == "fora"
    assert caminho.passos[0].texto == "junta linhas com o mesmo valor"   # o texto ainda vale


def test_pergunta_registra_o_caminho_na_explicacao(com_teia):
    r = com_teia.responder("para que serve o where?")
    etapas = r["mensagem"]["meta"]["explicacao"]["etapas"]
    teia = next(e for e in etapas if e["nome"] == "Teia de porquês")
    assert teia["dados"]["partida"] == "where" and teia["dados"]["usados"] == 2


# --------------------------------------------------------------- resposta trabalhada
import random  # noqa: E402

from aprendiz import recursos  # noqa: E402
from aprendiz.linguagem.normalizador import normalizar  # noqa: E402

EXPRESSAO = {"abertura_addon": ["Olha, no {x} eu tenho isto:"],
             "porque": ["E é assim porque {x}."],
             "diferente-de": ["A diferença: {x}."],
             "fechamento": ["Quer que eu aprofunde algum ponto?"]}


def test_trabalhada_explica_os_porques(com_teia):
    r = com_teia.responder("para que serve o where?", resposta="trabalhada")
    texto = r["mensagem"]["texto"]
    assert texto.startswith("Pelo que tenho em **SQL teia**:")       # abertura padrão
    assert "O WHERE filtra as linhas." in texto                      # o fato
    assert "Isso porque filtra as linhas antes de agrupar." in texto  # porquê nível 1
    assert "O GROUP BY agrupa linhas iguais." not in texto           # o porquê já diz o essencial
    assert "Já o HAVING filtra depois de agrupar." in texto           # contraste, minúscula
    assert "{x}" not in texto
    assert texto.index("porque") < texto.index("HAVING")             # causa antes do contraste


def test_trabalhada_usa_frases_do_addon_de_linguagem(com_teia):
    compreensao = recursos.validar_compreensao({"expressao": EXPRESSAO}, normalizar)
    com_teia.instalar_addon(criar_pacote(
        {"id": "expressao-teste", "nome": "Expressão", "versao": "1.0.0", "autor": "t"},
        compreensao=compreensao))
    com_teia.contexto.expressao.sorteio = random.Random(1)
    texto = com_teia.responder("para que serve o where?", resposta="trabalhada")["mensagem"]["texto"]
    assert texto.startswith("Olha, no SQL teia eu tenho isto:")
    assert "E é assim porque filtra as linhas antes de agrupar." in texto
    assert "A diferença: o HAVING filtra depois de agrupar." in texto
    assert texto.endswith("Quer que eu aprofunde algum ponto?")


def test_trabalhada_sem_teia_responde_como_a_direta(assistente):
    assistente.ensinar("Fica na garagem.", pergunta="onde está a bicicleta")
    r = assistente.responder("onde está a bicicleta?", resposta="trabalhada")
    assert r["mensagem"]["texto"] == "Fica na garagem."


@pytest.mark.parametrize("ruim", [
    {"porque": ["sem lacuna"]}, {"porque": ["{x} e {x}"]}, {"inventada": ["{x}"]},
    {"porque": ["com {chave} estranha {x}"]},
])
def test_expressao_invalida_e_recusada(ruim):
    with pytest.raises(recursos.ErroRecurso):
        recursos.validar_compreensao({"expressao": ruim}, normalizar)
