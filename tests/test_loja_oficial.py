"""Testes do link da loja oficial: endereço fixo, aberto pelo servidor no navegador do sistema."""

from fastapi.testclient import TestClient

from aprendiz.aplicativo import config
from aprendiz.api import criar_app
from aprendiz.api import servidor


def test_endereco_da_loja_oficial():
    assert config.URL_LOJA_OFICIAL == "https://jano-projects.github.io/aprendiz-addons/"


def test_status_informa_a_loja(tmp_path):
    with TestClient(criar_app(tmp_path / "api.db")) as c:
        assert c.get("/api/status").json()["loja_oficial"] == config.URL_LOJA_OFICIAL


def test_abrir_loja_usa_sempre_o_endereco_fixo(tmp_path, monkeypatch):
    abertos = []
    monkeypatch.setattr(servidor.webbrowser, "open", lambda url, new=0: abertos.append(url) or True)
    with TestClient(criar_app(tmp_path / "api.db")) as c:
        # Mesmo que alguém mande outro endereço, ele é ignorado.
        r = c.post("/api/loja-oficial", json={"url": "https://site-falso.example"})
        assert r.json() == {"aberto": True, "url": config.URL_LOJA_OFICIAL}
    assert abertos == [config.URL_LOJA_OFICIAL]


def test_sem_navegador_devolve_o_endereco(tmp_path, monkeypatch):
    monkeypatch.setattr(servidor.webbrowser, "open", lambda url, new=0: False)
    with TestClient(criar_app(tmp_path / "api.db")) as c:
        assert c.post("/api/loja-oficial").json()["aberto"] is False
