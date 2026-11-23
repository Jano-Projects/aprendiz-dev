"""
Ajuste pessoal da busca Calibrada (2.6): avaliações do dono viram exemplos e
um treino local, ancorado nos pesos oficiais.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from aprendiz.algoritmos.busca import ajuste_pessoal, calibrado_pesos
from aprendiz.api import criar_app
from aprendiz.core import Assistente

OFICIAL = calibrado_pesos.MODELO


# --------------------------------------------------------------- a conta
def _exemplos_do_sinal(j: int, n: int = 40) -> list[tuple[list[float], int]]:
    """Exemplos em que SÓ o sinal j decide: alto → certo, baixo → errado."""
    k = len(OFICIAL["sinais"])
    saida = []
    for i in range(n):
        x = [0.0] * k
        x[j] = 1.5 if i % 2 else -1.5
        saida.append((x, i % 2))
    return saida


def test_treino_aprende_a_direcao_do_sinal():
    j = OFICIAL["sinais"].index("termos")
    pesos, _ = ajuste_pessoal.treinar(_exemplos_do_sinal(j), OFICIAL)
    assert pesos[j] > OFICIAL["pesos"][j] + 0.3


def test_ancora_forte_quase_nao_muda():
    j = OFICIAL["sinais"].index("termos")
    pesos, vies = ajuste_pessoal.treinar(_exemplos_do_sinal(j), OFICIAL, lambda_=1e6)
    assert abs(pesos[j] - OFICIAL["pesos"][j]) < 1e-3
    assert abs(vies - OFICIAL["vies"]) < 1e-3


def test_sem_exemplos_devolve_o_oficial():
    assert ajuste_pessoal.treinar([], OFICIAL) == (list(OFICIAL["pesos"]), OFICIAL["vies"])


def test_um_acerto_vira_exemplos_negativos_dos_outros_candidatos():
    linhas = [({"id": f"d{i}"}, {"termos": i / 10}) for i in range(6)]
    exemplos, grupos = ajuste_pessoal.montar_exemplos(
        [{"pergunta": "p", "conhecimento_id": "d2", "certo": 1}], lambda _: linhas, OFICIAL)
    assert [y for _, y in exemplos] == [1] + [0] * ajuste_pessoal.OUTROS_POR_ACERTO
    assert len(grupos) == 1 and len(grupos[0]) == 6


def test_conhecimento_fora_dos_candidatos_e_pulado():
    exemplos, _ = ajuste_pessoal.montar_exemplos(
        [{"pergunta": "p", "conhecimento_id": "x", "certo": 1}],
        lambda _: [({"id": "d1"}, {})], OFICIAL)
    assert exemplos == []


def test_poucas_avaliacoes_nao_treinam():
    poucas = [{"pergunta": "p", "conhecimento_id": "d", "certo": 1}] * (ajuste_pessoal.MIN_AVALIACOES - 1)
    assert ajuste_pessoal.ajustar(poucas, lambda _: [], OFICIAL, "hoje") is None


def test_compatibilidade_com_o_oficial():
    assert ajuste_pessoal.compativel({**OFICIAL}, OFICIAL)
    assert not ajuste_pessoal.compativel({**OFICIAL, "sinais": OFICIAL["sinais"][:-1]}, OFICIAL)


# --------------------------------------------------------------- no assistente
def _resposta(assistente, pergunta):
    return assistente.responder(pergunta, busca="calibrado")["mensagem"]


def test_avaliar_guarda_e_marca_a_mensagem(assistente_ensinado):
    msg = _resposta(assistente_ensinado, "qual a senha do wifi")
    assert msg["meta"]["tipo"] == "conhecimento"
    r = assistente_ensinado.avaliar(msg["id"], True)
    assert r["avaliacao"] == "util"
    assert assistente_ensinado.banco.contar_avaliacoes()["certos"] == 1
    assert assistente_ensinado.banco.obter_mensagem(msg["id"])["meta"]["avaliacao"] == "util"


def test_so_avalia_resposta_de_conhecimento(assistente_ensinado):
    msg = assistente_ensinado.responder("oi")["mensagem"]
    with pytest.raises(ValueError):
        assistente_ensinado.avaliar(msg["id"], True)


def _treinar_com_avaliacoes(assistente):
    perguntas = ["qual a senha do wifi", "senha da internet", "que horas a farmácia abre",
                 "horário da farmácia", "a farmácia fecha que horas", "senha do wifi por favor"]
    for p in perguntas:
        msg = _resposta(assistente, p)
        if msg["meta"]["tipo"] == "conhecimento":
            assistente.avaliar(msg["id"], True)
    return assistente.ajustar_pessoal(forcar=True)


def test_treina_usa_e_persiste(assistente_ensinado):
    resumo = _treinar_com_avaliacoes(assistente_ensinado)
    assert resumo and resumo["exemplos"] >= ajuste_pessoal.MIN_AVALIACOES
    assert assistente_ensinado.contexto.modelo_calibrado["pessoal"] == resumo
    msg = _resposta(assistente_ensinado, "qual a senha do wifi")
    busca = [e for e in msg["meta"]["explicacao"]["etapas"] if e["nome"].startswith("Busca")][0]
    assert "pessoal" in json.dumps(busca["dados"])
    # Reabrir o banco carrega o ajuste.
    de_novo = Assistente(assistente_ensinado.banco)
    assert de_novo.contexto.modelo_calibrado["pessoal"] == resumo


def test_voltar_ao_oficial(assistente_ensinado):
    _treinar_com_avaliacoes(assistente_ensinado)
    estado = assistente_ensinado.voltar_ao_oficial()
    assert not estado["ativo"] and assistente_ensinado.contexto.modelo_calibrado is None
    assert estado["avaliacoes"]["total"] > 0          # os exemplos ficam
    assert assistente_ensinado.voltar_ao_oficial(apagar_avaliacoes=True)["avaliacoes"]["total"] == 0
    assert Assistente(assistente_ensinado.banco).contexto.modelo_calibrado is None


def test_ajuste_de_outro_modelo_oficial_e_descartado(assistente_ensinado):
    velho = {**OFICIAL, "sinais": ["outro"], "pesos": [1.0], "pessoal": {}}
    assistente_ensinado.banco.definir_meta(Assistente.CHAVE_AJUSTE, json.dumps(velho))
    assert Assistente(assistente_ensinado.banco).contexto.modelo_calibrado is None


def test_nao_era_isso_e_avaliacao_negativa(assistente_ensinado):
    from aprendiz.addons import pacote as pacotes, recursos
    from aprendiz.linguagem import normalizar
    dialogo = {"dialogo": {"conversa": ["ajudar"], "sem_assunto": ["Pode perguntar."],
                           "continuacoes": ["e o"], "atos": [{"id": "nao-era-isso", "acao": "outras_opcoes",
                                     "gatilhos": ["nao era isso"], "respostas": ["Ops."]}]}}
    assistente_ensinado.instalar_addon(pacotes.criar_pacote(
        {"id": "dialogo-teste", "nome": "d", "versao": "1.0.0", "origem": "oficial",
         "editor": "Jano Projects"},
        compreensao=recursos.validar_compreensao(dialogo, normalizar)))
    r = assistente_ensinado.responder("qual a senha do wifi", busca="calibrado")
    conversa = r.get("conversa_id") or r["mensagem"].get("conversa_id")
    assistente_ensinado.responder("não era isso", conversa_id=conversa, busca="calibrado")
    linhas = assistente_ensinado.banco.listar_avaliacoes()
    assert any(a["origem"] == "nao_era_isso" and a["certo"] == 0 for a in linhas)


def test_corrigir_e_avaliacao_positiva(assistente_ensinado):
    msg = _resposta(assistente_ensinado, "qual a senha do wifi")
    novo = assistente_ensinado.corrigir(msg["id"], "A senha do wifi é outra123.")
    linhas = assistente_ensinado.banco.listar_avaliacoes()
    assert any(a["conhecimento_id"] == novo["id"] and a["certo"] == 1 for a in linhas)


def test_resetar_conhecimentos_apaga_avaliacoes(assistente_ensinado):
    _treinar_com_avaliacoes(assistente_ensinado)
    assistente_ensinado.banco.resetar(linguagem=False, conversas=False, addons=False,
                                      configuracoes=False)
    assert assistente_ensinado.banco.contar_avaliacoes()["total"] == 0
    assert Assistente(assistente_ensinado.banco).contexto.modelo_calibrado is None


# --------------------------------------------------------------- API
def test_api(tmp_path):
    with TestClient(criar_app(tmp_path / "api.db")) as c:
        c.post("/api/conhecimentos", json={"conteudo": "A senha do wifi é casa123.",
                                     "pergunta": "senha do wifi"})
        r = c.post("/api/chat", json={"mensagem": "qual a senha do wifi",
                                      "busca": "calibrado"}).json()
        assert c.post("/api/avaliar", json={"mensagem_id": r["mensagem"]["id"],
                                            "util": True}).status_code == 200
        estado = c.get("/api/ajuste").json()
        assert estado["avaliacoes"]["certos"] == 1 and not estado["ativo"]
        assert c.post("/api/ajuste/treinar").status_code == 200
        assert c.delete("/api/ajuste?avaliacoes=true").json()["avaliacoes"]["total"] == 0
        assert c.post("/api/avaliar", json={"mensagem_id": "nada", "util": True}).status_code == 400
