"""
Testes da compreensão (0.7): addons "compreensao" e "vetores".

Os addons de verdade (loja oficial) são grandes; aqui montamos versões
pequenas, com os mesmos formatos, para testar cada peça do motor.
"""

import struct

import pytest
from fastapi.testclient import TestClient

from aprendiz.addons import pacote as pacotes
from aprendiz.aplicativo import config
from aprendiz.addons import recursos
from aprendiz.api import criar_app, servidor
from aprendiz.linguagem import normalizar

COMPREENSAO = {
    "expressoes": {"dar um jeito": "resolver", "palavra passe": "senha"},
    "tipos_pergunta": [
        {"tipo": "definicao", "gatilhos": ["o que e", "o que significa"]},
        {"tipo": "procedimento", "gatilhos": ["como faco para", "como"]},
        {"tipo": "localizacao", "gatilhos": ["onde fica", "onde"]},
    ],
    "autoconhecimento": [
        {"id": "versao", "perguntas": ["qual a sua versao"], "funcao": "versao"},
        {"id": "ia", "perguntas": ["voce e uma ia"], "resposta": "Sou PLN clássico."},
        {"id": "quem-sou", "perguntas": ["qual o seu nome"], "resposta": "Sou o Aprendiz."},
    ],
    "fora_de_alcance": [
        {"tema": "clima", "gatilhos": ["previsao do tempo"], "resposta": "Não sei o clima."},
    ],
    "necessidades": [
        {"gatilhos": ["estou com fome"], "palavras": ["receita", "cozinha"]},
    ],
    "catalogo": [
        {"id": "girias-angola", "nome": "Gírias de Angola", "descricao": "Kota, kamba…",
         "palavras": ["angola", "kota", "kamba", "kumbu"]},
        {"id": "receitas", "nome": "Receitas", "descricao": "Receitas de cozinha.",
         "palavras": ["receita", "bolo", "cozinha", "forno"]},
    ],
}
LEMAS = [("fiz", "fazer"), ("fez", "fazer"), ("fizemos", "fazer"), ("carro", ""), ("bicicleta", ""),
         ("moto", ""), ("chuva", "")]


def manifesto(id_, **extra):
    return {"id": id_, "nome": id_, "versao": "1.0.0", "origem": "oficial",
            "editor": "Jano Projects", **extra}


def pacote_compreensao(**trocas) -> bytes:
    return pacotes.criar_pacote(manifesto("compreensao-teste"),
                                compreensao=recursos.validar_compreensao(
                                    {**COMPREENSAO, **trocas}, normalizar),
                                lemas=LEMAS)


def vetores_teste() -> recursos.Vetores:
    """Quatro vetores de 8 dimensões: moto ≈ bicicleta; chuva bem diferente."""
    linhas = [
        [127, 0, 0, 0, 0, 0, 0, 0],    # 0 bicicleta
        [120, 30, 0, 0, 0, 0, 0, 0],   # 1 moto
        [0, 0, 127, 0, 0, 0, 0, 0],    # 2 chuva
        [0, 0, 0, 127, 0, 0, 0, 0],    # 3 gaveta
    ]
    dados = b"".join(struct.pack("8b", *l) for l in linhas)
    palavras = [("bicicleta", 0), ("moto", 1), ("chuva", 2), ("gaveta", 3), ("motoca", 1)]
    return recursos.Vetores(dimensoes=8, quantidade=4, palavras=palavras, dados=dados)


def pacote_vetores() -> bytes:
    return pacotes.criar_pacote(manifesto("vetores-teste"), vetores=vetores_teste())


# ------------------------------------------------------------------ formato
def test_pacote_de_compreensao_e_lido_e_classificado():
    p = pacotes.ler_pacote(pacote_compreensao())
    assert p.manifesto["classificacao"] == ["compreensao"]
    assert p.compreensao["expressoes"]["dar um jeito"] == "resolver"
    assert ("fiz", "fazer") in p.lemas and ("carro", "") in p.lemas
    assert pacotes.resumo(p)["totais"]["lemas"] == len(LEMAS)


def test_vetores_ida_e_volta():
    p = pacotes.ler_pacote(pacote_vetores())
    assert p.manifesto["classificacao"] == ["vetores"]
    assert p.vetores.dimensoes == 8 and p.vetores.quantidade == 4
    assert ("motoca", 1) in p.vetores.palavras


@pytest.mark.parametrize("ruim, trecho", [
    ({"tipos_pergunta": [{"tipo": "regex", "gatilhos": ["x"]}]}, "tipo"),
    ({"autoconhecimento": [{"id": "xx", "perguntas": ["oi"], "funcao": "apagar_tudo"}]}, "funcao"),
    ({"autoconhecimento": [{"id": "xx", "perguntas": ["oi"]}]}, "funcao' OU"),
    ({"expressoes": {"sozinha": "outra"}}, "duas palavras"),
    ({"codigo": "import os"}, "desconhecidas"),
    ({"catalogo": [{"id": "../fora", "nome": "x", "palavras": ["a"]}]}, "id"),
])
def test_compreensao_invalida_e_recusada(ruim, trecho):
    with pytest.raises(recursos.ErroRecurso, match=trecho):
        recursos.validar_compreensao(ruim, normalizar)


def test_lemas_so_aceitam_palavras_normalizadas():
    with pytest.raises(recursos.ErroRecurso, match="linha 1"):
        recursos.validar_lemas("Fui\tser\n".encode())
    assert recursos.validar_lemas(b"# comentario\nfui\tser\ncarro\n") == [("fui", "ser"), ("carro", "")]


def test_vetores_corrompidos_sao_recusados():
    bruto = vetores_teste().como_bytes()
    with pytest.raises(recursos.ErroRecurso):
        recursos.validar_vetores(bruto[:-1])            # tamanho não bate
    with pytest.raises(recursos.ErroRecurso):
        recursos.validar_vetores(b"XXXXXXXX" + bruto[8:])  # assinatura errada


def test_lemas_sem_compreensao_sao_recusados():
    import io
    import json
    import zipfile
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("manifesto.json", json.dumps({**manifesto("x1"), "formato": 2,
                                                 "classificacao": ["memoria"]}))
        z.writestr("conhecimentos.json", json.dumps([{"conteudo": "oi"}]))
        z.writestr("lemas.tsv", "fui\tser\n")
    with pytest.raises(pacotes.ErroAddon, match="lemas.tsv"):
        pacotes.ler_pacote(buffer.getvalue())


# ------------------------------------------------------------------ linguagem
def test_lemas_unem_formas_irregulares_e_reindexam(assistente):
    assistente.ensinar("Na sala 3.", pergunta="onde eu fiz a prova")
    # Sem o addon, "fez" e "fiz" têm radicais diferentes.
    assert "fiz" not in assistente.linguagem.processar("fez").lemas
    assistente.instalar_addon(pacote_compreensao())
    consulta = assistente.linguagem.processar("onde ele fez a prova")
    assert consulta.lemas == {"fez": "fazer"}
    assert assistente.responder("onde ele fez a prova?")["mensagem"]["texto"] == "Na sala 3."
    # A base foi reindexada com os lemas...
    texto = assistente.banco.todos_conhecimentos()[0]["texto_busca"]
    assert "fiz" not in texto.split()
    # ...e volta ao normal quando o addon é desativado.
    assistente.definir_addon_ativo("compreensao-teste", False)
    assert "fiz" in assistente.banco.todos_conhecimentos()[0]["texto_busca"].split()


def test_expressoes_viram_uma_palavra(assistente):
    assistente.instalar_addon(pacote_compreensao())
    p = assistente.linguagem.processar("qual a palavra-passe do wifi")
    assert p.expressoes == {"palavra passe": "senha"} and "senha" in p.tokens


def test_lexico_protege_palavras_reais_da_correcao(assistente):
    assistente.ensinar("Muito caro.", pergunta="preço do caro")
    assert assistente.linguagem.processar("carro").correcoes == {"carro": "caro"}
    assistente.instalar_addon(pacote_compreensao())
    assert assistente.linguagem.processar("carro").correcoes == {}


# ------------------------------------------------------------------ pipeline
def test_autoconhecimento_dinamico_e_fixo(assistente):
    assistente.instalar_addon(pacote_compreensao())
    r = assistente.responder("qual a sua versão?")["mensagem"]
    assert r["meta"]["tipo"] == "autoconhecimento" and config.VERSAO in r["texto"]
    assert assistente.responder("você é uma IA?")["mensagem"]["texto"] == "Sou PLN clássico."


@pytest.mark.parametrize("mensagem", [
    "Mas você tem nome?",            # marcador "mas" + palavras-chave
    "Você tem nome?",                # palavras-chave {nome} + 2ª pessoa
    "Mas e aí, qual é o seu nome?",  # vários marcadores no começo
])
def test_autoconhecimento_aceita_variacoes(assistente, mensagem):
    assistente.instalar_addon(pacote_compreensao())
    r = assistente.responder(mensagem)["mensagem"]
    assert r["meta"]["tipo"] == "autoconhecimento" and r["texto"] == "Sou o Aprendiz."


@pytest.mark.parametrize("mensagem", ["nome de cachorro", "você tem nome de cachorro para sugerir?"])
def test_autoconhecimento_nao_sequestra_outros_assuntos(assistente, mensagem):
    assistente.instalar_addon(pacote_compreensao())
    assert assistente.responder(mensagem)["mensagem"]["meta"]["tipo"] != "autoconhecimento"


def test_dono_vence_o_autoconhecimento(assistente):
    assistente.instalar_addon(pacote_compreensao())
    assistente.ensinar("Sou a versão do Victor.", pergunta="qual a sua versão")
    assert assistente.responder("qual a sua versão")["mensagem"]["texto"] == "Sou a versão do Victor."


def test_fora_de_alcance_so_quando_nao_ha_resposta(assistente):
    assistente.instalar_addon(pacote_compreensao())
    r = assistente.responder("qual a previsão do tempo?")["mensagem"]
    assert r["meta"]["tipo"] == "limite" and r["texto"] == "Não sei o clima."
    assistente.ensinar("Veja no app do celular.", pergunta="previsão do tempo")
    assert assistente.responder("previsão do tempo")["mensagem"]["texto"] == "Veja no app do celular."


def test_tipo_de_pergunta_deixa_o_nao_sei_mais_preciso(assistente):
    assistente.instalar_addon(pacote_compreensao())
    r = assistente.responder("o que é fotossíntese?")["mensagem"]
    assert "o que é **fotossíntese**" in r["texto"]
    etapa = next(e for e in r["meta"]["explicacao"]["etapas"] if e["nome"] == "Compreensão")
    assert etapa["dados"]["assunto"] == "fotossíntese"


def test_recomenda_addon_da_loja_ou_ativar(assistente):
    assistente.instalar_addon(pacote_compreensao())
    r = assistente.responder("o que significa kota?")["mensagem"]["meta"]
    assert r["recomendacao"]["id"] == "girias-angola" and r["recomendacao"]["acao"] == "loja"
    # Necessidade deduzida: "estou com fome" → receitas
    r = assistente.responder("estou com fome")["mensagem"]["meta"]
    assert r["recomendacao"]["id"] == "receitas"
    # Instalado mas desativado → sugere ativar
    assistente.instalar_addon(pacotes.criar_pacote(
        manifesto("girias-angola"), [{"tipo": "verbete", "pergunta": "kota",
                                      "conteudo": "Pessoa mais velha."}]))
    assistente.definir_addon_ativo("girias-angola", False)
    r = assistente.responder("o que significa kota?")["mensagem"]["meta"]
    assert r["recomendacao"]["acao"] == "ativar"
    # Ativo: responde e não recomenda nada
    assistente.definir_addon_ativo("girias-angola", True)
    r = assistente.responder("o que significa kota?")["mensagem"]
    assert "recomendacao" not in r["meta"] and "mais velha" in r["texto"]


def test_sem_compreensao_nada_muda(assistente):
    r = assistente.responder("o que significa kota?")["mensagem"]
    assert "recomendacao" not in r["meta"]
    assert all(e["nome"] != "Compreensão" for e in r["meta"]["explicacao"]["etapas"])


def test_busca_por_sentido_com_vetores(assistente):
    assistente.ensinar("Fica na garagem.", pergunta="bicicleta")
    assistente.instalar_addon(pacote_compreensao())
    assert assistente.responder("moto")["mensagem"]["meta"]["tipo"] == "desconhecido"
    assistente.instalar_addon(pacote_vetores())
    r = assistente.responder("moto")["mensagem"]
    assert r["meta"]["tipo"] == "conhecimento"
    assert "moto → bicicleta" in r["texto"] and "garagem" in r["texto"]
    # "chuva" não tem sentido próximo de nada da base: não inventa.
    assert assistente.responder("chuva")["mensagem"]["meta"]["tipo"] == "desconhecido"


def test_apelidos_de_vetor_valem_menos(assistente):
    assistente.instalar_addon(pacote_compreensao())
    assistente.instalar_addon(pacote_vetores())
    lexico = assistente.linguagem.lexico
    assert lexico.vetor_info("moto")[1] is False
    assert lexico.vetor_info("motoca")[1] is True          # empresta o vetor de "moto"
    assert lexico.vetor("motoca", apelidos=False) is None


def test_pergunta_com_assunto_nao_vira_cumprimento(assistente):
    assistente.ensinar("Ctrl+A seleciona tudo.", pergunta="como selecionar tudo no windows")
    assistente.instalar_addon(pacote_compreensao())
    r = assistente.responder("como selecionar tudo no windows")["mensagem"]
    assert r["texto"] == "Ctrl+A seleciona tudo."


def test_remover_addon_apaga_o_lexico(assistente):
    assistente.instalar_addon(pacote_compreensao())
    assistente.instalar_addon(pacote_vetores())
    assistente.remover_addon("compreensao-teste")
    assistente.remover_addon("vetores-teste")
    assert assistente.banco._consultar("SELECT COUNT(*) AS n FROM addon_lexico")[0]["n"] == 0
    assert assistente.banco._consultar("SELECT COUNT(*) AS n FROM addon_recursos")[0]["n"] == 0
    assert assistente.linguagem.processar("fez").lemas == {}


# ------------------------------------------------------------------ loja
def test_loja_abre_filtrada_no_addon_recomendado(tmp_path, monkeypatch):
    abertos = []
    monkeypatch.setattr(servidor.webbrowser, "open", lambda url, new=0: abertos.append(url) or True)
    with TestClient(criar_app(tmp_path / "api.db")) as c:
        r = c.post("/api/loja-oficial", json={"addon": "girias-angola"})
        assert r.json()["url"] == config.URL_LOJA_OFICIAL + "?busca=girias-angola"
        assert c.post("/api/loja-oficial", json={"addon": "https://falso.example"}).status_code == 400
    assert abertos == [config.URL_LOJA_OFICIAL + "?busca=girias-angola"]
