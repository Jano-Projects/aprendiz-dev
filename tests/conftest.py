"""Fixtures compartilhadas: cada teste ganha um banco novo, num arquivo temporário."""

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
