"""
Testes da 0.4.1: verbetes (dicionário), stopwords e intenções vindas de
addons de linguagem, e a migração dos bancos da 0.4.0.
"""

import sqlite3

import pytest

from aprendiz.addons import ErroAddon, criar_pacote, ler_pacote
from aprendiz.core import Assistente
from aprendiz.memoria import Banco
from aprendiz.memoria.banco import ESQUEMA

VERBETES = [
    {"tipo": "verbete", "pergunta": "bué", "conteudo": "**bué** (Angola): muito, bastante."},
    {"tipo": "verbete", "pergunta": "kota", "conteudo": "**kota** (Angola): pessoa mais velha."},
    {"tipo": "verbete", "pergunta": "casa de banho", "conteudo": "**casa de banho** (Portugal): banheiro."},
]
LINGUAGEM = {
    "stopwords": ["significa", "significado", "quer", "dizer"],
    "intencoes": {"saudacao": ["xe kamba"], "agradecimento": ["obrigadu barak"]},
}
MANIFESTO = {"id": "girias-teste", "nome": "Gírias", "versao": "1.0.0"}


def pacote():
    return criar_pacote(MANIFESTO, VERBETES, LINGUAGEM)


def tipo(assistente, pergunta, busca="bm25"):
    return assistente.responder(pergunta, busca=busca)["mensagem"]


# ------------------------------------------------------------------ formato
def test_linguagem_aceita_stopwords_e_intencoes():
    p = ler_pacote(pacote())
    assert p.linguagem["stopwords"] == {"significa": "", "significado": "", "quer": "", "dizer": ""}
    assert p.linguagem["intencoes"] == {"xe kamba": "saudacao", "obrigadu barak": "agradecimento"}
    assert p.conhecimentos[0]["tipo"] == "verbete"


@pytest.mark.parametrize("linguagem, trecho", [
    ({"stopwords": "significa"}, "lista de palavras"),
    ({"stopwords": ["duas palavras"]}, "uma palavra só"),
    ({"intencoes": {"hackear": ["x"]}}, "Intenção desconhecida"),
    ({"intencoes": {"saudacao": "oi"}}, "numa lista"),
])
def test_linguagem_invalida(linguagem, trecho):
    with pytest.raises(ErroAddon, match=trecho):
        criar_pacote(MANIFESTO, VERBETES, linguagem)


def test_verbete_precisa_da_palavra():
    with pytest.raises(ErroAddon, match="precisa da palavra"):
        criar_pacote(MANIFESTO, [{"tipo": "verbete", "conteudo": "sem palavra"}])


# ------------------------------------------------------------------ comportamento
@pytest.mark.parametrize("busca", ["bm25", "tfidf", "fuzzy", "hibrido"])
@pytest.mark.parametrize("pergunta, esperado", [
    ("bué", "muito"),
    ("o que significa bué?", "muito"),
    ("qual o significado de kota", "mais velha"),
    ("o que quer dizer kota", "mais velha"),
    ("significado de casa de banho", "banheiro"),
])
def test_verbete_responde_a_palavra_sozinha_ou_o_que_significa(assistente, busca, pergunta, esperado):
    assistente.instalar_addon(pacote())
    msg = tipo(assistente, pergunta, busca)
    assert msg["meta"]["tipo"] == "conhecimento" and esperado in msg["texto"]


@pytest.mark.parametrize("busca", ["bm25", "tfidf", "fuzzy", "hibrido"])
@pytest.mark.parametrize("pergunta", [
    "tem bué de gente na festa",
    "onde fica a casa de banho do shopping",
    "o que significa abacaxi",
    "casa",
])
def test_verbete_ignora_outros_contextos(assistente, busca, pergunta):
    assistente.instalar_addon(pacote())
    assert tipo(assistente, pergunta, busca)["meta"]["tipo"] == "desconhecido"


def test_stopwords_e_intencoes_valem_so_com_o_addon_ativo(assistente):
    banco = assistente.banco
    assistente.instalar_addon(pacote())
    assert "significa" in banco.lista_stopwords()
    assert "significa" not in banco.lista_stopwords(incluir_addons=False)  # tela de Linguagem
    assert tipo(assistente, "xé kamba")["meta"]["tipo"] == "social"

    assistente.definir_addon_ativo("girias-teste", False)
    assert "significa" not in banco.lista_stopwords()
    assert tipo(assistente, "bué")["meta"]["tipo"] == "desconhecido"


def test_o_que_o_dono_ensinou_continua_funcionando(assistente_ensinado):
    assistente_ensinado.instalar_addon(pacote())
    assert tipo(assistente_ensinado, "qual a senha do wifi?")["texto"].startswith("A senha")


# ------------------------------------------------------------------ migração
def test_banco_da_0_4_0_e_migrado(tmp_path):
    caminho = tmp_path / "v040.db"
    antigo = (ESQUEMA
              .replace("'pergunta', 'nota', 'trecho', 'verbete'", "'pergunta', 'nota', 'trecho'")
              .replace("'abreviacoes', 'sinonimos', 'stopwords', 'intencoes'",
                       "'abreviacoes', 'sinonimos'"))
    con = sqlite3.connect(caminho)
    con.executescript(antigo)
    con.executescript("""
        INSERT INTO meta VALUES ('versao_esquema', '4');
        INSERT INTO addons (id, nome, versao, ativo, instalado_em, hash)
            VALUES ('velho', 'Velho', '1.0.0', 1, '2026-01-01', 'x');
        INSERT INTO addon_linguagem VALUES ('velho', 'sinonimos', 'chicara', 'xicara');
        INSERT INTO conhecimentos (id, tipo, pergunta, conteudo, origem, texto_busca,
            criado_em, atualizado_em) VALUES ('a1', 'pergunta', 'senha do wifi', 'casa123',
            'chat', 'senh wifi', '2026-01-01', '2026-01-01');
        INSERT INTO conhecimentos_fts VALUES ('a1', 'senh wifi');
    """)
    con.commit()
    con.close()

    banco = Banco(caminho)
    assert banco.obter_meta("versao_esquema") == "5"
    assert banco.mapa_sinonimos()["chicara"] == "xicara"           # dados preservados
    assert banco.obter_conhecimento("a1")["conteudo"] == "casa123"
    Assistente(banco).instalar_addon(pacote())                     # CHECK novo aceita
    banco.fechar()
    Banco(caminho).fechar()                                        # idempotente


def test_mesma_palavra_em_dois_dicionarios_mostra_os_dois(assistente):
    assistente.instalar_addon(pacote())
    assistente.instalar_addon(criar_pacote(
        {"id": "girias-pt", "nome": "PT", "versao": "1.0.0"},
        [{"tipo": "verbete", "pergunta": "bué", "conteudo": "**bué** (Portugal): muito."}],
        LINGUAGEM))
    msg = tipo(assistente, "o que significa bué")
    assert "(Angola)" in msg["texto"] and "(Portugal)" in msg["texto"]
    assert len(msg["meta"]["fontes"]) == 2


@pytest.mark.parametrize("busca", ["bm25", "tfidf", "fuzzy", "hibrido"])
def test_verbete_exato_nao_perde_para_algo_parecido_do_dono(assistente_ensinado, busca):
    # "nha" (Cabo Verde) lembra "se-nha" para o Fuzzy, mas o verbete é exato.
    assistente_ensinado.instalar_addon(criar_pacote(
        MANIFESTO, [{"tipo": "verbete", "pergunta": "nha", "conteudo": "**nha**: meu, minha."}],
        LINGUAGEM))
    assert "meu, minha" in tipo(assistente_ensinado, "nha", busca)["texto"]


def test_o_dono_pode_redefinir_a_palavra(assistente):
    assistente.instalar_addon(pacote())
    assistente.ensinar("Na minha família, kota é o avô.", pergunta="kota")
    assert "avô" in tipo(assistente, "o que significa kota")["texto"]
