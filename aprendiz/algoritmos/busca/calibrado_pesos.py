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
        "pares",
        "pergunta_exata",
        "regras_bm25",
        "termos",
        "tfidf_conf",
        "tfidf_rank"
    ],
    "media": [
        0.44358,
        0.306434,
        0.13804,
        0.418493,
        0.523407,
        0.268353,
        0.084806,
        0.394437,
        0.142206,
        0.029138,
        0.117219,
        0.174274,
        0.055021,
        0.003542,
        0.223611,
        0.509891,
        0.101096,
        0.13804
    ],
    "desvio": [
        0.440438,
        0.365155,
        0.234928,
        0.293963,
        0.499452,
        0.443102,
        0.278593,
        0.410763,
        0.234566,
        0.168192,
        0.321681,
        0.177576,
        0.174935,
        0.059409,
        0.416664,
        0.184501,
        0.13656,
        0.234928
    ],
    "pesos": [
        -0.488621,
        -0.486537,
        0.573937,
        0.717487,
        0.494582,
        0.10991,
        0.254867,
        -0.394472,
        0.128223,
        0.210276,
        0.333046,
        0.296496,
        0.245488,
        0.209479,
        0.150812,
        0.08214,
        0.044936,
        0.455665
    ],
    "vies": -5.09893,
    "regularizacao": 0.3,
    "decisao": {
        "sinais": [
            "nota_do_primeiro",
            "distancia_do_segundo",
            "topo_cobertura_idf",
            "topo_pares",
            "topo_cobre_assunto",
            "topo_melhor_assunto",
            "topo_consenso_hibrido",
            "topo_termos"
        ],
        "pesos": [
            0.349932,
            0.264423,
            0.45107,
            0.561772,
            0.35333,
            0.073622,
            -0.399284,
            -0.071857
        ],
        "vies": -1.012724
    },
    "treino": {
        "data": "2026-11-23",
        "versao_app": "2.6.0",
        "perguntas_treino": 1455,
        "perguntas_teste": 241,
        "addons": {
            "aprendiz-preparar-ambiente": "2.0.2",
            "aprendiz-arquitetura": "2.2.0",
            "aprendiz-codigo": "2.0.2",
            "aprendiz-algoritmos": "2.2.1",
            "aprendiz-do-zero": "2.0.1",
            "atalhos-windows": "2.0.0",
            "c-basico": "2.0.0",
            "c-intermediario": "2.0.1",
            "c-avancado": "2.0.0",
            "cpp-basico": "2.0.0",
            "cpp-intermediario": "2.0.0",
            "cpp-avancado": "2.0.0",
            "atalhos-terminal-linux": "2.0.0",
            "compreensao-portugues": "2.1.0",
            "conversoes-medidas": "2.0.0",
            "dialogo-portugues": "2.2.0",
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
            "python-basico": "2.0.1",
            "python-avancado": "2.0.2",
            "sql-basico": "2.0.1",
            "sql-avancado": "2.0.0",
            "sql-teoria-pratica": "2.0.0",
            "vetores-portugues": "1.0.0"
        },
        "teste": {
            "bm25": {
                "acerto": 0.584,
                "errou": 0.364,
                "recusou": 0.052,
                "inventou": 0.838,
                "ms_por_pergunta": 4.2
            },
            "hibrido": {
                "acerto": 0.549,
                "errou": 0.399,
                "recusou": 0.052,
                "inventou": 0.853,
                "ms_por_pergunta": 16.9
            },
            "calibrado": {
                "acerto": 0.642,
                "errou": 0.225,
                "recusou": 0.133,
                "inventou": 0.662,
                "ms_por_pergunta": 22.5
            },
            "calibrado@0.18": {
                "acerto": 0.653,
                "errou": 0.254,
                "recusou": 0.092,
                "inventou": 0.735,
                "ms_por_pergunta": 22.7
            }
        }
    }
}
