"""
Testes da 2.3.1: confusão entre domínios.

Caso real: "é possível listar ou indicar traduções ou variações da palavra
aldeia em português?" era respondido com um índice de SQL. Três falhas
empilhadas:
    1. "indicar" casava com "índice" pela folga de flexão (mesmo começo);
    2. a folga abaixo do limiar aceitava quem batia numa única palavra de
       contexto ("português");
    3. o dicionário não reconhecia o pedido escrito com "é possível listar…".
"""

import struct

from aprendiz import addons as pacotes
from aprendiz import recursos
from aprendiz.core.assistente import _parecida

from test_dicionario import com_dicionarios, texto  # noqa: F401 (fixture)


def manifesto(id_):
    return {"id": id_, "nome": id_, "versao": "1.0.0", "origem": "oficial", "editor": "Jano Projects"}


def pacote_vetores() -> bytes:
    """indice ≈ indices; indicar aponta para outro lado (como nos vetores reais)."""
    linhas = [
        [127, 0, 0, 0, 0, 0, 0, 0],    # 0 indice
        [118, 40, 0, 0, 0, 0, 0, 0],   # 1 indices
        [0, 0, 127, 0, 0, 0, 0, 0],    # 2 indicar
    ]
    dados = b"".join(struct.pack("8b", *l) for l in linhas)
    vetores = recursos.Vetores(dimensoes=8, quantidade=3, dados=dados,
                               palavras=[("indice", 0), ("indices", 1), ("indicar", 2)])
    return pacotes.criar_pacote(manifesto("vetores-teste"), vetores=vetores)


# ------------------------------------------------------------------ falsa flexão
def test_sem_vetores_o_comeco_igual_basta(assistente):
    assert _parecida("indicar", {"indice"}, False, assistente.linguagem.lexico)


def test_com_vetores_falsa_flexao_nao_conta(assistente):
    assistente.instalar_addon(pacote_vetores())
    lexico = assistente.linguagem.lexico
    assert lexico.sem_relacao("indicar", "indice")
    assert not lexico.sem_relacao("indices", "indice")
    assert not _parecida("indicar", {"indice"}, False, lexico)
    assert _parecida("indices", {"indice"}, False, lexico)


def test_palavra_sem_vetor_nao_e_barrada(assistente):
    assistente.instalar_addon(pacote_vetores())
    assert not assistente.linguagem.lexico.sem_relacao("indicador", "indice")


def test_indicar_nao_puxa_indice(assistente):
    assistente.ensinar("CREATE INDEX acelera as buscas.", pergunta="como criar índice em sql")
    assistente.instalar_addon(pacote_vetores())
    r = assistente.responder("pode me indicar um livro?")["mensagem"]
    assert "CREATE INDEX" not in r["texto"]


# ------------------------------------------------------------------ dicionário
def test_pedido_educado_chega_ao_dicionario(com_dicionarios):  # noqa: F811
    for pergunta in ["é possível listar ou indicar traduções ou variações da palavra aldeia em português?",
                     "você pode me mostrar as variações de aldeia?",
                     "sinônimos de aldeia",
                     "traduções ou variações da palavra aldeia"]:
        tipo, resposta = texto(com_dicionarios, pergunta)
        assert tipo == "conhecimento", pergunta
        assert "tabanka" in resposta, pergunta


def test_pedido_sobre_a_palavra_sem_verbete_diz_que_nao_sabe(com_dicionarios):  # noqa: F811
    com_dicionarios.ensinar("Ensine sinônimos em Configurações.",
                            pergunta="como adicionar sinônimos de fábrica")
    tipo, resposta = texto(com_dicionarios, "sinônimos de vilarejo")
    assert tipo == "desconhecido"
    assert "vilarejo" in resposta and "Configurações" not in resposta


def test_formas_de_fazer_algo_segue_para_a_busca(com_dicionarios):  # noqa: F811
    com_dicionarios.ensinar("Use sorted() ou lista.sort().", pergunta="como ordenar uma lista em python")
    tipo, resposta = texto(com_dicionarios, "quais as formas de ordenar uma lista em python")
    assert tipo == "conhecimento" and "sorted" in resposta


def test_dono_ensinou_exatamente_vale_o_dele(com_dicionarios):  # noqa: F811
    com_dicionarios.ensinar("Lugarejo, vila, povoado.", pergunta="sinônimos de vilarejo")
    tipo, resposta = texto(com_dicionarios, "sinônimos de vilarejo")
    assert tipo == "conhecimento" and "Lugarejo" in resposta
