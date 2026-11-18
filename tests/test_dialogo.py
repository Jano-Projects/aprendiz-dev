"""
Testes do diálogo (0.9): a seção "dialogo" dos addons de compreensão e a
herança de grupo dos addons de apoio.

Como em test_compreensao.py, montamos addons pequenos com os mesmos
formatos dos addons da loja.
"""

import pytest

from aprendiz import addons as pacotes
from aprendiz import recursos
from aprendiz.linguagem import normalizar

DIALOGO = {
    "aberturas": {"ola": "Olá!", "bom dia": "Bom dia!", "tudo bem": "Tudo bem por aqui!"},
    "conversa": ["conseguir", "consegue", "ajudar", "explicar", "pode", "coisa", "voce",
                 "fazer", "isso", "hoje"],
    "sem_assunto": ["Estou aqui! O que você quer saber?"],
    "continuacoes": ["e em", "e no", "e o", "e a"],
    "atos": [
        {"id": "crise", "acao": "crise", "gatilhos": ["quero morrer"],
         "respostas": ["Ligue 188 (CVV)."]},
        {"id": "pedido-ajuda", "acao": "convidar",
         "gatilhos": ["consegue me ajudar", "pode me explicar"],
         "respostas": ["Claro! O que você quer saber?"],
         "assunto_vago": ["Qual {assunto}?"]},
        {"id": "travado", "acao": "convidar", "gatilhos": ["estou perdido"],
         "respostas": ["Me conte o que está acontecendo."]},
        {"id": "desabafo", "acao": "acolher", "gatilhos": ["estou triste"],
         "respostas": ["Sinto muito. Quer me contar?"]},
        {"id": "como-voce-esta", "acao": "responder", "gatilhos": ["tudo bem com voce"],
         "respostas": ["Tudo certo por aqui!"]},
        {"id": "opiniao", "acao": "opinar", "gatilhos": ["o que voce acha"],
         "respostas": ["Não tenho opinião sobre {assunto}."],
         "sem_assunto": ["Não tenho opinião própria."]},
        {"id": "reflexao", "acao": "refletir", "gatilhos": ["sentido da vida"],
         "respostas": ["Pergunta antiga, sem resposta minha."]},
        {"id": "nao-entendi", "acao": "reformular", "gatilhos": ["nao entendi"],
         "respostas": ["Diga qual parte."]},
        {"id": "nao-era-isso", "acao": "outras_opcoes", "gatilhos": ["nao era isso"],
         "respostas": ["Diga de outro jeito."]},
        {"id": "sim", "acao": "confirmar", "gatilhos": ["sim", "isso"],
         "respostas": ["Certo!"]},
        {"id": "nao", "acao": "negar", "gatilhos": ["nao"], "respostas": ["Tudo bem!"]},
    ],
}
TIPOS = [{"tipo": "definicao", "gatilhos": ["o que significa", "o que e"]}]


def manifesto(id_, **extra):
    return {"id": id_, "nome": id_, "versao": "1.0.0", "origem": "oficial",
            "editor": "Jano Projects", **extra}


def pacote_dialogo(**extra) -> bytes:
    compreensao = recursos.validar_compreensao(
        {"tipos_pergunta": TIPOS, "dialogo": DIALOGO}, normalizar)
    return pacotes.criar_pacote(manifesto("dialogo-teste", **extra), compreensao=compreensao)


@pytest.fixture
def com_dialogo(assistente_ensinado):
    assistente_ensinado.ensinar("Ajudei-lhe é o uso angolano; a norma pede ajudei-o.",
                                pergunta="ajudei-lhe ou ajudei-o")
    assistente_ensinado.instalar_addon(pacote_dialogo())
    return assistente_ensinado


def texto(assistente, mensagem, conversa=None):
    r = assistente.responder(mensagem, conversa)
    return r["mensagem"]["texto"], r["mensagem"]["meta"]["tipo"], r["conversa_id"]


# ---------------------------------------------------------------- validação
def test_valida_secao_dialogo():
    saida = recursos.validar_compreensao({"dialogo": DIALOGO}, normalizar)
    assert saida["dialogo"]["atos"][1]["gatilhos"] == ["consegue me ajudar", "pode me explicar"]
    assert saida["dialogo"]["aberturas"]["ola"] == "Olá!"


@pytest.mark.parametrize("trocar, mensagem", [
    ({"atos": [{"id": "xx", "acao": "executar", "gatilhos": ["oi"], "respostas": ["a"]}]}, "acao"),
    ({"atos": [{"id": "xx", "acao": "responder", "gatilhos": ["oi"], "respostas": []}]}, "respostas"),
    ({"desconhecida": 1}, "chaves desconhecidas"),
])
def test_recusa_dialogo_invalido(trocar, mensagem):
    with pytest.raises(recursos.ErroRecurso, match=mensagem):
        recursos.validar_compreensao({"dialogo": {**DIALOGO, **trocar}}, normalizar)


def test_sem_dialogo_continua_compativel_com_versoes_antigas():
    """Um compreensao.json sem diálogo não ganha a chave "dialogo" (0.7 e 0.8 a recusariam)."""
    saida = recursos.validar_compreensao({"tipos_pergunta": TIPOS}, normalizar)
    assert "dialogo" not in saida


# ---------------------------------------------------------------- atos de fala
def test_cumprimento_e_pedido_sem_assunto_nao_busca(com_dialogo):
    """O caso que motivou o diálogo: "ajudar" achava "ajudei-lhe" na base."""
    resposta, tipo, _ = texto(com_dialogo, "Olá, consegue me ajudar?")
    assert resposta == "Olá! Claro! O que você quer saber?"
    assert tipo == "dialogo"


def test_pedido_com_assunto_segue_para_a_busca(com_dialogo):
    resposta, tipo, _ = texto(com_dialogo, "consegue me ajudar com a senha do wifi?")
    assert "casa123" in resposta and tipo == "conhecimento"


def test_pedido_com_assunto_vago_pergunta_qual(com_dialogo):
    resposta, _, _ = texto(com_dialogo, "consegue me ajudar com uma senha?")
    assert resposta == "Qual senha?"


def test_cumprimento_com_pergunta(com_dialogo):
    resposta, tipo, _ = texto(com_dialogo, "Bom dia! qual o horário da farmácia?")
    assert resposta.startswith("Bom dia! ") and "8h às 20h" in resposta
    assert tipo == "conhecimento"


def test_ato_inteiro_vence_o_cumprimento(com_dialogo):
    assert texto(com_dialogo, "tudo bem com você?")[0] == "Tudo certo por aqui!"


def test_gatilho_com_palavras_no_meio(com_dialogo):
    resposta, tipo, _ = texto(com_dialogo, "estou meio perdido hoje")
    assert resposta == "Me conte o que está acontecendo." and tipo == "dialogo"


def test_desabafo_e_crise(com_dialogo):
    assert texto(com_dialogo, "estou triste com o carro")[0] == "Sinto muito. Quer me contar?"
    assert texto(com_dialogo, "às vezes eu quero morrer")[0] == "Ligue 188 (CVV)."


def test_so_palavras_de_conversa_nao_dispara_busca(com_dialogo):
    resposta, tipo, _ = texto(com_dialogo, "consegue fazer isso?")
    assert resposta == "Estou aqui! O que você quer saber?" and tipo == "dialogo"


def test_opiniao_mostra_o_que_sabe(com_dialogo):
    resposta, tipo, _ = texto(com_dialogo, "o que você acha da senha do wifi?")
    assert resposta.startswith("Não tenho opinião sobre senha do wifi.")
    assert "casa123" in resposta and tipo == "conhecimento"


def test_reflexao_so_quando_a_base_nao_cobre_o_assunto(com_dialogo):
    assert texto(com_dialogo, "qual o sentido da vida?")[0] == "Pergunta antiga, sem resposta minha."
    com_dialogo.ensinar("Para mim, o sentido da vida é cuidar de quem amo.",
                        pergunta="sentido da vida")
    assert "cuidar de quem amo" in texto(com_dialogo, "qual o sentido da vida?")[0]


def test_o_que_o_dono_ensinou_vale_mais(com_dialogo):
    com_dialogo.ensinar("Faço, sim: é só pedir.", pergunta="consegue fazer isso")
    assert texto(com_dialogo, "consegue fazer isso?")[0] == "Faço, sim: é só pedir."


def test_sem_addon_de_dialogo_nada_muda(assistente_ensinado):
    assert not assistente_ensinado.dialogo.ativo
    assert assistente_ensinado.responder("estou perdido")["mensagem"]["meta"]["tipo"] != "dialogo"


# ---------------------------------------------------------------- contexto
def test_nao_entendi_mostra_o_texto_inteiro(com_dialogo):
    # A Extrativa resume o trecho; "não entendi" mostra o texto inteiro.
    conversa = com_dialogo.responder("quando trocar o óleo do carro?",
                                     resposta="extrativa")["conversa_id"]
    anterior = com_dialogo.banco.listar_mensagens(conversa)[-1]
    resposta, tipo, _ = texto(com_dialogo, "não entendi", conversa)
    if "calibragem" in anterior["texto"]:   # a Extrativa já mostrou tudo
        assert "já era o texto inteiro" in resposta
    else:
        assert "texto completo" in resposta and "calibragem" in resposta
        assert tipo == "conhecimento"


def test_nao_entendi_quando_ja_era_tudo(com_dialogo):
    _, _, conversa = texto(com_dialogo, "senha do wifi")
    resposta, _, _ = texto(com_dialogo, "não entendi", conversa)
    assert resposta.startswith("Diga qual parte.") and "já era o texto inteiro" in resposta


def test_nao_entendi_sem_conversa(com_dialogo):
    assert texto(com_dialogo, "não entendi")[0] == "Diga qual parte."


def test_continuacao_troca_o_lugar(com_dialogo):
    _, _, conversa = texto(com_dialogo, "qual o horário da farmácia?")
    resposta, _, _ = texto(com_dialogo, "e no domingo?", conversa)
    assert "Entendi: “qual o horário da farmácia no domingo”" in resposta
    assert "8h às 20h" in resposta


def test_continuacao_troca_o_assunto(com_dialogo):
    com_dialogo.instalar_addon(pacotes.criar_pacote(
        manifesto("compreensao-teste"),
        compreensao=recursos.validar_compreensao({"tipos_pergunta": TIPOS}, normalizar)))
    _, _, conversa = texto(com_dialogo, "o que é a senha do wifi?")
    assert (com_dialogo.dialogo.continuar(["e", "o", "farmacia"], "e o farmácia?",
                                          "o que é a senha do wifi?", com_dialogo.compreensao)
            == "o que é farmácia")
    # Se a frase já é uma pergunta que o dono ensinou, ela vale sozinha.
    resposta, _, _ = texto(com_dialogo, "e o horário da farmácia?", conversa)
    assert "8h às 20h" in resposta


def test_sim_ativa_o_addon_recomendado(com_dialogo):
    _, _, conversa = texto(com_dialogo, "qual o horário da farmácia?")
    anterior = com_dialogo.banco.listar_mensagens(conversa)[-1]
    addon = com_dialogo.instalar_addon(pacotes.criar_pacote(
        manifesto("receitas"), [{"pergunta": "bolo de cenoura", "conteudo": "Cenoura e farinha."}]))
    com_dialogo.definir_addon_ativo("receitas", False)
    meta = {**anterior["meta"], "recomendacao": {"id": "receitas", "nome": "Receitas",
                                                  "acao": "ativar"}}
    com_dialogo.banco.atualizar_meta_mensagem(anterior["id"], meta)
    resposta, _, _ = texto(com_dialogo, "sim", conversa)
    assert resposta.startswith("Ativei o addon **Receitas**.")
    assert com_dialogo.banco.obter_addon("receitas")["ativo"]
    assert addon["addon"]["id"] == "receitas"


def test_sim_e_nao_so_valem_sozinhos(com_dialogo):
    assert texto(com_dialogo, "sim")[0] == "Certo!"
    assert texto(com_dialogo, "não")[0] == "Tudo bem!"
    # "isso" no meio da frase não é um "sim".
    assert texto(com_dialogo, "consegue fazer isso?")[1] == "dialogo"


# ---------------------------------------------------------------- grupos
def _addon_recomendado(id_):
    return pacotes.criar_pacote(
        manifesto(id_, recomendado={"busca": "hibrido", "resposta": "direta"}),
        [{"pergunta": f"pergunta de {id_}", "conteudo": "Resposta."}])


def test_addons_de_apoio_herdam_o_grupo(assistente):
    for id_ in ("portugues-a", "portugues-b"):
        assistente.instalar_addon(_addon_recomendado(id_))
    compreensao = recursos.validar_compreensao({"tipos_pergunta": TIPOS}, normalizar)
    assistente.instalar_addon(pacotes.criar_pacote(
        manifesto("compreensao-teste", complementa=["portugues-a", "portugues-b"]),
        compreensao=compreensao))
    assistente.instalar_addon(pacotes.criar_pacote(
        manifesto("vetores-teste", dependencias=[{"id": "compreensao-teste", "versao": "1.0.0"}]),
        compreensao=compreensao))
    assistente.instalar_addon(pacotes.criar_pacote(
        manifesto("boas-vindas", dependencias=[{"id": "portugues-a", "versao": "1.0.0"}]),
        personalizacao={"personalizacao.boas_vindas": "Oi!"}))
    assistente.instalar_addon(pacotes.criar_pacote(
        manifesto("tema"), personalizacao={"personalizacao.cor": "#0f766e"}))

    grupos = {g["chave"]: g for g in assistente.grupos_de_addons()}
    ids = {a["id"]: a["apoio"] for a in grupos["hibrido+direta"]["addons"]}
    assert ids == {"portugues-a": False, "portugues-b": False, "compreensao-teste": True,
                   "vetores-teste": True, "boas-vindas": True}
    assert [a["id"] for a in grupos[None]["addons"]] == ["tema"]


def test_complementa_e_validado():
    assert pacotes.validar_complementa(["a-b", "a-b", "eu"], "eu") == ["a-b"]
    with pytest.raises(pacotes.ErroAddon):
        pacotes.validar_complementa(["Inválido!"], "eu")


def test_opiniao_sobre_tema_aberto_e_reflexao(com_dialogo):
    com_dialogo.dialogo._carregar()
    for ato in com_dialogo.dialogo.dados["atos"]:
        assert ato["id"] != "reflexao" or ato["gatilhos"] == ["sentido da vida"]
    resposta, tipo, _ = texto(com_dialogo, "o que você acha do sentido da vida?")
    assert resposta == "Pergunta antiga, sem resposta minha." and tipo == "dialogo"
