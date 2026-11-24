# Desenvolvimento

Comandos do dia a dia, integração contínua, executável, onde ficam os dados e o resumo da estrutura.

## Comandos

```bash
bash instalar.sh --dev                          # ambiente com pytest e PyInstaller
.venv/bin/pip install -r requirements/treino.txt  # scikit-learn, só para treinar a Calibrada
.venv/bin/python ferramentas/treinar_calibrado.py ../aprendiz-addons   # treina e mede
.venv/bin/python ferramentas/homologar.py ../aprendiz-addons --busca calibrado
.venv/bin/python ferramentas/homologar.py ../aprendiz-addons --pessoal --busca calibrado  # base pessoal
.venv/bin/python -m pytest                      # testes (ver docs/estudo/testes.md)
.venv/bin/python -m pytest --loja ../aprendiz-addons  # + homologação com os addons reais
.venv/bin/python ferramentas/comparar.py         # benchmark dos algoritmos
.venv/bin/python ferramentas/gerar_estrutura.py # atualiza docs/referencia/estrutura.md
.venv/bin/python ferramentas/conferir_addons.py addons/*.aprendiz  # conflitos de linguagem entre addons
.venv/bin/python -m aprendiz --modo servidor    # só o servidor: http://127.0.0.1:8765
```

Com o servidor rodando, a documentação interativa da API fica em `http://127.0.0.1:8765/docs`.
Essa página carrega componentes da internet, então só funciona online.

**Executável:** `bash distribuicao/empacotar.sh` (Linux) ou `distribuicao\empacotar.bat` (Windows) gera `dist/Aprendiz/`,
que inclui o próprio Python. Ao criar uma tag `v*`, o GitHub Actions gera os executáveis dos
dois sistemas.

**Integração contínua:** a cada push, o GitHub instala o projeto com os próprios scripts e roda
os testes no Windows (com e sem Python) e em contêineres Ubuntu, Fedora e Debian que partem
**sem Python** ([testes.yml](../../.github/workflows/testes.yml)). Nas mesmas plataformas, o
workflow [homologacao.yml](../../.github/workflows/homologacao.yml) roda as homologações com os
addons da loja ([Homologação por plataforma](../referencia/homologacao.md)).

## Onde ficam os dados

Toda a memória fica em **um único arquivo SQLite**, fora da pasta do programa:

| Sistema | Pasta |
|---|---|
| Linux | `~/.local/share/aprendiz/aprendiz.db` |
| Windows | `%APPDATA%\Aprendiz\aprendiz.db` |
| macOS | `~/Library/Application Support/Aprendiz/aprendiz.db` |

Para fazer backup, basta copiar esse arquivo. O reset salva antes uma cópia em `backups/`, na
mesma pasta. Para usar outra pasta, defina a variável de ambiente `APRENDIZ_DADOS`.

## Estrutura do projeto

Resumo. O mapa completo, com **todos** os arquivos comentados, está em
[referencia/estrutura.md](../referencia/estrutura.md), gerado a partir dos docstrings do código.

```
aprendiz/
├── aprendiz/                  # o programa (pacote Python)
│   ├── core/                  #   o pipeline (assistente.py), a teia de porquês, padrões e o Monitor
│   ├── linguagem/             #   PLN clássico: normalizador, stemmer, léxico, Naive Bayes, entidades
│   ├── algoritmos/            #   o seletor (padrão Strategy)
│   │   ├── busca/             #     bm25, tfidf, fuzzy, hibrido, calibrado
│   │   └── resposta/          #     direta, extrativa, trabalhada
│   ├── capacidades/           #   compreensão, diálogo, dicionário e revisão (ligadas por addons)
│   ├── addons/                #   o arquivo .aprendiz, recursos, normas, exportação e recomendação
│   ├── memoria/               #   SQLite: conhecimento, linguagem, conversas, addons
│   ├── api/                   #   API local (FastAPI, só em 127.0.0.1)
│   ├── web/                   #   interface e Monitor: HTML, CSS e JS puros, offline
│   └── aplicativo/            #   caminhos, configurações, atualização e a janela de desktop
├── docs/                      # documentação: estudo/, guias/ e referencia/ (índice em docs/README.md)
├── tests/                     # pytest: unidade, API, addons, documentação
├── ferramentas/               # verificar, criar e conferir addons, homologar, treinar, comparar
├── exemplos/addons/           # addons de exemplo (fonte + .aprendiz)
├── distribuicao/              # instalador do Windows, empacotamento e entrada do executável
├── requirements/              # dependências opcionais: dev, janela nativa, treino
├── .github/                   # CI, modelos de issue/PR, contribuição, conduta e segurança
├── instalar.* · executar.*    # instalar e abrir: .sh no Linux, .bat no Windows
└── requirements.txt · pyproject.toml
```
