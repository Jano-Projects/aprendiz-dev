"""
Invariantes do assistente inteiro (2.5.1).

Coisas que precisam valer sempre, qualquer que seja o algoritmo:
determinismo, memória que se atualiza ao ensinar/esquecer, addons que
entram e saem sem deixar resto, exportação que preserva respostas e
várias threads perguntando ao mesmo tempo.
"""

import threading

import pytest

from aprendiz.addons import exportacao
from aprendiz.addons.pacote import criar_pacote
from aprendiz.algoritmos import BUSCAS, RESPOSTAS
from aprendiz.core import Assistente
from aprendiz.memoria import Banco

PERGUNTAS = [
    "qual a senha do wifi?",
    "que horas a farmácia abre?",
    "quando levar o carro na revisão?",
    "qual a calibragem dos pneus?",
    "de quanto em quanto tempo troca o óleo?",
    "quem descobriu o Brasil?",          # fora da base
]

MANIFESTO = {"id": "casa-teste", "nome": "Casa teste", "versao": "1.0.0", "autor": "Teste"}
ITENS = [
    {"pergunta": "cor do portão", "conteudo": "O portão é verde."},
    {"pergunta": "dia do lixo reciclável", "conteudo": "O reciclável passa às quintas."},
]


def texto(a, pergunta, **kw):
    return a.responder(pergunta, **kw)["mensagem"]["texto"]


# ------------------------------------------------------------ determinismo
@pytest.mark.parametrize("busca", sorted(BUSCAS))
@pytest.mark.parametrize("resposta", sorted(RESPOSTAS))
def test_mesma_pergunta_mesma_resposta(assistente_ensinado, busca, resposta):
    for p in PERGUNTAS:
        primeira = texto(assistente_ensinado, p, busca=busca, resposta=resposta)
        for _ in range(2):
            assert texto(assistente_ensinado, p, busca=busca, resposta=resposta) == primeira


def test_ordem_de_ensino_nao_muda_a_resposta(tmp_path):
    """Mesma base ensinada em ordem inversa → mesmas fontes."""
    itens = [
        ("8h às 20h, de segunda a sábado", "horário da farmácia"),
        ("A senha do wifi é casa123.", "senha do wifi"),
        ("Levar o carro na revisão em março.", None),
        ("O portão é verde.", "cor do portão"),
    ]
    resultados = []
    for nome, ordem in (("a", itens), ("b", list(reversed(itens)))):
        banco = Banco(tmp_path / f"{nome}.db")
        a = Assistente(banco)
        for conteudo, pergunta in ordem:
            a.ensinar(conteudo, pergunta=pergunta)
        resultados.append({p: texto(a, p) for p in PERGUNTAS})
        banco.fechar()
    assert resultados[0] == resultados[1]


def test_conversas_separadas_nao_se_misturam(assistente_ensinado):
    a = assistente_ensinado
    c1 = a.responder("qual a senha do wifi?")["conversa_id"]
    c2 = a.responder("que horas a farmácia abre?")["conversa_id"]
    assert c1 != c2
    # Uma continuação na conversa 2 não pode herdar o assunto da conversa 1.
    r = a.responder("e no domingo?", conversa_id=c2)
    assert "casa123" not in r["mensagem"]["texto"]


# ------------------------------------------------------------ memória viva
def test_ensinar_e_esquecer_atualizam_a_busca(assistente):
    a = assistente
    for busca in BUSCAS:
        assert "verde" not in texto(a, "qual a cor do portão?", busca=busca)
    item = a.ensinar("O portão é verde.", pergunta="cor do portão")
    for busca in BUSCAS:
        assert "verde" in texto(a, "qual a cor do portão?", busca=busca), busca
    a.banco.remover_conhecimento(item["id"])
    for busca in BUSCAS:
        assert "verde" not in texto(a, "qual a cor do portão?", busca=busca), busca


def test_corrigir_um_conhecimento_troca_a_resposta(assistente):
    a = assistente
    item = a.ensinar("A senha do wifi é casa123.", pergunta="senha do wifi")
    assert "casa123" in texto(a, "qual a senha do wifi?")
    a.banco.remover_conhecimento(item["id"])
    a.ensinar("A senha do wifi agora é nova456.", pergunta="senha do wifi")
    r = texto(a, "qual a senha do wifi?")
    assert "nova456" in r and "casa123" not in r


# ------------------------------------------------------------ addons
def test_instalar_e_remover_addon_nao_deixa_resto(assistente_ensinado):
    a = assistente_ensinado
    antes = {p: texto(a, p) for p in PERGUNTAS}
    a.instalar_addon(criar_pacote(MANIFESTO, ITENS, {}))
    assert "verde" in texto(a, "qual a cor do portão?")
    assert a.remover_addon("casa-teste")
    assert "verde" not in texto(a, "qual a cor do portão?")
    assert {p: texto(a, p) for p in PERGUNTAS} == antes


def test_desativar_addon_equivale_a_nao_ter(assistente_ensinado):
    a = assistente_ensinado
    a.instalar_addon(criar_pacote(MANIFESTO, ITENS, {}))
    a.definir_addon_ativo("casa-teste", False)
    assert "verde" not in texto(a, "qual a cor do portão?")
    a.definir_addon_ativo("casa-teste", True)
    assert "verde" in texto(a, "qual a cor do portão?")


def test_reinstalar_o_mesmo_addon_nao_duplica(assistente):
    a = assistente
    a.instalar_addon(criar_pacote(MANIFESTO, ITENS, {}))
    n = a.banco._consultar("SELECT COUNT(*) AS n FROM conhecimentos")[0]["n"]
    a.instalar_addon(criar_pacote({**MANIFESTO, "versao": "1.0.1"}, ITENS, {}))
    assert a.banco._consultar("SELECT COUNT(*) AS n FROM conhecimentos")[0]["n"] == n


# ------------------------------------------------------------ exportação
def test_exportar_e_importar_preserva_as_respostas(assistente_ensinado, tmp_path):
    origem = assistente_ensinado
    previa = exportacao.previa(origem.banco)
    ids = [c["id"] for c in previa["conhecimentos"]]           # inclui o que foi desmarcado
    _, dados = exportacao.exportar(origem.banco, {
        "manifesto": {"nome": "Tudo", "autor": "Dono"}, "conhecimentos": ids})

    banco = Banco(tmp_path / "destino.db")
    destino = Assistente(banco)
    destino.instalar_addon(dados)
    for busca in BUSCAS:
        for p in PERGUNTAS[:-1]:
            assert texto(destino, p, busca=busca) == texto(origem, p, busca=busca), (busca, p)
    banco.fechar()


# ------------------------------------------------------------ banco reaberto
def test_reabrir_o_banco_mantem_as_respostas(tmp_path):
    caminho = tmp_path / "persistente.db"
    banco = Banco(caminho)
    a = Assistente(banco)
    a.ensinar("A senha do wifi é casa123.", pergunta="senha do wifi")
    antes = texto(a, "qual a senha do wifi?")
    banco.fechar()

    banco = Banco(caminho)
    assert texto(Assistente(banco), "qual a senha do wifi?") == antes
    banco.fechar()


# ------------------------------------------------------------ concorrência
def test_varias_threads_perguntando_ao_mesmo_tempo(tmp_path):
    """O servidor atende o navegador em threads; respostas não podem se cruzar."""
    banco = Banco(tmp_path / "threads.db")
    a = Assistente(banco)
    a.ensinar("A senha do wifi é casa123.", pergunta="senha do wifi")
    a.ensinar("O portão é verde.", pergunta="cor do portão")
    esperado = {"qual a senha do wifi?": "casa123", "qual a cor do portão?": "verde"}
    erros = []

    def trabalhar(pergunta):
        try:
            for _ in range(10):
                t = texto(a, pergunta)
                if esperado[pergunta] not in t:
                    erros.append((pergunta, t))
        except Exception as e:      # noqa: BLE001 — o teste quer saber de QUALQUER erro
            erros.append((pergunta, repr(e)))

    threads = [threading.Thread(target=trabalhar, args=(p,)) for p in esperado for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    banco.fechar()
    assert not erros, erros[:3]
