"""
Regressão das correções da 2.5.1, achadas pelos testes metamórficos e de fuzz.

Cada bloco documenta um defeito real: a entrada que falhava e o que passou a
sair. Se algum destes testes quebrar, o defeito voltou.
"""

import pytest

from aprendiz.core.assistente import sem_cortesia
from aprendiz.linguagem.entidades import extrair_entidades
from aprendiz.linguagem.normalizador import normalizar
from aprendiz.linguagem.stemmer import radical


# ------------------------------------------------------------ plurais (stemmer)
# O plural e o singular precisam dar o MESMO radical, senão "animais" não acha
# "animal". Antes da 2.5.1, -ais/-éis/-óis/-ns/-ães/-eses davam radicais diferentes.
PARES = [
    ("animal", "animais"), ("jornal", "jornais"), ("papel", "papeis"),
    ("anel", "aneis"), ("lençol", "lencois"), ("anzol", "anzois"),
    ("azul", "azuis"), ("homem", "homens"), ("jovem", "jovens"),
    ("viagem", "viagens"), ("mês", "meses"), ("país", "paises"),
    ("inglês", "ingleses"), ("pão", "paes"), ("mão", "maos"),
    ("cão", "caes"), ("limão", "limoes"), ("botão", "botoes"),
    ("mulher", "mulheres"), ("flor", "flores"), ("mal", "males"),
    ("mãe", "maes"), ("pai", "pais"), ("boi", "bois"), ("sol", "sois"),
    ("lei", "leis"), ("rei", "reis"), ("barril", "barris"), ("funil", "funis"),
    ("carro", "carros"), ("casa", "casas"), ("lápis", "lapis"),
]

# Limitações conhecidas: sem o acento (o normalizador tira) não dá para saber
# se "faceis" vem de "fácil" (-il átono) ou de "fiel" (-el). Ficam registradas
# para quem quiser melhorar o stemmer.
LIMITACOES = [
    ("fácil", "faceis"), ("útil", "uteis"), ("réptil", "repteis"),
    ("fóssil", "fosseis"), ("herói", "herois"), ("campus", "campi"),
]


@pytest.mark.parametrize("singular, plural", PARES)
def test_plural_e_singular_tem_o_mesmo_radical(singular, plural):
    assert radical(normalizar(singular)) == radical(normalizar(plural))


@pytest.mark.parametrize("singular, plural", LIMITACOES)
@pytest.mark.xfail(reason="depende do acento que o normalizador remove", strict=False)
def test_plurais_que_dependem_do_acento(singular, plural):
    assert radical(normalizar(singular)) == radical(normalizar(plural))


@pytest.mark.parametrize("palavra", ["mes", "pais", "sol", "gas", "lapis", "onibus", "virus"])
def test_radical_nunca_fica_vazio(palavra):
    assert len(radical(palavra)) >= 2


# ------------------------------------------------------------ números
@pytest.mark.parametrize("texto, esperado", [
    ("2 mil", "2000"),
    ("dois mil", "2000"),
    ("3 milhões", "3000000"),
    ("um milhão", "1000000"),
    ("dois bilhões", "2000000000"),
    ("1.000", "1000"),               # separador de milhar
    ("1.234.567", "1234567"),
    ("dois milhões e quinhentos mil", "2500000"),
])
def test_numeros_grandes(texto, esperado):
    assert normalizar(texto) == esperado


@pytest.mark.parametrize("texto", ["3.14", "1.5", "versão 2.5.1"])
def test_ponto_decimal_nao_vira_milhar(texto):
    # "3.14" tem 2 dígitos depois do ponto; "2.5.1" não é número de milhar.
    assert "314" not in normalizar(texto) and "251" not in normalizar(texto)


# ------------------------------------------------------------ cortesia
@pytest.mark.parametrize("mensagem, esperado", [
    ("por favor, qual a senha do wifi?", "qual a senha do wifi?"),
    ("qual a senha do wifi, por favor?", "qual a senha do wifi"),
    ("Por gentileza qual o horário da farmácia", "qual o horário da farmácia"),
    ("pfv qual a senha", "qual a senha"),
    ("qual a senha do wifi? obrigado", "qual a senha do wifi?"),
    ("valeu", "valeu"),                         # só cortesia: mantém a mensagem
    ("por favor", "por favor"),
    ("me passa o pf de frango", "me passa o pf de frango"),   # "pf" é prato feito
])
def test_sem_cortesia(mensagem, esperado):
    assert sem_cortesia(mensagem) == esperado


def test_cortesia_nao_muda_a_resposta(assistente_ensinado):
    a = assistente_ensinado
    puro = a.responder("qual a senha do wifi?")["mensagem"]["texto"]
    educado = a.responder("por favor, qual a senha do wifi?")["mensagem"]["texto"]
    assert puro == educado


# ------------------------------------------------------------ correção (OSA)
@pytest.fixture
def linguagem(assistente_ensinado):
    a = assistente_ensinado
    a.ensinar("Linhas de ônibus que passam no centro.", pergunta="linhas de ônibus")
    a.ensinar("Comando para deletar um arquivo: rm.", pergunta="deletar arquivo")
    a._garantir_indice()
    return a.linguagem


@pytest.mark.parametrize("errada, certa", [
    ("snhea", "senha"),          # transposição: o OSA conta como 1 erro (Levenshtein, 2)
    ("framacia", "farmacia"),
    ("lihnas", "linhas"),
    ("deltear", "deletar"),
    ("carro", "carro"),          # palavra certa não é "corrigida"
])
def test_correcao_por_transposicao(linguagem, errada, certa):
    assert linguagem.processar(errada).reescrito == certa


def test_texto_reescrito_mantem_o_que_nao_conhece(linguagem):
    r = linguagem.processar("qual a snhea do wifi xyzzy")
    assert r.reescrito.split() == ["qual", "a", "senha", "do", "wifi", "xyzzy"]


# ------------------------------------------------------------ entidades
@pytest.mark.parametrize("texto, esperado", [
    ("CEP 01310-100", [("cep", "01310-100")]),
    ("2026-03-12", [("data", "2026-03-12")]),
    ("29/02/2024", [("data", "29/02/2024")]),             # ano bissexto
    ("12/03", [("data", "12/03")]),
    ("23:59", [("horario", "23:59")]),
    ("00:00", [("horario", "00:00")]),
    ("reunião 14h30 dia 12/03/2026", [("horario", "14h30"), ("data", "12/03/2026")]),
    ("ganhei 10,5%", [("percentual", "10,5%")]),
    ("R$ 1.234,56", [("valor", "R$ 1.234,56")]),
])
def test_entidades_validas(texto, esperado):
    assert [(e["tipo"], e["valor"]) for e in extrair_entidades(texto)] == esperado


@pytest.mark.parametrize("texto, tipo_proibido", [
    ("às 25:99", "horario"),
    ("às 24:00", "horario"),
    ("data 31/02/2026", "data"),
    ("29/02/2023", "data"),            # 2023 não é bissexto
    ("12/13", "data"),                 # mês 13
    ("00/05", "data"),                 # dia 0
    ("1999-02-30", "data"),
])
def test_entidades_impossiveis_sao_descartadas(texto, tipo_proibido):
    assert tipo_proibido not in [e["tipo"] for e in extrair_entidades(texto)]


def test_entidades_nunca_se_sobrepoem():
    texto = "dia 12/03/2026 às 14:30, R$ 50,00, CEP 01310-100, (11) 98765-4321, 30%"
    ents = extrair_entidades(texto)
    for a, b in zip(ents, ents[1:]):
        assert a["fim"] <= b["inicio"]
    for e in ents:
        assert texto[e["inicio"]:e["fim"]] == e["valor"]


# ------------------------------------------------------------ diálogo
def test_pergunta_com_que_nao_e_assunto_vago(assistente_ensinado):
    # "me fala o que é ..." já é a pergunta inteira; não deve pedir "sobre o quê?".
    r = assistente_ensinado.responder("me fala qual é a senha do wifi")
    assert "casa123" in r["mensagem"]["texto"]


# ------------------------------------------------------------ singular
@pytest.mark.parametrize("plural, esperado", [
    ("paes", "pao"), ("animais", "animal"), ("paises", "pai"), ("homens", "homem"),
    ("leis", "lei"), ("carros", "carro"), ("pao", "pao"), ("gas", "gas"), ("2026", "2026"),
])
def test_singular_so_tira_o_plural(plural, esperado):
    from aprendiz.linguagem.stemmer import singular
    assert singular(plural) == esperado


def test_palavra_de_tres_letras_no_assunto(assistente):
    assistente.ensinar("Os pães saem às 7h.", pergunta="pães da padaria")
    assert "7h" in assistente.responder("que horas saem os pão?")["mensagem"]["texto"]
