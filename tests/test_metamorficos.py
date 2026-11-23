"""
Testes metamórficos (2.5.1).

Ideia: nem sempre sabemos a resposta "certa", mas sabemos que certas
mudanças na pergunta NÃO podem mudar a resposta. Se "qual a senha do wifi?"
acha a senha, então "QUAL A SENHA DO WIFI", "qual a senha do wifi por favor"
e "qual a snhea do wifi" também precisam achar.

Cada transformação roda em todos os algoritmos de busca. Foi assim que os
defeitos da 2.5.1 apareceram (cortesia, transposição de letras, plurais).
"""

import unicodedata

import pytest

from aprendiz.algoritmos import BUSCAS

BASE = [
    ("senha do wifi", "A senha do wifi é casa123."),
    ("horário da farmácia", "A farmácia abre das 8h às 20h, de segunda a sábado."),
    ("calibragem dos pneus", "A calibragem dos pneus é 35 psi na frente e 33 atrás."),
    ("troca de óleo do carro", "Trocar o óleo do carro a cada 10 mil quilômetros."),
    ("telefone do encanador", "O encanador atende no (11) 98765-4321."),
    ("dia da coleta de lixo", "O caminhão do lixo passa às terças e sextas."),
    ("remédio do cachorro", "O cachorro toma vermífugo a cada três meses."),
    ("aniversário da vó", "O aniversário da vó é dia 12 de agosto."),
    ("como deletar arquivo no linux", "Para deletar um arquivo no Linux use rm nome."),
    ("animais da fazenda", "Na fazenda tem vacas, cavalos e galinhas."),
    ("jornais da cidade", "Os jornais da cidade são o Diário e a Gazeta."),
    ("viagens de férias", "As viagens de férias são sempre em julho."),
]

PERGUNTAS = {
    "qual a senha do wifi?": "casa123",
    "que horas a farmácia abre?": "8h",
    "qual a calibragem dos pneus?": "35 psi",
    "quando trocar o óleo do carro?": "10 mil",
    "qual o telefone do encanador?": "98765",
    "que dia passa a coleta de lixo?": "terças",
    "qual o remédio do cachorro?": "vermífugo",
    "quando é o aniversário da vó?": "12 de agosto",
    "como deletar um arquivo no linux?": "rm",
    "quais os animais da fazenda?": "galinhas",
    "quais os jornais da cidade?": "Gazeta",
    "quando são as viagens de férias?": "julho",
}


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def trocar_letras(s):
    """Inverte duas letras do meio da palavra mais longa (erro de digitação comum)."""
    ps = s.rstrip("?").split()
    i = max(range(len(ps)), key=lambda k: len(ps[k]))
    p = ps[i]
    if len(p) < 6:
        return None
    j = len(p) // 2
    ps[i] = p[:j] + p[j + 1] + p[j] + p[j + 2:]
    return " ".join(ps)


def singular_plural(s):
    trocas = {"animais": "animal", "jornais": "jornal", "viagens": "viagem", "pneus": "pneu"}
    novo = " ".join(trocas.get(p.rstrip("?"), p) for p in s.split())
    return novo if novo != s else None


TRANSFORMACOES = {
    "maiusculas": str.upper,
    "sem_acento": sem_acento,
    "sem_pontuacao": lambda s: s.rstrip("?"),
    "pontuacao_exagerada": lambda s: s.rstrip("?") + "?!?!",
    "espacos": lambda s: "   " + s.replace(" ", "    ") + "   ",
    "por_favor_antes": lambda s: "por favor, " + s,
    "por_favor_depois": lambda s: s.rstrip("?") + ", por favor?",
    "obrigado": lambda s: s + " obrigado",
    "me_explica": lambda s: "me explica " + s,
    "me_diz": lambda s: "me diz " + s,
    "letras_trocadas": trocar_letras,
    "singular": singular_plural,
}


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    from aprendiz.core import Assistente
    from aprendiz.memoria import Banco
    banco = Banco(tmp_path_factory.mktemp("meta") / "meta.db")
    a = Assistente(banco)
    for pergunta, conteudo in BASE:
        a.ensinar(conteudo, pergunta=pergunta)
    yield a
    banco.fechar()


def responde(a, pergunta, busca):
    return a.responder(pergunta, busca=busca)["mensagem"]["texto"]


@pytest.mark.parametrize("busca", sorted(BUSCAS))
def test_base_responde_as_perguntas_originais(base, busca):
    erradas = [p for p, chave in PERGUNTAS.items() if chave not in responde(base, p, busca)]
    assert not erradas, erradas


@pytest.mark.parametrize("nome", sorted(TRANSFORMACOES))
@pytest.mark.parametrize("busca", sorted(BUSCAS))
def test_transformacao_nao_muda_a_resposta(base, busca, nome):
    transformar = TRANSFORMACOES[nome]
    falhas, total = [], 0
    for pergunta, chave in PERGUNTAS.items():
        if chave not in responde(base, pergunta, busca):
            continue                       # só vale para o que já acertava
        nova = transformar(pergunta)
        if not nova or nova == pergunta:
            continue
        total += 1
        if chave not in responde(base, nova, busca):
            falhas.append(nova)
    assert total > 0, "a transformação não se aplicou a nenhuma pergunta"
    assert not falhas, falhas


# ------------------------------------------------------------ com distratores
# Base com armadilhas: "favor" (de "por favor"), "obrigações" (de "obrigado"),
# "milhas" × "linhas" (uma letra trocada leva a outra), palavras de 3 letras
# ("pão", "gás") e plurais que trocam a terminação (pães, países, homens).
ARMADILHAS = [
    ("senha do wifi", "A senha do wifi é casa123."),
    ("favor para a vizinha", "A vizinha pediu o favor de regar as plantas."),
    ("obrigações do condomínio", "As obrigações do condomínio vencem dia 10."),
    ("milhas aéreas", "As milhas aéreas vencem em dezembro."),
    ("linhas de ônibus", "As linhas 175 e 702 passam no centro."),
    ("animal de estimação", "O animal de estimação da casa é o Thor."),
    ("jornal da cidade", "O jornal da cidade é a Gazeta."),
    ("pães da padaria", "Os pães saem às 7h."),
    ("viagem de férias", "A viagem de férias é em julho."),
    ("explicação da conta de luz", "A conta de luz subiu por causa da bandeira vermelha."),
    ("deletar arquivo no linux", "Para deletar um arquivo no Linux use rm."),
    ("excluir conta do banco", "Para excluir a conta vá à agência."),
    ("país de origem do vinho", "O vinho é do Chile."),
    ("homem do gás", "O homem do gás vem às quartas."),
]

CASOS_ARMADILHA = [
    ("por favor, qual a senha do wifi?", "casa123"),
    ("qual a senha do wifi, por favor?", "casa123"),
    ("qual a senha do wifi? obrigado", "casa123"),
    ("pfv qual a senha do wifi", "casa123"),
    ("por gentileza, quando vem o homem do gás", "quartas"),
    ("quais as lihnas de ônibus?", "175"),
    ("quando vencem as mlihas aéreas?", "dezembro"),
    ("qual a snhea do wifi", "casa123"),
    ("como deltear arquivo no linux", "rm"),
    ("qual o animais de estimação?", "Thor"),
    ("quais os jornais da cidade?", "Gazeta"),
    ("quando são as viagens de férias?", "julho"),
    ("quais os países de origem do vinho?", "Chile"),
    ("quando vem os homens do gás?", "quartas"),
    ("que horas saem os pão?", "7h"),             # 2.5.1: palavra de 3 letras no assunto
    ("me explica por que a conta de luz subiu", "bandeira"),
    ("me fala qual é a senha do wifi", "casa123"),
]

# O Fuzzy compara letras, não palavras: "pão" (3 letras) não chega a 85%.
LIMITES_DO_FUZZY = {"que horas saem os pão?"}


@pytest.fixture(scope="module")
def base_armadilhas(tmp_path_factory):
    from aprendiz.core import Assistente
    from aprendiz.memoria import Banco
    banco = Banco(tmp_path_factory.mktemp("armadilhas") / "a.db")
    a = Assistente(banco)
    for pergunta, conteudo in ARMADILHAS:
        a.ensinar(conteudo, pergunta=pergunta)
    yield a
    banco.fechar()


@pytest.mark.parametrize("pergunta, chave", CASOS_ARMADILHA)
@pytest.mark.parametrize("busca", sorted(BUSCAS))
def test_armadilhas(base_armadilhas, busca, pergunta, chave):
    if busca == "fuzzy" and pergunta in LIMITES_DO_FUZZY:
        pytest.skip("limite conhecido do Fuzzy")
    assert chave in responde(base_armadilhas, pergunta, busca)
