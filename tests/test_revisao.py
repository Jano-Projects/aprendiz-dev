"""
Testes das normas da língua e da revisão de texto (0.8).

Os addons de verdade (loja oficial) têm milhões de formas; aqui montamos
normas pequenas, com os mesmos formatos, para testar cada peça do motor.
"""

import pytest
from fastapi.testclient import TestClient

from aprendiz.addons import pacote as pacotes
from aprendiz.addons import normas
from aprendiz.api import criar_app
from aprendiz.capacidades import revisao
from aprendiz.addons.normas import Vocabulario

COMUM = """a o os as um uma de do da que não e é eu tu ele ela nós você me te se lhe
dois três anos meses dias faz fazia fez fazem faziam fizeram há havia houve muitas pessoas
estou está estava estão fazer fazendo dizer dizendo comer comendo disse dá isso livro
casa banho para mim entre e exceção cansada meio meia onde aonde vai vou o certo
ação ótimo ideia fato carro chegar chegado chegou haviam havia ontem hoje frase
""".split()
PT = COMUM + "facto económico autocarro pequeno-almoço receção comboio".split()
BR = COMUM + "econômico ônibus recepção trem café manhã".split()

REGRAS = [
    {"id": "fazer-tempo", "nivel": "erro", "titulo": "Fazer indicando tempo",
     "padrao": [{"palavras": ["fazem", "faziam", "fizeram"]}, {"classe": "numero"},
                {"palavras": ["anos", "meses", "dias"]}],
     "sugestao": "{1:troca} {2} {3}", "troca": {"fazem": "faz", "faziam": "fazia", "fizeram": "fez"},
     "mensagem": "Indicando tempo decorrido, o verbo fazer fica no singular.",
     "exemplo": {"errado": "Fazem dois anos.", "certo": "Faz dois anos."}},
    {"id": "haver-existir", "nivel": "erro", "titulo": "Haver no sentido de existir",
     "padrao": [{"palavras": ["haviam", "houveram"]}, {"nao": {"classe": "participio"}}],
     "sugestao": "{1:troca} {2}", "troca": {"haviam": "havia", "houveram": "houve"},
     "marcar": [1, 1],
     "mensagem": "No sentido de existir, haver é impessoal."},
]
REGRAS_PT = REGRAS + [
    {"id": "proclise-inicio", "nivel": "norma", "titulo": "Pronome no começo da frase",
     "padrao": [{"classe": "inicio"}, {"palavras": ["me", "te", "lhe"]},
                {"nao": {"classe": "pronome_reto"}}],
     "sugestao": "{3:capital}-{2:minuscula}",
     "mensagem": "Na norma europeia, a frase não começa por pronome átono."},
    {"id": "estar-gerundio", "nivel": "variante", "titulo": "Estar + gerúndio",
     "padrao": [{"palavras": ["estou", "está", "estava", "estão"]}, {"classe": "gerundio"}],
     "sugestao": "{1} a {2:infinitivo}",
     "mensagem": "Em Portugal, usa-se estar a + infinitivo."},
    {"id": "nao-enclise", "nivel": "erro", "titulo": "Próclise depois de não",
     "padrao": [{"palavras": ["não", "nunca"]}, {"classe": "verbo_com_pronome"}],
     "sugestao": "{1} {2:proclise}", "mensagem": "Depois de não, o pronome vem antes do verbo."},
]


def norma(id_, pais, ortografia, grafias=None, equivalencias=None, regras=None, artigo=""):
    nome = f"Português {'do' if artigo == 'o' else 'de'} {pais}"
    return {"norma": {"id": id_, "nome": nome, "pais": pais, "ortografia": ortografia},
            "fontes": ["teste"],
            "grafias": grafias or {},
            "erros_comuns": {"excessão": "exceção", "concerteza": "com certeza"},
            "equivalencias": equivalencias or [],
            "verbos": ["fazer", "dizer", "comer", "chegar", "estar"],
            "regras": regras or []}


def pacote(id_, pais, ortografia, vocab, artigo="", **kw) -> bytes:
    m = {"id": id_, "nome": f"Norma {pais}", "versao": "1.0.0", "origem": "oficial",
         "editor": "Jano Projects",
         "regiao": {"nome": pais, "artigo": artigo, "termos": [pais.lower()]}}
    return pacotes.criar_pacote(
        m, norma=normas.validar_norma(norma(f"pt-{pais[:2].upper()}", pais, ortografia,
                                            artigo=artigo, **kw)),
        vocabulario=normas.validar_vocabulario("\n".join(vocab).encode()))


@pytest.fixture
def pt():
    return pacote("norma-portugal", "Portugal", "1990", PT, regras=REGRAS_PT,
                  grafias={"econômico": "económico", "recepção": "receção", "fato": "facto"},
                  equivalencias=[{"termos": ["ônibus"], "equivale": "autocarro",
                                  "uso": "Brasil"},
                                 {"termos": ["café da manhã"], "equivale": "pequeno-almoço",
                                  "uso": "Brasil"}])


@pytest.fixture
def br():
    return pacote("norma-brasil", "Brasil", "1990", BR, artigo="o", regras=REGRAS,
                  grafias={"económico": "econômico", "receção": "recepção", "facto": "fato"},
                  equivalencias=[{"termos": ["autocarro", "autocarros"], "equivale": "ônibus",
                                  "uso": "Portugal"},
                                 {"termos": ["comboio"], "equivale": "trem", "uso": "Portugal"}])


def resposta(assistente, texto):
    return assistente.responder(texto)["mensagem"]


# ------------------------------------------------------------------ vocabulário
def test_vocabulario_busca_binaria():
    palavras = ["ação", "zebra", "árvore", "casa", "casas", "ônibus", "a", "é", "bem-estar"]
    bloco = normas.validar_vocabulario("\n".join(palavras).encode())
    vocab = Vocabulario(bloco)
    assert len(vocab) == len(palavras)
    for p in palavras:
        assert p in vocab
    for p in ["", "cas", "casass", "onibus", "b", "zz", "aa", "ç"]:
        assert p not in vocab


def test_vocabulario_grande_e_ordenado():
    def palavra(n):
        letras = "".join("abcdefghij"[int(c)] for c in f"{n:06d}")
        return "p" + letras
    palavras = sorted({palavra(i) for i in range(0, 200_000, 3)})
    vocab = Vocabulario(normas.validar_vocabulario("\n".join(palavras).encode()))
    assert all(p in vocab for p in palavras[::997])
    assert palavra(1) not in vocab and palavra(199_999) not in vocab


def test_vocabulario_invalido():
    with pytest.raises(normas.ErroNorma):
        normas.validar_vocabulario("casa\n<script>\n".encode())
    with pytest.raises(normas.ErroNorma):
        normas.validar_vocabulario(b"# so comentario\n")


# ------------------------------------------------------------------ validação
def test_regra_invalida_e_recusada():
    base = norma("pt-PT", "Portugal", "1990")
    for regra in [
        {"id": "x", "nivel": "erro", "titulo": "t", "mensagem": "m", "padrao": [{"regex": ".*"}]},
        {"id": "xy", "nivel": "grave", "titulo": "t", "mensagem": "m", "padrao": [{"palavras": ["a"]}]},
        {"id": "xy", "nivel": "erro", "titulo": "t", "mensagem": "m",
         "padrao": [{"classe": "verbo_magico"}]},
        {"id": "xy", "nivel": "erro", "titulo": "t", "mensagem": "m",
         "padrao": [{"palavras": ["a"]}], "sugestao": "{2}"},
        {"id": "xy", "nivel": "erro", "titulo": "t", "mensagem": "m",
         "padrao": [{"palavras": ["a"]}], "sugestao": "{1:executar}"},
        {"id": "xy", "nivel": "erro", "titulo": "t", "mensagem": "m", "padrao": [{"classe": "inicio"}]},
    ]:
        with pytest.raises(normas.ErroNorma):
            normas.validar_norma({**base, "regras": [regra]})
    with pytest.raises(normas.ErroNorma):
        normas.validar_norma({**base, "norma": {**base["norma"], "id": "portugues"}})
    with pytest.raises(normas.ErroNorma):
        normas.validar_norma({**base, "secao_estranha": 1})


def test_vocabulario_sem_norma_e_recusado():
    import io
    import zipfile
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("manifesto.json", '{"formato": 2, "id": "so-vocab", "nome": "x", '
                   '"versao": "1.0.0", "classificacao": ["memoria"]}')
        z.writestr("conhecimentos.json", '[{"conteudo": "oi"}]')
        z.writestr("vocabulario.tsv", "casa\n")
    with pytest.raises(pacotes.ErroAddon):
        pacotes.ler_pacote(buffer.getvalue())


def test_pacote_de_norma_tem_classificacao_norma(pt):
    p = pacotes.ler_pacote(pt)
    assert p.manifesto["classificacao"] == ["norma"]
    resumo = pacotes.resumo(p)
    assert resumo["norma"]["id"] == "pt-PO"
    assert resumo["totais"]["vocabulario"] == len(set(PT))


# ------------------------------------------------------------------ revisão
def test_regras_grafias_e_erros(assistente, pt):
    assistente.instalar_addon(pt)
    r = assistente.revisar_texto("Fazem dois anos. Haviam muitas pessoas. Uma excessão.")
    assert r["texto_revisado"] == "Faz dois anos. Havia muitas pessoas. Uma exceção."
    regras = {a["regra"] for a in r["apontamentos"] if a["regra"]}
    assert {"fazer-tempo", "haver-existir"} <= regras
    haver = next(a for a in r["apontamentos"] if a["regra"] == "haver-existir")
    assert haver["destaque"] == [r["texto"].index("Haviam"), r["texto"].index("Haviam") + 6]


def test_haver_auxiliar_nao_e_apontado(assistente, pt):
    assistente.instalar_addon(pt)
    r = assistente.revisar_texto("Eles haviam chegado ontem.")
    assert not [a for a in r["apontamentos"] if a["regra"] == "haver-existir"]


def test_transformacoes_de_portugal(assistente, pt):
    assistente.instalar_addon(pt)
    r = assistente.revisar_texto("Me dá isso. Estou fazendo o livro. Ele não disse-me nada.")
    assert "Dá-me isso" in r["texto_revisado"]
    assert "Estou a fazer o livro" in r["texto_revisado"]
    assert "não me disse" in r["texto_revisado"]


def test_padrao_nao_atravessa_virgula(assistente, pt):
    assistente.instalar_addon(pt)
    r = assistente.revisar_texto("Estou, fazendo isso, cansada.")
    assert not [a for a in r["apontamentos"] if a["regra"] == "estar-gerundio"]


def test_grafia_de_outra_norma_e_acento(assistente, pt, br):
    assistente.instalar_addon(pt)
    assistente.instalar_addon(br)
    r = assistente.revisar_texto("O fato econômico.", "pt-PO")
    assert r["texto_revisado"] == "O facto económico."
    r = assistente.revisar_texto("O facto económico.", "pt-BR")
    assert r["texto_revisado"] == "O fato econômico."


def test_palavra_desconhecida_tem_sugestoes(assistente, pt):
    assistente.instalar_addon(pt)
    r = assistente.revisar_texto("O carrro e a acao.")
    sugestoes = {a["trecho"]: a["sugestoes"] for a in r["apontamentos"]}
    assert sugestoes["carrro"][0] == "carro"
    assert sugestoes["acao"][0] == "ação"


def test_nomes_proprios_e_palavras_do_dono_sao_aceitos(assistente, pt):
    assistente.instalar_addon(pt)
    assistente.ensinar("A Fefê mora em Xique-Xique.", pergunta="onde mora a fefê")
    r = assistente.revisar_texto("Ontem a Mariazinha disse que a fefê e o ABC chegou.")
    trechos = {a["trecho"] for a in r["apontamentos"]}
    assert not trechos & {"Mariazinha", "fefê", "ABC"}


def test_equivalencias_entre_variantes(assistente, br):
    assistente.instalar_addon(br)
    r = assistente.revisar_texto("O autocarro e o comboio.")
    assert r["texto_revisado"] == "O ônibus e o trem."
    autocarro = r["apontamentos"][0]
    assert autocarro["nivel"] == "variante" and "No Brasil" in autocarro["mensagem"]


def test_equivalencia_de_varias_palavras(assistente, pt):
    assistente.instalar_addon(pt)
    r = assistente.revisar_texto("O café da manhã.")
    assert r["texto_revisado"] == "O pequeno-almoço."


def test_verbo_com_pronome_existe(assistente, pt):
    assistente.instalar_addon(pt)
    r = assistente.revisar_texto("Dá-me isso. Vou fazê-lo. Disse-lhe.")
    assert not [a for a in r["apontamentos"] if a["tipo"] == "ortografia"]


def test_escolha_automatica_da_norma(assistente, pt, br):
    assistente.instalar_addon(pt)
    assistente.instalar_addon(br)
    assert assistente.revisar_texto("O autocarro económico.")["norma"]["id"] == "pt-PO"
    assert assistente.revisar_texto("O ônibus econômico.")["norma"]["id"] == "pt-BR"
    assistente.configuracoes.definir("revisao.norma", "pt-BR")
    assert assistente.revisar_texto("O autocarro económico.")["norma"]["id"] == "pt-BR"


def test_sem_norma(assistente):
    with pytest.raises(ValueError):
        assistente.revisar_texto("Olá.")
    msg = resposta(assistente, "revise: fazem dois anos")
    assert msg["meta"]["tipo"] == "revisao" and "addon de **norma**" in msg["texto"]
    # Uma pergunta curta sem norma ativa segue o pipeline normal.
    assert resposta(assistente, "o certo é exceção ou excessão?")["meta"]["tipo"] != "revisao"


# ------------------------------------------------------------------ chat
def test_chat_revise(assistente, pt, br):
    assistente.instalar_addon(pt)
    assistente.instalar_addon(br)
    msg = resposta(assistente, "revise em português de Portugal: Fazem dois anos que estou fazendo isso.")
    assert msg["meta"]["tipo"] == "revisao"
    assert "Faz dois anos que estou a fazer isso." in msg["texto"]
    assert msg["meta"]["revisao"]["norma"]["id"] == "pt-PO"
    msg = resposta(assistente, "Corrija o texto no Brasil: o autocarro")
    assert "ônibus" in msg["texto"]
    etapas = [e["nome"] for e in msg["meta"]["explicacao"]["etapas"]]
    assert "Revisão" in etapas


def test_chat_o_certo_e(assistente, pt):
    assistente.instalar_addon(pt)
    msg = resposta(assistente, "o certo é exceção ou excessão?")
    assert "✔ **exceção**" in msg["texto"] and "✘ **excessão**" in msg["texto"]


def test_chat_como_se_escreve(assistente, pt, br):
    assistente.instalar_addon(pt)
    assistente.instalar_addon(br)
    msg = resposta(assistente, "como se escreve economico?")
    assert "económico" in msg["texto"] and "econômico" in msg["texto"]
    msg = resposta(assistente, "como se escreve economico no Brasil?")
    assert msg["texto"].startswith("Na norma **Português do Brasil**, escreve-se **econômico**")


def test_perguntas_comuns_nao_viram_revisao(assistente, pt):
    assistente.instalar_addon(pt)
    for pergunta in ["como se diz ônibus em Portugal?", "o que é o certo?",
                     "corrija o horário da farmácia", "como faço um bolo?"]:
        assert revisao.interpretar(pergunta) is None or pergunta.startswith("o certo"), pergunta
    assert revisao.interpretar("revise: oi").acao == "revisar"
    assert revisao.interpretar("está certo escrever menas?").texto == "menas"


def test_dono_vence_pergunta_curta(assistente, pt):
    assistente.instalar_addon(pt)
    assistente.ensinar("Com cuidado e caneta.", pergunta="como se escreve carta")
    assert resposta(assistente, "como se escreve carta?")["texto"] == "Com cuidado e caneta."


# ------------------------------------------------------------------ API e configuração
def test_api(tmp_path, pt):
    cliente = TestClient(criar_app(tmp_path / "api.db"))
    import base64
    assert cliente.post("/api/revisar", json={"texto": "oi"}).status_code == 400
    r = cliente.post("/api/addons", json={"nome_arquivo": "pt.aprendiz",
                                          "conteudo_base64": base64.b64encode(pt).decode()})
    assert r.status_code == 200
    assert cliente.get("/api/normas").json()[0]["id"] == "pt-PO"
    opcoes = cliente.get("/api/algoritmos").json()["normas"]
    assert opcoes[0]["nome"] == "" and opcoes[1]["nome"] == "pt-PO"
    r = cliente.post("/api/revisar", json={"texto": "Fazem dois anos."}).json()
    assert r["texto_revisado"] == "Faz dois anos."
    assert cliente.put("/api/configuracoes/revisao.norma", json={"valor": "pt-PO"}).status_code == 200
    assert cliente.put("/api/configuracoes/revisao.norma", json={"valor": "<x>"}).status_code == 400


def test_desativar_addon_desliga_a_norma(assistente, pt):
    assistente.instalar_addon(pt)
    assert assistente.normas_disponiveis()
    assistente.definir_addon_ativo("norma-portugal", False)
    assert not assistente.normas_disponiveis()


# ------------------------------------------------------------------ transformações
@pytest.mark.parametrize("de,para", [("fazendo", "fazer"), ("comendo", "comer"),
                                     ("partindo", "partir"), ("pondo", "pôr"),
                                     ("compondo", "compor")])
def test_infinitivo(de, para):
    assert revisao.infinitivo_de(de) == para
    assert revisao.gerundio_de(para) == de


@pytest.mark.parametrize("de,para", [("disse-me", "me disse"), ("dá-lhe", "lhe dá"),
                                     ("amá-la", "a amar"), ("fazê-lo", "o fazer"),
                                     ("pô-lo", "o pôr"), ("dir-te-ei", None)])
def test_proclise(de, para):
    assert revisao.proclise_de(de) == para


# ------------------------------------------------------------------ variedades (dicionário)
def test_variedades_no_dicionario(assistente):
    m = {"id": "girias-teste", "nome": "Gírias", "versao": "1.0.0", "origem": "oficial",
         "editor": "Jano Projects",
         "regiao": {"nome": "Brasil", "artigo": "o", "termos": ["brasil"],
                    "variedades": [
                        {"id": "nordeste", "nome": "Nordeste", "artigo": "o",
                         "termos": ["nordeste", "nordestino"]},
                        {"id": "sul", "nome": "Sul", "artigo": "o", "termos": ["sul", "gaucho"]}]}}
    verbetes = [
        {"tipo": "verbete", "pergunta": "macaxeira", "conteudo": "**macaxeira** (Nordeste): mandioca.",
         "traducoes": ["mandioca"], "variedade": "nordeste"},
        {"tipo": "verbete", "pergunta": "aipim", "conteudo": "**aipim** (Sul e Sudeste): mandioca.",
         "traducoes": ["mandioca"], "variedade": "sul"},
    ]
    assistente.instalar_addon(pacotes.criar_pacote(
        m, verbetes, {"stopwords": ["significa"]}))
    texto = resposta(assistente, "como se diz mandioca no Nordeste?")["texto"]
    assert "macaxeira" in texto and "aipim" not in texto
    texto = resposta(assistente, "como os gaúchos chamam a mandioca?")["texto"]
    assert "aipim" in texto and "macaxeira" not in texto
    texto = resposta(assistente, "como se diz mandioca no Brasil?")["texto"]
    assert "aipim" in texto and "macaxeira" in texto


def test_variedade_nao_declarada_e_recusada():
    m = {"id": "girias-teste", "nome": "Gírias", "versao": "1.0.0",
         "regiao": {"nome": "Brasil", "termos": ["brasil"]}}
    with pytest.raises(pacotes.ErroAddon):
        pacotes.criar_pacote(m, [{"tipo": "verbete", "pergunta": "x", "conteudo": "y",
                                  "variedade": "marte"}])


# ------------------------------------------------------------------ opções dos elementos
def test_nao_com_lista_e_na_pergunta(assistente):
    regras = [
        {"id": "porque-pergunta", "nivel": "norma", "titulo": "Por que na pergunta",
         "padrao": [{"classe": "inicio"}, {"palavras": ["porque"], "na_pergunta": True}],
         "sugestao": "Por que", "mensagem": "Na pergunta, por que."},
        {"id": "haviam", "nivel": "erro", "titulo": "Haver",
         "padrao": [{"palavras": ["haviam"]},
                    {"nao": [{"classe": "participio"}, {"palavras": ["de", "se"]}]}],
         "sugestao": "havia {2}", "mensagem": "Impessoal."},
    ]
    assistente.instalar_addon(pacote("norma-brasil", "Brasil", "1990", BR + ["porque", "vieste"],
                                     artigo="o", regras=regras))
    r = assistente.revisar_texto("Porque você não veio? Porque não quis. Eles haviam de ir. "
                                 "Haviam se esquecido. Haviam muitas pessoas.")
    regras_achadas = [(a["regra"], a["trecho"]) for a in r["apontamentos"] if a["regra"]]
    assert regras_achadas == [("porque-pergunta", "Porque"), ("haviam", "Haviam muitas")]
