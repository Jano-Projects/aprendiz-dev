"""
Testes da 0.6: dicionário nos dois sentidos (traduções e regiões), variações
de pergunta e o novo formato do perguntas.txt/verbetes.txt.
"""

import importlib.util
from pathlib import Path

import pytest

from aprendiz.addons import ErroAddon, criar_pacote, ler_pacote

STOP = {"stopwords": ["significa", "significado", "quer", "dizer", "giria", "palavra"]}


def dicionario(assistente, id_, nome, termos, itens, artigo=""):
    assistente.instalar_addon(criar_pacote(
        {"id": id_, "nome": nome, "versao": "1.0.0", "regiao": {"nome": nome, "termos": termos, "artigo": artigo}},
        itens, STOP))


def v(termo, conteudo, traducoes=(), variacoes=()):
    item = {"tipo": "verbete", "pergunta": termo, "conteudo": conteudo}
    if traducoes:
        item["traducoes"] = list(traducoes)
    if variacoes:
        item["variacoes"] = list(variacoes)
    return item


@pytest.fixture
def com_dicionarios(assistente):
    dicionario(assistente, "gb", "Guiné-Bissau",
               ["guine", "guine bissau", "guineense", "guineenses", "kriol"],
               [v("tabanka", "**tabanka**: aldeia.", ["aldeia", "povoado"], ["tabanca"]),
                v("obrigadu", "**obrigadu**: obrigado.", ["obrigado"])], artigo="a")
    dicionario(assistente, "ao", "Angola", ["angola", "angolano", "angolana", "angolanos"],
               [v("kumbu", "**kumbu**: dinheiro.", ["dinheiro"]),
                v("kota", "**kota**: pessoa mais velha.", ["pessoa mais velha"]),
                v("machimbombo", "**machimbombo**: ônibus.", ["ônibus"])])
    dicionario(assistente, "pt", "Portugal", ["portugal", "portugueses"],
               [v("autocarro", "**autocarro**: ônibus.", ["ônibus"])])
    return assistente


def texto(assistente, pergunta):
    msg = assistente.responder(pergunta)["mensagem"]
    return msg["meta"]["tipo"], msg["texto"]


# ------------------------------------------------------------------ sentido inverso
@pytest.mark.parametrize("pergunta", [
    "como se fala aldeia em guiné?",
    "Como se diz aldeia no kriol",
    "como os guineenses chamam a aldeia?",
    "qual a palavra para aldeia em Guiné-Bissau",
    "qual a gíria guineense pra aldeia",
    "traduza aldeia para kriol",
    "aldeia em kriol",
    "como é aldeia na guiné",
    "como se diz povoado em guiné",
])
def test_como_se_diz_em_uma_regiao(com_dicionarios, pergunta):
    tipo, resposta = texto(com_dicionarios, pergunta)
    assert tipo == "conhecimento"
    assert resposta.startswith("Na Guiné-Bissau,") and "**tabanka**" in resposta


def test_sem_regiao_lista_todos_os_lugares(com_dicionarios):
    _, resposta = texto(com_dicionarios, "como se diz ônibus?")
    assert "**Angola:** machimbombo" in resposta and "**Portugal:** autocarro" in resposta


@pytest.mark.parametrize("pergunta", [
    'quais as variações de "ônibus" em português?',
    "outras formas de dizer ônibus",
    "variações de ônibus nos países",
])
def test_variacoes_listam_todos_os_lugares(com_dicionarios, pergunta):
    _, resposta = texto(com_dicionarios, pergunta)
    assert "**Angola:** machimbombo" in resposta and "**Portugal:** autocarro" in resposta


def test_regiao_sem_dicionario_avisa_e_mostra_os_outros(com_dicionarios):
    _, resposta = texto(com_dicionarios, "como se diz dinheiro em inglês?")
    assert resposta.startswith("Não tenho um dicionário de “inglês” instalado.")
    assert "**Angola:** kumbu" in resposta


def test_intencao_social_nao_atrapalha(com_dicionarios):
    _, resposta = texto(com_dicionarios, "como se diz obrigado em guiné")
    assert "**obrigadu**" in resposta


# ------------------------------------------------------------------ sentido direto
@pytest.mark.parametrize("pergunta", ["o que é kota em angola", "kota em angola",
                                      "o que significa kota em Angola?", "kota"])
def test_termo_com_ou_sem_regiao(com_dicionarios, pergunta):
    assert texto(com_dicionarios, pergunta)[1] == "**kota**: pessoa mais velha."


def test_termo_em_outra_regiao(com_dicionarios):
    _, resposta = texto(com_dicionarios, "o que significa kota em portugal")
    assert resposta.startswith("Não encontrei *kota* no dicionário de Portugal.")


def test_variacao_de_grafia(com_dicionarios):
    assert "**tabanka**" in texto(com_dicionarios, "o que significa tabanca")[1]


# ------------------------------------------------------------------ não sequestra
@pytest.mark.parametrize("pergunta", [
    "como se chama a capital da frança",
    "fui de ônibus em portugal ano passado",
    "como se diz isso de um jeito educado",
])
def test_frases_comuns_seguem_o_pipeline(com_dicionarios, pergunta):
    assert texto(com_dicionarios, pergunta)[0] == "desconhecido"


def test_o_dono_vence_na_mesma_pergunta(com_dicionarios):
    com_dicionarios.ensinar("Na minha casa, chamamos de vila.", pergunta="como se diz aldeia em guiné")
    assert texto(com_dicionarios, "como se diz aldeia em guiné")[1].startswith("Na minha casa")
    com_dicionarios.ensinar("Meu pai se chama João.", pergunta="como se chama o meu pai")
    assert texto(com_dicionarios, "como se chama o meu pai")[1] == "Meu pai se chama João."


def test_desativar_o_addon_tira_do_dicionario(com_dicionarios):
    com_dicionarios.definir_addon_ativo("gb", False)
    assert texto(com_dicionarios, "como se diz aldeia em guiné")[0] == "desconhecido"


# ------------------------------------------------------------------ variações (perguntas)
@pytest.mark.parametrize("busca", ["bm25", "tfidf", "fuzzy", "hibrido"])
@pytest.mark.parametrize("pergunta", ["como copiar um arquivo", "atalho de copiar",
                                      "o que o ctrl c faz"])
def test_variacoes_levam_a_mesma_resposta(assistente, busca, pergunta):
    assistente.instalar_addon(criar_pacote(
        {"id": "atalhos", "nome": "Atalhos", "versao": "1.0.0"},
        [{"pergunta": "como copiar um arquivo",
          "variacoes": ["atalho de copiar", "o que o ctrl c faz"],
          "conteudo": "Selecione e use Ctrl+C."},
         {"pergunta": "como colar", "conteudo": "Use Ctrl+V."}]))
    msg = assistente.responder(pergunta, busca=busca)["mensagem"]
    assert msg["texto"] == "Selecione e use Ctrl+C."


# ------------------------------------------------------------------ formato
@pytest.mark.parametrize("item, trecho", [
    ({"pergunta": "a", "conteudo": "b", "traducoes": ["x"]}, "Só verbetes"),
    ({"conteudo": "b", "variacoes": ["x"]}, "não tem 'pergunta'"),
    ({"pergunta": "a", "conteudo": "b", "variacoes": "x"}, "lista"),
])
def test_campos_novos_invalidos(item, trecho):
    with pytest.raises(ErroAddon, match=trecho):
        criar_pacote({"id": "teste", "nome": "T", "versao": "1.0.0"}, [item])


def test_regiao_no_manifesto():
    m = ler_pacote(criar_pacote(
        {"id": "teste", "nome": "T", "versao": "1.0.0", "regiao": {"nome": "Angola", "termos": ["angola"]}},
        [v("kota", "x")])).manifesto
    assert m["regiao"] == {"nome": "Angola", "termos": ["angola"], "artigo": ""}
    with pytest.raises(ErroAddon, match="nome"):
        criar_pacote({"id": "teste", "nome": "T", "versao": "1.0.0", "regiao": {"termos": []}},
                     [v("kota", "x")])


def test_criar_addon_le_variacoes_e_traducoes(tmp_path):
    caminho = Path(__file__).resolve().parent.parent / "ferramentas" / "criar_addon.py"
    spec = importlib.util.spec_from_file_location("criar_addon", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    arquivo = tmp_path / "verbetes.txt"
    arquivo.write_text("# comentário\nV: busão\nV: buzão\nT: ônibus, coletivo\nR: Ônibus.\n\n"
                       "P: como copiar\nP: atalho de copiar\nR: Ctrl+C.\nP: como colar\nR: Ctrl+V.\n",
                       encoding="utf-8")
    itens = modulo.ler_perguntas(arquivo)
    assert itens[0] == {"pergunta": "busão", "conteudo": "Ônibus.", "tipo": "verbete",
                        "variacoes": ["buzão"], "traducoes": ["ônibus", "coletivo"]}
    assert itens[1]["variacoes"] == ["atalho de copiar"]
    assert itens[2] == {"pergunta": "como colar", "conteudo": "Ctrl+V.", "tipo": "pergunta"}


def test_em_portugues_pede_o_significado(com_dicionarios):
    assert texto(com_dicionarios, "como se diz kota em português?")[1] == "**kota**: pessoa mais velha."


def test_criar_addon_preserva_blocos_de_codigo(tmp_path):
    caminho = Path(__file__).resolve().parent.parent / "ferramentas" / "criar_addon.py"
    spec = importlib.util.spec_from_file_location("criar_addon", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    arquivo = tmp_path / "perguntas.txt"
    arquivo.write_text(
        "P: como fazer um if em python\n"
        "R: Assim:\n"
        "```python\n"
        "# comentário do Python\n"
        "if x > 0:\n"
        "    print(x)\n"
        "\n"
        "p: list = []\n"
        "```\n"
        "O bloco termina aqui.\n"
        "\n"
        "P: hello world em c\n"
        "R: ```c\n#include <stdio.h>\n```\n",
        encoding="utf-8")
    itens = modulo.ler_perguntas(arquivo)
    assert len(itens) == 2
    assert itens[0]["conteudo"] == ("Assim:\n```python\n# comentário do Python\nif x > 0:\n"
                                    "    print(x)\n\np: list = []\n```\nO bloco termina aqui.")
    assert itens[1]["conteudo"] == "```c\n#include <stdio.h>\n```"

    arquivo.write_text("P: x\nR: ```\naberto\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="não fechado"):
        modulo.ler_perguntas(arquivo)
