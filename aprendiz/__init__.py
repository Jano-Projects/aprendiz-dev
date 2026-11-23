"""
Aprendiz — um assistente pessoal local, leve e offline.

Ele não sabe nada "de fábrica": responde apenas com o que o dono ensina.
A inteligência vem de técnicas clássicas de Processamento de Linguagem
Natural (PLN) — normalização, radicalização, classificação de intenções e
algoritmos de busca — e não de um modelo gigante. Por isso roda até em
máquinas bem modestas.

Mapa dos pacotes:

    aprendiz/
    ├── core/            → o pipeline que junta tudo (classe Assistente), a teia e o Monitor
    ├── linguagem/       → PLN clássico: normalizador, radicalizador, intenções, entidades
    ├── algoritmos/      → plugins de busca e de resposta (o "seletor")
    ├── capacidades/     → compreensão, diálogo, dicionário e revisão (ligadas por addons)
    ├── addons/          → o arquivo .aprendiz, recursos, normas, exportação e recomendação
    ├── memoria/         → banco SQLite (conhecimento, linguagem, conversas)
    ├── api/             → servidor HTTP local (FastAPI)
    ├── web/             → interface de chat e Monitor (HTML/CSS/JS puros)
    └── aplicativo/      → caminhos, configurações, atualização e a janela de desktop
"""

__version__ = "2.5.1"
