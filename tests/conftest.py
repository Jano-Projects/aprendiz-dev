"""Fixtures compartilhadas: cada teste ganha um banco novo, num arquivo temporário."""

import os
from pathlib import Path

import pytest

from aprendiz.core import Assistente
from aprendiz.memoria import Banco


@pytest.fixture
def banco(tmp_path):
    b = Banco(tmp_path / "teste.db")
    yield b
    b.fechar()


@pytest.fixture
def assistente(banco):
    return Assistente(banco)


@pytest.fixture
def assistente_ensinado(assistente):
    """Assistente com uma pequena base de conhecimento já ensinada."""
    assistente.ensinar("8h às 20h, de segunda a sábado", pergunta="horário da farmácia")
    assistente.ensinar("A senha do wifi é casa123.", pergunta="senha do wifi")
    assistente.ensinar("Levar o carro na revisão em março.")
    assistente.ensinar(
        "O carro precisa trocar o óleo a cada 10 mil km. O filtro de ar também "
        "deve ser trocado. A calibragem dos pneus é 35 psi na frente e 33 atrás.",
        tipo="trecho",
    )
    return assistente


# ------------------------------------------------------------ loja (opcional)
# Os testes marcados com @pytest.mark.loja rodam contra os addons REAIS da loja
# (repositório aprendiz-addons). São lentos (~2 min), então só rodam quando
# pedidos:  pytest --loja ../aprendiz-addons   (ou APRENDIZ_LOJA=../aprendiz-addons)
def pytest_addoption(parser):
    parser.addoption("--loja", default=os.environ.get("APRENDIZ_LOJA"),
                     help="pasta do repositório aprendiz-addons (liga os testes da loja)")


def pytest_collection_modifyitems(config, items):
    loja = config.getoption("--loja")
    if loja and (Path(loja) / "addons").is_dir():
        return
    motivo = ("use --loja CAMINHO para rodar contra os addons reais" if not loja
              else f"pasta da loja não encontrada: {loja}")
    for item in items:
        if "loja" in item.keywords:
            item.add_marker(pytest.mark.skip(reason=motivo))


@pytest.fixture(scope="session")
def pasta_loja(pytestconfig):
    return Path(pytestconfig.getoption("--loja"))
