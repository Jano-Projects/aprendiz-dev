"""
Pesos da busca Calibrada. ARQUIVO GERADO por ferramentas/treinar_calibrado.py:
não edite à mão; treine de novo.
"""

MODELO = {
    "sinais": [
        "assunto",
        "bm25_conf",
        "bm25_rank",
        "cobertura_idf",
        "cobre_assunto",
        "consenso_hibrido",
        "define",
        "fuzzy_conf",
        "fuzzy_rank",
        "melhor_assunto",
        "palavra_forte",
        "palavras_assunto",
        "pergunta_exata",
        "regras_bm25",
        "termos",
        "tfidf_conf",
        "tfidf_rank"
    ],
    "media": [
        0.43231,
        0.323059,
        0.139301,
        0.442424,
        0.467453,
        0.288049,
        0.094809,
        0.400217,
        0.144422,
        0.030272,
        0.101774,
        0.173739,
        0.004457,
        0.213112,
        0.475253,
        0.104854,
        0.139301
    ],
    "desvio": [
        0.428104,
        0.380686,
        0.23633,
        0.308276,
        0.49894,
        0.452854,
        0.292951,
        0.410842,
        0.235709,
        0.171335,
        0.30235,
        0.177472,
        0.066614,
        0.409506,
        0.171522,
        0.141179,
        0.23633
    ],
    "pesos": [
        -0.332815,
        -0.296145,
        0.507337,
        1.005584,
        0.456641,
        0.064759,
        0.250686,
        -0.331477,
        0.058095,
        0.206056,
        0.265827,
        0.350071,
        0.229649,
        -0.028802,
        0.111636,
        0.1742,
        0.418666
    ],
    "vies": -5.358871,
    "regularizacao": 0.3,
    "decisao": {
        "sinais": [
            "nota_do_primeiro",
            "distancia_do_segundo"
        ],
        "pesos": [
            0.518392,
            0.20489
        ],
        "vies": -0.389101
    },
    "treino": {
        "data": "2026-11-19",
        "versao_app": "2.4.0",
        "perguntas_treino": 532,
        "perguntas_teste": 240,
        "addons": {
            "aprendiz-preparar-ambiente": "2.0.1",
            "aprendiz-arquitetura": "2.1.0",
            "aprendiz-codigo": "2.0.1",
            "aprendiz-algoritmos": "2.2.0",
            "aprendiz-do-zero": "2.0.0",
            "atalhos-windows": "2.0.0",
            "c-basico": "2.0.0",
            "c-intermediario": "2.0.1",
            "c-avancado": "2.0.0",
            "cpp-basico": "2.0.0",
            "cpp-intermediario": "2.0.0",
            "cpp-avancado": "2.0.0",
            "atalhos-terminal-linux": "2.0.0",
            "compreensao-portugues": "2.0.4",
            "conversoes-medidas": "2.0.0",
            "dialogo-portugues": "2.1.0",
            "expressoes-guine-bissau": "2.1.0",
            "girias-angola": "2.1.0",
            "expressoes-cabo-verde": "2.1.0",
            "girias-mocambique": "2.1.0",
            "girias-portugal": "2.1.1",
            "expressoes-sao-tome-e-principe": "2.1.0",
            "expressoes-timor-leste": "2.1.1",
            "girias-brasil": "2.1.0",
            "prog-logica": "2.0.0",
            "prog-vocabulario": "2.0.0",
            "prog-estruturas-dados": "2.0.1",
            "prog-banco-dados": "2.0.1",
            "python-basico": "2.0.0",
            "python-avancado": "2.0.1",
            "sql-basico": "2.0.1",
            "sql-avancado": "2.0.0",
            "sql-teoria-pratica": "2.0.0",
            "vetores-portugues": "1.0.0"
        },
        "teste": {
            "bm25": {
                "acerto": 0.587,
                "errou": 0.349,
                "recusou": 0.064,
                "inventou": 0.838,
                "ms_por_pergunta": 2.2
            },
            "hibrido": {
                "acerto": 0.529,
                "errou": 0.401,
                "recusou": 0.07,
                "inventou": 0.838,
                "ms_por_pergunta": 7.7
            },
            "calibrado": {
                "acerto": 0.599,
                "errou": 0.221,
                "recusou": 0.18,
                "inventou": 0.574,
                "ms_por_pergunta": 12.8
            }
        }
    }
}
