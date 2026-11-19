"""Padrões de frase (2.0): a estrutura da frase diz o conceito; as lacunas são exemplos."""

import pytest

from aprendiz import addons as pacotes
from aprendiz import recursos
from aprendiz.core.padroes import Padroes
from aprendiz.linguagem.normalizador import normalizar

PADROES = [
    {"padrao": "quantos|quantas * cada|por *", "conceitos": ["agrupar", "contar"]},
    {"padrao": "os|as <n> * mais *", "conceitos": ["limitar", "primeiros"]},
    {"padrao": "jogar fora os|as *", "conceitos": ["apagar"]},
]


def pacote_padroes():
    compreensao = recursos.validar_compreensao({"padroes": PADROES}, normalizar)
    return pacotes.criar_pacote({"id": "padroes-teste", "nome": "Padrões", "versao": "1.0.0",
                                 "autor": "t"}, compreensao=compreensao)


def test_lacunas_sao_exemplos_e_os_conceitos_entram(assistente):
    assistente.instalar_addon(pacote_padroes())
    leitura = assistente.padroes.ler(normalizar("Quantos pedidos cada cliente fez?"))
    assert leitura.exemplos == ["pedidos", "cliente"]
    assert leitura.texto == "quantos cada fez agrupar contar"
    leitura = assistente.padroes.ler(normalizar("só os 3 produtos mais caros"))
    assert leitura.conceitos == ["limitar", "primeiros"] and "produtos" in leitura.exemplos
    assert assistente.padroes.ler("o que e null") is None


def test_pergunta_com_padrao_acha_pelo_conceito(assistente):
    assistente.ensinar("Use GROUP BY para agrupar e COUNT para contar.", pergunta="como agrupar e contar")
    assistente.ensinar("Os pedidos ficam na tabela pedidos, ligados aos clientes.",
                       pergunta="onde ficam os pedidos dos clientes")
    assistente.instalar_addon(pacote_padroes())
    r = assistente.responder("quantos pedidos cada cliente fez?")
    assert "GROUP BY" in r["mensagem"]["texto"]                    # não o banco de pedidos
    etapas = r["mensagem"]["meta"]["explicacao"]["etapas"]
    assert any(e["nome"] == "Padrão de frase" for e in etapas)


def test_sem_resposta_pela_reescrita_fica_a_pergunta_original(assistente):
    assistente.ensinar("Os pedidos ficam na tabela pedidos.", pergunta="onde ficam os pedidos")
    antes = assistente.responder("jogar fora os pedidos")["mensagem"]["texto"]
    assistente.instalar_addon(pacote_padroes())
    r = assistente.responder("jogar fora os pedidos")
    etapa = next(e for e in r["mensagem"]["meta"]["explicacao"]["etapas"]
                 if e["nome"] == "Padrão de frase")
    assert etapa["dados"]["encontrou"] == 0             # nada sobre apagar na base
    assert r["mensagem"]["texto"] == antes              # então a pergunta não é trocada


@pytest.mark.parametrize("ruim", [
    [{"padrao": "* *", "conceitos": ["x"]}],                       # só lacunas
    [{"padrao": "quantos *", "conceitos": []}],                    # sem conceito
    [{"padrao": "quantos *", "conceitos": ["x"], "outra": 1}],     # chave estranha
    [{"padrao": "quan@tos|x *", "conceitos": ["x"]}],              # peça que vira duas palavras
])
def test_padrao_invalido_e_recusado(ruim):
    with pytest.raises(recursos.ErroRecurso):
        recursos.validar_compreensao({"padroes": ruim}, normalizar)


def test_sem_addon_nao_ha_padroes(banco):
    assert Padroes(banco).ler("quantos pedidos cada cliente fez") is None


def test_padrao_mais_especifico_vence(assistente):
    compreensao = recursos.validar_compreensao({"padroes": [
        {"padrao": "colocar um|uma|o|a * no|na *", "conceitos": ["inserir"]},
        {"padrao": "colocar * no ar", "conceitos": ["publicar"]},
    ]}, normalizar)
    assistente.instalar_addon(pacotes.criar_pacote(
        {"id": "padroes-x", "nome": "P", "versao": "1.0.0", "autor": "t"}, compreensao=compreensao))
    leitura = assistente.padroes.ler("colocar o sistema no ar")
    assert leitura.conceitos == ["publicar"]          # "ar" é fixo num e lacuna no outro
    assert assistente.padroes.ler("colocar o cliente na tabela").conceitos == ["inserir"]
