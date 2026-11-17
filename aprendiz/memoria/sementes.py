"""
Dados iniciais ("sementes") do banco de linguagem.

Na primeira execução, estas listas são gravadas no SQLite. Depois disso o
dono pode editar tudo pela interface (menu "Linguagem"): acrescentar gírias,
sinônimos, novas frases de exemplo para as intenções etc.

Todos os termos estão SEM acento e em minúsculas, porque é assim que o
normalizador deixa o texto antes de consultar estas tabelas
(veja aprendiz/linguagem/normalizador.py).
"""

# ---------------------------------------------------------------------------
# Abreviações comuns da escrita informal em português.
# A chave é o que a pessoa digita; o valor é a forma expandida.
# ---------------------------------------------------------------------------
ABREVIACOES: dict[str, str] = {
    "vc": "voce",
    "vcs": "voces",
    "q": "que",
    "oq": "o que",
    "pq": "porque",
    "tb": "tambem",
    "tbm": "tambem",
    "td": "tudo",
    "blz": "beleza",
    "obg": "obrigado",
    "obgd": "obrigado",
    "vlw": "valeu",
    "msg": "mensagem",
    "hj": "hoje",
    "amn": "amanha",
    "cmg": "comigo",
    "ctg": "contigo",
    "n": "nao",
    "nd": "nada",
    "mt": "muito",
    "mto": "muito",
    "qd": "quando",
    "qnd": "quando",
    "qto": "quanto",
    "dps": "depois",
    "info": "informacao",
    "tel": "telefone",
    "end": "endereco",
}

# ---------------------------------------------------------------------------
# Sinônimos: cada termo é trocado pela sua forma "canônica" antes da busca.
# Assim, ensinar sobre "carro" também responde perguntas sobre "veículo".
# ---------------------------------------------------------------------------
SINONIMOS: dict[str, str] = {
    "automovel": "carro",
    "veiculo": "carro",
    "celular": "telefone",
    "smartphone": "telefone",
    "grana": "dinheiro",
    "custo": "preco",
    "residencia": "casa",
    "moradia": "casa",
    "remedio": "medicamento",
    "trampo": "trabalho",
    "emprego": "trabalho",
    # "horas" e "horário" geram radicais diferentes (hor × horari); sem isto,
    # "que horas abre?" não encontraria "horário de funcionamento".
    "hora": "horario",
    "horas": "horario",
}

# Sinônimos acrescentados em versões novas. Bancos antigos os recebem na
# migração (sem sobrescrever o que o dono já tiver mudado).
SINONIMOS_V3: dict[str, str] = {"hora": "horario", "horas": "horario"}

# ---------------------------------------------------------------------------
# Stopwords: palavras muito frequentes que quase não carregam significado.
# Elas são ignoradas na BUSCA, mas continuam valendo para entender a
# INTENÇÃO (ex.: "tudo bem?" é uma saudação mesmo sendo só stopwords).
# Repare que "nao" NÃO está aqui: negação muda o sentido da frase.
# ---------------------------------------------------------------------------
STOPWORDS: list[str] = """
a o as os um uma uns umas de da do das dos em na no nas nos por pelo pela
pelos pelas para pra pro com sem sob sobre ao aos e ou mas que se ja
eu tu ele ela nos vos eles elas me te lhe meu minha meus minhas teu tua
seu sua seus suas nosso nossa isso isto aquilo esse essa este esta
ser e sao foi era estar esta estou ter tem tenho tinha ha
qual quais como onde quando quem quanto quanta quantos quantas
voce voces mim ti
muito pouco mais menos bem tambem so ate entao assim
me fala diga diz sabe saber poderia pode
""".split()

# ---------------------------------------------------------------------------
# Frases de exemplo de cada intenção. O classificador Naive Bayes
# (aprendiz/linguagem/intencoes.py) aprende a partir delas.
# Quanto mais variadas, melhor ele fica.
# ---------------------------------------------------------------------------
INTENCOES: dict[str, list[str]] = {
    "saudacao": [
        "oi", "ola", "bom dia", "boa tarde", "boa noite", "e ai", "opa",
        "oi tudo bem", "ola tudo bem", "hey", "salve", "oi como vai",
        "tudo bem", "tudo bom",
    ],
    "despedida": [
        "tchau", "ate logo", "ate mais", "falou", "ate amanha", "adeus",
        "vou indo", "fui", "ate a proxima", "tchau tchau", "ate depois",
    ],
    "agradecimento": [
        "obrigado", "obrigada", "valeu", "muito obrigado", "agradeco",
        "brigado", "obrigado pela ajuda", "valeu mesmo", "grato", "show obrigado",
    ],
    "ajuda": [
        "ajuda", "como funciona", "o que voce faz", "como te ensino",
        "como eu te ensino", "quais comandos", "me ajuda a usar",
        "o que posso perguntar", "como usar", "preciso de ajuda", "socorro",
    ],
    "pergunta": [
        "qual o horario da farmacia", "onde fica o mercado",
        "quando e a reuniao", "quem e o responsavel", "como faco para pagar",
        "qual e a senha do wifi", "quanto custa o conserto", "o que e isso",
        "me fala sobre o projeto", "voce sabe o endereco", "onde guardei a chave",
        "qual o telefone do medico", "que horas abre", "qual a placa do carro",
    ],
    "ensinar": [
        "aprenda que", "memorize isso", "lembre que", "anote que",
        "guarde essa informacao", "quero te ensinar uma coisa", "aprende isso",
        "vou te ensinar", "grave isso", "registre que",
    ],
}

# ---------------------------------------------------------------------------
# Respostas prontas para as intenções "sociais" (que não precisam de busca).
# Quando há mais de uma, o assistente sorteia uma delas.
# ---------------------------------------------------------------------------
RESPOSTAS_PADRAO: dict[str, list[str]] = {
    "saudacao": [
        "Olá! Em que posso ajudar?",
        "Oi! Pode me perguntar algo ou me ensinar uma coisa nova.",
    ],
    "despedida": [
        "Até logo! Fico aqui guardando tudo o que você me ensinou.",
        "Até mais! Quando voltar, continuo de onde paramos.",
    ],
    "agradecimento": [
        "Por nada! Estou aqui para ajudar.",
        "Disponha!",
    ],
    "ajuda": [
        "Eu só sei o que você me ensina. Algumas formas de fazer isso:\n\n"
        "- Escreva `aprenda que a senha do wifi é casa123`\n"
        "- Ou use `pergunta: horário da farmácia resposta: 8h às 20h`\n"
        "- Ou `anote: levar o carro na revisão em março`\n"
        "- Clique em **Ensinar** no menu lateral para cadastrar com calma\n"
        "- Em **Base de conhecimento** você também pode importar arquivos .txt e .md\n\n"
        "Se eu errar, clique em **Corrigir** embaixo da minha resposta. "
        "A correção vira um novo ensinamento.",
    ],
}
