"""Testes do processamento de linguagem: radicais, normalização, intenções, entidades."""

from aprendiz.linguagem import ClassificadorIntencoes, extrair_entidades, normalizar, radical


def test_radicais_agrupam_variacoes():
    assert len({radical(p) for p in ["ensinar", "ensinei", "ensinando", "ensinou"]}) == 1
    assert radical("farmacia") == radical("farmacias")
    assert radical("carro") == radical("carros")


def test_radical_preserva_palavras_curtas_e_numeros():
    assert radical("oi") == "oi"
    assert radical("2026") == "2026"


def test_normalizar_remove_acentos_e_pontuacao():
    assert normalizar("Qual o HORÁRIO da farmácia?!") == "qual o horario da farmacia"


def test_processar_expande_abreviacoes(assistente):
    texto = assistente.linguagem.processar("vc sabe oq é isso")
    assert texto.expansoes == {"vc": "voce", "oq": "o que"}
    assert "voce" in texto.tokens


def test_processar_aplica_sinonimos_e_remove_stopwords(assistente):
    texto = assistente.linguagem.processar("qual a placa do automóvel")
    assert texto.sinonimos == {"automovel": "carro"}
    assert texto.conteudo == ["placa", "carro"]


def test_correcao_de_digitacao_usa_vocabulario_da_base(assistente_ensinado):
    texto = assistente_ensinado.linguagem.processar("horario da farmasia")
    assert texto.correcoes == {"farmasia": "farmacia"}


def test_classificador_naive_bayes():
    c = ClassificadorIntencoes()
    c.treinar([
        ("saudacao", ["oi"]), ("saudacao", ["bom", "dia"]),
        ("pergunta", ["qual", "horari"]), ("pergunta", ["ond", "fica"]),
    ])
    assert c.classificar(["bom", "dia"])[0]["intencao"] == "saudacao"
    assert c.classificar(["qual", "horari"])[0]["intencao"] == "pergunta"
    assert c.classificar(["xyz"])[0]["intencao"] == "desconhecida"
    soma = sum(r["probabilidade"] for r in c.classificar(["oi"]))
    assert abs(soma - 1) < 0.01


def test_entidades():
    tipos = {e["tipo"]: e["valor"] for e in extrair_entidades(
        "Reunião 12/03 às 14h30, custa R$ 25,00. Ligue (00) 90000-0000 ou mande para a@b.com"
    )}
    assert tipos["data"] == "12/03"
    assert tipos["horario"] == "14h30"
    assert tipos["valor"] == "R$ 25,00"
    assert tipos["telefone"] == "(00) 90000-0000"
    assert tipos["email"] == "a@b.com"


def test_prefixo_curto_com_hifen_vira_uma_palavra():
    assert normalizar("Wi-Fi, E-mail e segunda-feira") == "wifi email e segunda feira"


def test_horas_e_horario_se_encontram(assistente):
    assistente.ensinar("8h às 20h.", pergunta="horário da farmácia")
    assistente.ensinar("A farmácia do bairro entrega remédios em casa.")
    assert assistente.responder("que horas a farmácia abre?")["mensagem"]["texto"] == "8h às 20h."


def test_regras_novas_de_normalizacao_reindexam_a_base(tmp_path):
    from aprendiz.core import Assistente
    from aprendiz.memoria import Banco
    banco = Banco(tmp_path / "b.db")
    banco.salvar_conhecimento("casa123", pergunta="senha do wi-fi", tipo="pergunta",
                              texto_busca="senh wi fi casa123")  # gravado pela regra antiga
    banco.definir_meta("assinatura_indice", "1")
    Assistente(banco)  # ao abrir, percebe a versão antiga e reindexa
    assert banco.todos_conhecimentos()[0]["texto_busca"] == "senh wifi casa123"


def test_nomes_de_linguagem_com_simbolo_nao_viram_c():
    assert normalizar("Ponteiro em C++?") == "ponteiro em cpp"
    assert normalizar("compilar com g++") == "compilar com gpp"
    assert normalizar("classes em C#") == "classes em csharp"
    assert normalizar("struct em C") == "struct em c"
