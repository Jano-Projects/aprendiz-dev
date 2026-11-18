"""
Aprendiz — um assistente pessoal local, leve e offline.

Ele não sabe nada "de fábrica": responde apenas com o que o dono ensina.
A inteligência vem de técnicas clássicas de Processamento de Linguagem
Natural (PLN) — normalização, radicalização, classificação de intenções e
algoritmos de busca — e não de um modelo gigante. Por isso roda até em
máquinas bem modestas.

Mapa dos pacotes:

    aprendiz/
    ├── config.py        → caminhos e configurações
    ├── memoria/         → banco SQLite (conhecimento, linguagem, conversas)
    ├── linguagem/       → normalizador, radicalizador, intenções, entidades
    ├── algoritmos/      → plugins de busca e de resposta (o "seletor")
    ├── core/            → o pipeline que junta tudo (classe Assistente)
    ├── api/             → servidor HTTP local (FastAPI)
    ├── web/             → interface de chat (HTML/CSS/JS puros)
    └── desktop.py       → abre o app como janela de desktop
"""

__version__ = "0.4.0"
