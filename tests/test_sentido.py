"""A resposta precisa falar do assunto da pergunta (2.0)."""

import pytest


def ensinar_sql(assistente):
    assistente.ensinar("O LEFT JOIN mantém todas as linhas: SELECT c.nome FROM clientes c "
                       "LEFT JOIN pedidos p ON p.cliente_id = c.id; as linhas sem par começam "
                       "com ponto de partida nulo.", pergunta="o que é left join")


def test_letra_solta_no_texto_nao_responde(assistente):
    ensinar_sql(assistente)
    r = assistente.responder("o que é um ponteiro em C?")
    assert r["mensagem"]["meta"]["tipo"] == "desconhecido"   # "c" e "ponto" não bastam
    assert "left join" not in r["mensagem"]["texto"]         # nem como sugestão


def test_palavra_curta_que_e_o_assunto_responde(assistente):
    ensinar_sql(assistente)
    assistente.ensinar("C é uma linguagem de programação compilada.", pergunta="o que é c")
    r = assistente.responder("o que é c?")
    assert r["mensagem"]["texto"] == "C é uma linguagem de programação compilada."


def test_flexao_da_palavra_forte_ainda_responde(assistente):
    assistente.ensinar("Índices aceleram as buscas.", pergunta="para que servem os índices")
    assert assistente.responder("o que é um índice?")["mensagem"]["texto"] == \
        "Índices aceleram as buscas."


def test_assunto_conhecido_nao_vira_conversa_social(assistente):
    assistente.ensinar("Um banco de dados guarda informações organizadas.",
                       pergunta="o que é banco de dados")
    r = assistente.responder("me fala de banco de dados")
    assert r["mensagem"]["meta"]["tipo"] != "social"
    assert "guarda informações" in r["mensagem"]["texto"]


def test_palavra_so_no_texto_precisa_de_todas(assistente):
    assistente.ensinar("Um algoritmo é como a receita de um bolo: passos em ordem.",
                       pergunta="o que é um algoritmo")
    r = assistente.responder("como fazer bolo de cenoura")
    assert "receita de um bolo" not in r["mensagem"]["texto"]   # "bolo" sozinho não basta


def test_correcao_prefere_o_par_que_existe_na_base(assistente):
    assistente.ensinar("O group by agrupa linhas iguais.", pergunta="o que faz o group by")
    assistente.ensinar("Um grupo de estudo se reúne às terças.", pergunta="quando o grupo se reúne")
    for _ in range(3):   # sempre igual, seja qual for a ordem interna dos conjuntos
        r = assistente.responder("pra que serve o grup by")
        assert r["mensagem"]["texto"] == "O group by agrupa linhas iguais."


@pytest.mark.parametrize("busca", [
    "bm25",
    # 2.6: a Calibrada vê o "melhor_assunto" no item da chave estrangeira, mas
    # numa base de dois itens a posição nas listas da BM25 e do TF-IDF pesa
    # mais. Falha conhecida, para resolver no treino (não esconder no teste).
    pytest.param("calibrado", marks=pytest.mark.xfail(reason="Calibrada prefere quem só cita",
                                                      strict=False)),
])
def test_quem_e_o_assunto_vence_quem_so_cita(assistente, busca):
    from aprendiz.addons.pacote import criar_pacote
    itens = [
        {"pergunta": "o que é join", "conteudo": "O JOIN junta tabelas pela chave estrangeira.",
         "teia": {"ref": "join", "assuntos": ["join", "chave estrangeira"], "porques": [], "raiz": False}},
        {"pergunta": "o que é chave estrangeira", "conteudo": "Uma coluna que aponta para outra tabela.",
         "teia": {"ref": "fk", "assuntos": ["fk"], "porques": [], "raiz": False}},
    ]
    assistente.instalar_addon(criar_pacote({"id": "bd-teste", "nome": "BD", "versao": "1.0.0",
                                            "autor": "t"}, itens, {}))
    r = assistente.responder("por que usar chave estrangeira?", busca=busca)
    assert r["mensagem"]["texto"] == "Uma coluna que aponta para outra tabela."


def test_gerundio_casa_com_infinitivo_mas_radical_solto_nao():
    from aprendiz.core.assistente import _parecida
    assert _parecida("dividindo", {"dividir", "metade"})
    assert _parecida("ordenando", {"ordenar"})
    assert not _parecida("ligacoes", {"lista", "ligada"})      # sentidos diferentes
    assert not _parecida("ponteiro", {"ponto"})


def _addon_com_teia(assistente, itens, id_="tutorial"):
    from aprendiz.addons.pacote import criar_pacote
    assistente.instalar_addon(criar_pacote({"id": id_, "nome": "T", "versao": "1.0.0", "autor": "t"},
                                           itens, {}))


def test_fragmento_com_teia_precisa_bater_no_assunto(assistente):
    _addon_com_teia(assistente, [{
        "pergunta": "mini aprendiz passo 6",
        "conteudo": "Ensine algo como: qual a capital da frança? Paris.",
        "teia": {"ref": "passo-6", "assuntos": ["mini aprendiz"], "porques": [], "raiz": False}}])
    r = assistente.responder("qual a capital da frança")
    assert "Paris" not in r["mensagem"]["texto"]     # só cita a frase de exemplo


def test_palavra_curta_nao_casa_pelo_comeco_de_outra():
    from aprendiz.core.assistente import _parecida
    assert not _parecida("valeu", {"vale", "mais"}, False)   # palavra que existe: sem digitação
    assert _parecida("indices", {"indice"})
