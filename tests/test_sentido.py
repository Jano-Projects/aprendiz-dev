"""A resposta precisa falar do assunto da pergunta (2.0)."""


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
