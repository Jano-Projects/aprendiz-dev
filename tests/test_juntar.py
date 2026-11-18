"""
Testes de "juntar e reinterpretar" (1.0): panorama ("o que você sabe sobre X?"),
pedido composto ("A e B?") e busca só pelo assunto ("quero fazer um bolo").
"""

from aprendiz import addons as pacotes
from aprendiz import recursos
from aprendiz.linguagem import normalizar

COMPREENSAO = {
    "tipos_pergunta": [
        {"tipo": "panorama", "gatilhos": ["o que voce sabe sobre", "tem algo sobre"]},
        {"tipo": "pedido", "gatilhos": ["quero", "me fala"]},
        {"tipo": "escolha", "gatilhos": ["qual"]},
    ],
}


def _preparar(assistente):
    assistente.instalar_addon(pacotes.criar_pacote(
        {"id": "compreensao-teste", "nome": "c", "versao": "1.0.0"},
        compreensao=recursos.validar_compreensao(COMPREENSAO, normalizar)))
    assistente.ensinar("A senha do wifi é casa123.", pergunta="senha do wifi")
    assistente.ensinar("8h às 20h.", pergunta="horário da farmácia")
    assistente.ensinar("Levar o carro na revisão em março.")
    assistente.ensinar("Trocar o óleo a cada 10 mil km.", pergunta="óleo do carro")
    return assistente


def _resp(assistente, texto):
    return assistente.responder(texto, busca="hibrido")["mensagem"]


def test_panorama_junta_tudo_sobre_o_assunto(assistente):
    r = _resp(_preparar(assistente), "o que você sabe sobre o carro?")
    assert r["meta"]["tipo"] == "conhecimento"
    assert "revisão" in r["texto"] and "10 mil km" in r["texto"]
    assert len(r["meta"]["fontes"]) == 2


def test_panorama_sem_nada_diz_que_nao_sabe(assistente):
    r = _resp(_preparar(assistente), "tem algo sobre astronomia?")
    assert r["meta"]["tipo"] == "desconhecido"


def test_pedido_composto_responde_as_duas_partes(assistente):
    r = _resp(_preparar(assistente), "qual a senha do wifi e o horário da farmácia?")
    assert "casa123" in r["texto"] and "8h às 20h" in r["texto"]


def test_pedido_composto_parcial_diz_o_que_faltou(assistente):
    r = _resp(_preparar(assistente), "qual a senha do wifi e qual a capital da frança?")
    assert "casa123" in r["texto"] and "Ainda não fui ensinado sobre" in r["texto"]


def test_pergunta_simples_nao_vira_composta(assistente):
    r = _resp(_preparar(assistente), "qual a senha do wifi?")
    assert r["texto"] == "A senha do wifi é casa123."
