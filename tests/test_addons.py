"""Testes dos addons: formato, segurança, instalação, ativação e migração."""

import base64
import io
import json
import sqlite3
import zipfile

import pytest
from fastapi.testclient import TestClient

from aprendiz.addons import pacote as addons
from aprendiz.addons.pacote import ErroAddon, criar_pacote, ler_pacote
from aprendiz.api import criar_app
from aprendiz.core import Assistente
from aprendiz.memoria import Banco

MANIFESTO = {"id": "medidas-teste", "nome": "Medidas", "versao": "1.0.0", "autor": "Teste"}
CONHECIMENTOS = [
    {"pergunta": "quantos ml tem uma xícara", "conteudo": "Cerca de 240 ml."},
    {"pergunta": "quantos centímetros tem uma polegada", "conteudo": "2,54 cm."},
]
LINGUAGEM = {"sinonimos": {"chicara": "xicara"}, "abreviacoes": {"pol": "polegada"}}


def pacote(**mudancas) -> bytes:
    manifesto = {**MANIFESTO, **mudancas.pop("manifesto", {})}
    return criar_pacote(manifesto, mudancas.get("conhecimentos", CONHECIMENTOS),
                        mudancas.get("linguagem", LINGUAGEM))


def zip_manual(arquivos: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for nome, conteudo in arquivos.items():
            z.writestr(nome, conteudo)
    return buffer.getvalue()


def tipo(assistente, pergunta, busca="bm25"):
    return assistente.responder(pergunta, busca=busca)["mensagem"]["meta"]["tipo"]


# ------------------------------------------------------------------ formato
def test_ida_e_volta():
    p = ler_pacote(pacote())
    assert p.manifesto["id"] == "medidas-teste"
    assert len(p.conhecimentos) == 2 and p.conhecimentos[0]["tipo"] == "pergunta"
    assert p.linguagem == LINGUAGEM
    assert len(p.hash) == 64


@pytest.mark.parametrize("dados, trecho_erro", [
    (b"isto nao e zip", "não é um addon"),
    (zip_manual({"conhecimentos.json": "[]"}), "manifesto.json"),
    (zip_manual({"manifesto.json": "{nao json", "conhecimentos.json": "[]"}), "JSON válido"),
    (zip_manual({"manifesto.json": json.dumps({**MANIFESTO, "formato": 99}),
                 "conhecimentos.json": "[]"}), "Formato"),
    (zip_manual({"manifesto.json": json.dumps({**MANIFESTO, "formato": 1, "id": "../Ruim"}),
                 "conhecimentos.json": "[]"}), "'id'"),
    (zip_manual({"manifesto.json": json.dumps({**MANIFESTO, "formato": 1}),
                 "conhecimentos.json": "[]"}), "nenhum conhecimento"),
    (zip_manual({"manifesto.json": json.dumps({**MANIFESTO, "formato": 1, "site": "javascript:alert(1)"}),
                 "conhecimentos.json": json.dumps(CONHECIMENTOS)}), "https"),
    (zip_manual({"manifesto.json": json.dumps({**MANIFESTO, "formato": 1}),
                 "conhecimentos.json": json.dumps([{"pergunta": "x"}])}), "sem 'conteudo'"),
])
def test_arquivos_invalidos_sao_recusados(dados, trecho_erro):
    with pytest.raises(ErroAddon, match=trecho_erro):
        ler_pacote(dados)


def test_protecao_contra_zip_bomb(monkeypatch):
    monkeypatch.setattr(addons, "MAX_DESCOMPACTADO", 1000)
    grande = zip_manual({"manifesto.json": json.dumps({**MANIFESTO, "formato": 1}),
                         "conhecimentos.json": json.dumps([{"conteudo": "a" * 5000}])})
    with pytest.raises(ErroAddon, match="grande demais"):
        ler_pacote(grande)


def test_arquivos_extras_e_caminhos_estranhos_sao_ignorados():
    dados = zip_manual({
        "manifesto.json": json.dumps({**MANIFESTO, "formato": 1}),
        "conhecimentos.json": json.dumps(CONHECIMENTOS),
        "../../fora.sh": "rm -rf /",
        "virus.exe": "MZ",
    })
    assert len(ler_pacote(dados).conhecimentos) == 2


def test_caracteres_de_controle_sao_removidos():
    p = ler_pacote(pacote(conhecimentos=[{"conteudo": "ok\x00\x1b[31m vermelho"}]))
    assert p.conhecimentos[0]["conteudo"] == "ok[31m vermelho"


# ------------------------------------------------------------------ instalação e uso
def test_addon_responde_e_mostra_a_origem(assistente):
    r = assistente.instalar_addon(pacote())
    assert r["addon"]["total_conhecimentos"] == 2 and r["versao_anterior"] is None
    resposta = assistente.responder("quantos ml tem uma xícara?")["mensagem"]
    assert resposta["texto"] == "Cerca de 240 ml."
    assert resposta["meta"]["fontes"][0]["addon"] == "Medidas"


@pytest.mark.parametrize("busca", ["bm25", "tfidf", "fuzzy", "hibrido"])
def test_desativar_esconde_e_ativar_mostra(assistente, busca):
    assistente.instalar_addon(pacote())
    assistente.definir_addon_ativo("medidas-teste", False)
    assert tipo(assistente, "quantos ml tem uma xícara?", busca) == "desconhecido"
    assistente.definir_addon_ativo("medidas-teste", True)
    assert tipo(assistente, "quantos ml tem uma xícara?", busca) == "conhecimento"


def test_linguagem_do_addon_vale_so_com_ele_ativo(assistente):
    assistente.instalar_addon(pacote())
    assert assistente.linguagem.processar("1 pol").tokens == ["1", "polegada"]
    assert tipo(assistente, "quantos ml tem uma chicara?") == "conhecimento"
    assistente.definir_addon_ativo("medidas-teste", False)
    assert assistente.linguagem.processar("1 pol").tokens == ["1", "pol"]


def test_linguagem_do_dono_tem_prioridade(assistente):
    assistente.banco.salvar_abreviacao("pol", "politica")
    assistente.instalar_addon(pacote())
    assert assistente.linguagem.processar("pol").tokens == ["politica"]


def test_atualizar_substitui_conteudo_e_mantem_escolha(assistente):
    assistente.instalar_addon(pacote())
    assistente.definir_addon_ativo("medidas-teste", False)
    r = assistente.instalar_addon(pacote(
        manifesto={"versao": "2.0.0"},
        conhecimentos=[{"pergunta": "quantos ml tem uma xícara", "conteudo": "240 ml (v2)."}],
        linguagem={}))
    assert r["versao_anterior"] == "1.0.0"
    assert r["addon"]["versao"] == "2.0.0" and r["addon"]["ativo"] == 0
    assert r["addon"]["total_conhecimentos"] == 1 and r["addon"]["total_linguagem"] == 0
    assistente.definir_addon_ativo("medidas-teste", True)
    assert assistente.responder("quantos ml tem uma xícara?")["mensagem"]["texto"] == "240 ml (v2)."


def test_remover_apaga_tudo_do_addon(assistente):
    assistente.ensinar("Minha nota.", pergunta="nota do dono")
    assistente.instalar_addon(pacote())
    assert assistente.remover_addon("medidas-teste")
    banco = assistente.banco
    assert banco.listar_addons() == []
    assert banco.contar_conhecimentos(de_addons=True) == 0
    assert banco.contar_conhecimentos() == 1
    assert "pol" not in banco.mapa_abreviacoes()


def test_base_do_dono_nao_mistura_addon(assistente):
    assistente.ensinar("Minha nota.")
    assistente.instalar_addon(pacote())
    assert len(assistente.banco.listar_conhecimentos()) == 1
    assert len(assistente.banco.listar_conhecimentos(addon_id="medidas-teste")) == 2


def test_reset_separa_conhecimentos_e_addons(assistente):
    assistente.ensinar("Minha nota.")
    assistente.instalar_addon(pacote())
    assistente.banco.resetar(conhecimentos=True, linguagem=False, conversas=False, addons=False)
    assert assistente.banco.contar_conhecimentos() == 0
    assert assistente.banco.contar_conhecimentos(de_addons=True) == 2
    assistente.banco.resetar(conhecimentos=False, linguagem=False, conversas=False, addons=True)
    assert assistente.banco.listar_addons() == []


def test_addon_de_exemplo_do_projeto(assistente):
    from pathlib import Path
    arquivo = Path(__file__).resolve().parent.parent / "exemplos/addons/conversoes-medidas.aprendiz"
    assistente.instalar_addon(arquivo.read_bytes())
    assert "2,54" in assistente.responder("quanto vale 1 pol em cm?")["mensagem"]["texto"]
    assert "177" in assistente.responder("350 °F é que temperatura de forno?",
                                         resposta="extrativa")["mensagem"]["texto"]


# ------------------------------------------------------------------ migração
def test_banco_da_versao_anterior_e_migrado(tmp_path):
    caminho = tmp_path / "antigo.db"
    con = sqlite3.connect(caminho)
    con.executescript("""
        CREATE TABLE meta (chave TEXT PRIMARY KEY, valor TEXT);
        CREATE TABLE conhecimentos (id TEXT PRIMARY KEY, tipo TEXT NOT NULL, pergunta TEXT,
            conteudo TEXT NOT NULL, origem TEXT NOT NULL DEFAULT 'manual',
            texto_busca TEXT NOT NULL DEFAULT '', criado_em TEXT NOT NULL, atualizado_em TEXT NOT NULL);
        CREATE VIRTUAL TABLE conhecimentos_fts USING fts5(id UNINDEXED, texto);
        INSERT INTO conhecimentos VALUES ('a1', 'pergunta', 'senha do wifi', 'casa123', 'chat',
            'senh wifi casa123', '2026-01-01', '2026-01-01');
        INSERT INTO conhecimentos_fts VALUES ('a1', 'senh wifi casa123');
    """)
    con.commit()
    con.close()

    banco = Banco(caminho)
    assistente = Assistente(banco)
    assert banco.obter_meta("versao_esquema") == "9"
    assert banco.mapa_sinonimos()["horas"] == "horario"  # sinônimo novo chegou na migração
    assert assistente.responder("qual a senha do wifi?")["mensagem"]["texto"] == "casa123"
    assistente.instalar_addon(pacote())
    assert banco.contar_conhecimentos() == 1 and banco.contar_conhecimentos(de_addons=True) == 2
    banco.fechar()
    Banco(caminho).fechar()  # abrir de novo não quebra (migração idempotente)


# ------------------------------------------------------------------ API
@pytest.fixture
def cliente(tmp_path):
    with TestClient(criar_app(tmp_path / "api.db")) as c:
        yield c


def test_api_de_addons(cliente):
    corpo = {"nome_arquivo": "medidas.aprendiz",
             "conteudo_base64": base64.b64encode(pacote()).decode()}
    r = cliente.post("/api/addons", json=corpo)
    assert r.status_code == 200 and r.json()["addon"]["nome"] == "Medidas"
    assert cliente.get("/api/status").json()["addons"] == 1

    assert cliente.patch("/api/addons/medidas-teste", json={"ativo": False}).json()["ativo"] == 0
    assert cliente.get("/api/conhecimentos?addon=medidas-teste").json()["itens"]
    assert cliente.delete("/api/addons/medidas-teste").status_code == 200
    assert cliente.get("/api/addons").json() == []
    assert cliente.delete("/api/addons/medidas-teste").status_code == 404


@pytest.mark.parametrize("corpo, status", [
    ({"nome_arquivo": "x.zip", "conteudo_base64": ""}, 400),
    ({"nome_arquivo": "x.aprendiz", "conteudo_base64": "%%%"}, 400),
    ({"nome_arquivo": "x.aprendiz", "conteudo_base64": base64.b64encode(b"lixo").decode()}, 400),
])
def test_api_recusa_arquivos_invalidos(cliente, corpo, status):
    assert cliente.post("/api/addons", json=corpo).status_code == status


@pytest.mark.parametrize("busca", ["bm25", "tfidf", "fuzzy", "hibrido"])
def test_o_que_o_dono_ensinou_vence_o_addon(assistente, busca):
    assistente.instalar_addon(pacote())
    assistente.ensinar("Na minha cozinha uso 250 ml.", pergunta="quantos ml tem uma xícara")
    texto = assistente.responder("quantos ml tem uma xícara?", busca=busca)["mensagem"]["texto"]
    assert texto == "Na minha cozinha uso 250 ml."
