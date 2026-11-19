<div align="center">

<img src="aprendiz/web/icone.svg" alt="" width="72">

# Aprendiz

**Um laboratório aberto para estudar Inteligência Artificial por dentro, em português.**
Um assistente local e offline, que só sabe o que você ensina e mostra, **ao vivo**, cada
etapa do que pensa: da tokenização à regressão logística.

[![Testes](https://github.com/Jano-Projects/aprendiz-dev/actions/workflows/testes.yml/badge.svg)](https://github.com/Jano-Projects/aprendiz-dev/actions/workflows/testes.yml)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab)
![Plataformas](https://img.shields.io/badge/plataformas-Linux%20%7C%20Windows-6b7280)
![Offline](https://img.shields.io/badge/funciona-100%25%20offline-16a34a)
[![Licença MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-4f46e5)](LICENSE)

<img src="docs/imagens/tela-principal.png" alt="Tela do Aprendiz 2.4: conversa respondida pela busca Calibrada e, à direita, o Monitor mostrando a conta da regressão logística sinal por sinal" width="820">

</div>

> 🧑‍💻 **Este repositório é para desenvolvedores e estudantes de IA**, do primeiro contato ao
> nível avançado: o código-fonte para estudar, medir, modificar e contribuir.

---

## Sumário

- [O que é](#o-que-é)
- [Para quem é](#para-quem-é)
- [O Monitor](#o-monitor)
- [Recursos](#recursos)
- [Rodando a partir do código](#rodando-a-partir-do-código)
- [Primeiros passos](#primeiros-passos)
- [Para quem vai estudar o código](#para-quem-vai-estudar-o-código)
- [Os algoritmos](#os-algoritmos)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Desenvolvimento](#desenvolvimento)
- [Onde ficam os dados](#onde-ficam-os-dados)
- [Contribuindo](#contribuindo) · [Licença](#licença)

## O que é

O Aprendiz é um chat que roda no seu computador, **sem internet e sem nuvem**. Você ensina
informações do dia a dia (a senha do wi-fi, o horário da farmácia, quando trocar o óleo do
carro) e depois pergunta do jeito que quiser. Ele entende abreviações, sinônimos, erros de
digitação e variações das palavras.

Não há nenhum modelo de IA gigante aqui. A "inteligência" vem de técnicas clássicas de
**PLN**, **recuperação de informação** e **aprendizado de máquina**: normalização,
radicalização, Naive Bayes, BM25, TF-IDF, distância de Levenshtein, *Reciprocal Rank Fusion*,
TextRank, vetores de palavras, busca em grafo e uma **regressão logística treinada** com
perguntas reais. Tudo implementado de forma legível e comentada em português, e pequeno o
bastante para rodar em máquinas bem modestas.

> **Projeto educacional.** Cada arquivo começa explicando o que faz, cada algoritmo explica a
> teoria por trás dele (no código, na documentação e dentro do app) e o **Monitor** mostra,
> enquanto o Aprendiz pensa, cada etapa com tempo, dados, fórmulas e parâmetros.

## Para quem é

| Você é… | Comece por | Depois |
|---|---|---|
| **Iniciante em IA** | Use o app com o Monitor no nível **Iniciante**: cada etapa explicada em palavras simples, e um glossário com os termos | [docs/algoritmos.md](docs/algoritmos.md), seções 1 a 4, com as contas feitas à mão |
| **Dev que quer entender PLN e busca** | A [trilha do código](#para-quem-vai-estudar-o-código): normalizador, stemmer, Naive Bayes, BM25, TF-IDF | Crie o seu algoritmo de busca ([docs/criar-algoritmo.md](docs/criar-algoritmo.md)) e compare no benchmark |
| **Estudante de aprendizado de máquina** | A busca **Calibrada**: sinais, padronização, regressão logística em duas etapas, limiar tirado do custo ([docs](docs/algoritmos.md#5-calibrado-buscacalibradopy-pesos-aprendidos-24)) | Treine de novo com `ferramentas/treinar_calibrado.py`, mude os sinais e meça no conjunto de teste e na homologação |
| **Avançado** | O Monitor no nível **Avançado**: nomes técnicos, fórmulas, contribuição de cada peso e o JSON bruto de cada etapa | A API ao vivo (`/api/chat/fluxo`, NDJSON) e a ficha de parâmetros (`/api/modelo`) para os seus próprios experimentos ([docs/monitor.md](docs/monitor.md)) |

## O Monitor

O painel à direita do chat mostra o que acontece por dentro de cada resposta, em dois níveis
de leitura (**Iniciante** e **Avançado**):

| Aba | O que mostra |
|---|---|
| **Pipeline** | Cada etapa **ao vivo**, assim que termina: o tempo, quando começou (como um gráfico de Gantt) e os dados. A **câmera lenta** espaça as etapas para acompanhar o raciocínio |
| **Busca** | Os candidatos, a confiança de cada um e o limiar. Na busca Calibrada, a conta inteira: `z = viés + Σ peso·sinal`, `p = σ(z)`, a parte de cada sinal num gráfico e a 2ª etapa, que decide se responde |
| **Modelo** | A ficha técnica: **quantos parâmetros** existem, de que tipo (aprendidos, estatísticas da base, pré-treinados, hiperparâmetros), o treino da Calibrada e o ambiente |
| **Desempenho** | Tempo médio de cada etapa, p90 e memória do processo nesta sessão |
| **Glossário** | Os termos técnicos, de *token* a *validação cruzada*, com a definição simples e a técnica |

Detalhes, formato do fluxo ao vivo e o que conta como parâmetro: [docs/monitor.md](docs/monitor.md).

## Recursos

| | |
|---|---|
| 💬 **Chat moderno** | Histórico de conversas, tema claro/escuro, Markdown, ícones, responsivo |
| 🎓 **Aprende pelo chat** | `aprenda que a senha do wifi é casa123` · `pergunta: … resposta: …` · `anote: …` |
| 🔁 **Aprende com correções** | Errou? *Corrigir* transforma a resposta certa em ensinamento |
| 🕸️ **Teia de porquês** | Addons dizem *por que* cada resposta é assim e a que outros conceitos ela se liga, inclusive em outros addons; a resposta **Trabalhada** explica a cadeia até a base ([docs](docs/algoritmos.md#8-resposta-trabalhada-e-teia-de-porquês-20)) |
| 🧩 **Entende a frase** | Padrões de frase ("quantos pedidos cada cliente fez" = agrupar e contar), números por extenso ("dois mais dois") e a regra de que a resposta precisa falar do assunto da pergunta ([docs](docs/compreensao.md#padrões-de-frase-20)) |
| 🧩 **Addons** | Pacotes `.aprendiz` (memória, linguagem, parâmetros, personalização, compreensão, vetores, norma) com confirmação antes de instalar ([docs](docs/addons.md)) |
| ✍️ **Revisão de texto** | Com um addon de norma: ortografia, gramática e palavras de outras variantes pelo português de cada país (Brasil, Portugal, Angola, Moçambique, Cabo Verde, Guiné-Bissau, São Tomé e Príncipe, Timor-Leste): `revise: …`, `o certo é X ou Y?` e a tela **Revisar texto** ([docs](docs/revisao.md)) |
| 🧠 **Compreensão** | Com o addon de compreensão: tipo de pergunta, expressões, formas irregulares, perguntas sobre o próprio app, limites de um assistente offline e indicação do addon certo quando não sabe algo ([docs](docs/compreensao.md)) |
| 🧭 **Busca por sentido** | Com o addon de vetores: se a palavra não está na base, tenta as de sentido parecido |
| 📖 **Dicionários** | Respondem nos dois sentidos, "o que significa kota?" e "como se diz dinheiro em Angola?", sem atrapalhar o resto da conversa |
| 🗣️ **Vários jeitos de perguntar** | Addons trazem variações de cada pergunta, que levam à mesma resposta |
| 🧪 **Algoritmo recomendado** | Cada addon traz a busca e a resposta que funcionam melhor com ele, medidas num teste com o próprio conteúdo e com perguntas fora do assunto |
| ✅ **Homologação** | `ferramentas/homologar.py` faz perguntas de gente de verdade contra os addons reais da loja, incluindo perguntas inéditas ([docs](docs/algoritmos.md#homologação)) |
| 🗂️ **Grupos de addons** | Addons com a mesma recomendação são ativados juntos, no mesmo padrão de busca; os de apoio (compreensão, diálogo, vetores, personalização) entram no grupo dos addons que complementam |
| 💬 **Diálogo** | Com o addon de diálogo: cumprimento + pedido na mesma frase, desabafo, pedido de opinião, perguntas reflexivas e reações à resposta anterior ("não entendi", "não era isso", "sim", "e em Portugal?") ([docs](docs/compreensao.md#diálogo)) |
| 📦 **Exporta o que você ensinou** | Gera um addon para compartilhar, escolhendo item a item; dados pessoais vêm desmarcados |
| 🎨 **Configurações** | Limiares, algoritmos padrão, nome, cor e boas-vindas do assistente |
| 🔍 **Seletor de algoritmos** | 5 de busca e 3 de resposta, cada um com explicação no botão **?** |
| 📈 **Busca Calibrada** | Regressão logística treinada com as perguntas dos addons; a confiança é a chance de acerto ([docs](docs/algoritmos.md#5-calibrado-buscacalibradopy-pesos-aprendidos-24)) |
| 🖥️ **Monitor** | O pipeline ao vivo, a conta da busca, os parâmetros do modelo, o desempenho e um glossário, em nível Iniciante ou Avançado ([docs](docs/monitor.md)) |
| 🛡️ **Modo estrito** | Se não sabe, diz que não sabe. Nada é inventado |
| 🗣️ **Banco de linguagem** | Abreviações, sinônimos e intenções editáveis pela interface |
| 📄 **Importa arquivos** | `.txt` e `.md`, divididos automaticamente em trechos |
| ♻️ **Reset com backup** | Volta ao estado inicial, salvando antes uma cópia de segurança completa |

## Rodando a partir do código

**Não é preciso instalar nada antes.** O instalador confere o Python e, se faltar, instala
sozinho, avisando antes que vai precisar de permissão de administrador. A internet é usada só
durante a instalação e quando você pede para atualizar ("verifique e atualize", no chat): aí o
Aprendiz baixa as versões novas dos addons da loja oficial e, se foi instalado pelo código,
atualiza a si mesmo.

| Sistema | Instalar | Abrir |
|---|---|---|
| **Linux** (Ubuntu, Debian, Fedora, openSUSE, Arch…) | `bash instalar.sh` | `bash executar.sh` |
| **Windows** | dois cliques em `instalar.bat` | dois cliques em `executar.bat` |

- **Linux:** se o seu usuário for administrador, o instalador pede a **sua** senha (sudo). Se
  não for, pede a do **root**. Não rode o instalador com `sudo`.
- **Windows:** o Python oficial é baixado do python.org e o Windows pede confirmação (UAC). Se
  você recusar, ele instala só para o seu usuário.
- Na primeira vez, o `executar` também instala tudo, se você pular o `instalar`.

Para conferir a instalação (Python, SQLite, dependências e um chat de ponta a ponta):

```bash
.venv/bin/python ferramentas/verificar.py          # Linux
.venv\Scripts\python ferramentas\verificar.py      # Windows
```

Detalhes, executável e problemas comuns: [docs/empacotamento.md](docs/empacotamento.md).

## Primeiros passos

1. **Ensine:** `pergunta: horário da farmácia resposta: 8h às 20h`
2. **Pergunte do seu jeito:** `que horas a farmácia abre?`
3. **Veja o raciocínio:** abra o **Monitor** (à direita) e acompanhe cada etapa ao vivo
4. **Compare algoritmos:** troque a busca no topo da tela e pergunte de novo
5. **Instale um addon:** *Addons → Importar addon* →
   `exemplos/addons/conversoes-medidas.aprendiz`, e pergunte `quanto vale 1 pol em cm?`
6. **Conheça a loja oficial:** *Addons → Abrir loja oficial* abre no navegador a
   [loja oficial de addons](https://jano-projects.github.io/aprendiz-addons/) da Jano Projects.

## Para quem vai estudar o código

**Trilha sugerida**, do geral para o específico:

| # | Arquivo | O que você aprende |
|---|---|---|
| 1 | [`core/assistente.py`](aprendiz/core/assistente.py) | O pipeline completo de uma mensagem |
| 2 | [`linguagem/normalizador.py`](aprendiz/linguagem/normalizador.py) | Acentos, abreviações, correção, sinônimos, stopwords |
| 3 | [`linguagem/stemmer.py`](aprendiz/linguagem/stemmer.py) | Radicalização (RSLP simplificado) |
| 4 | [`linguagem/intencoes.py`](aprendiz/linguagem/intencoes.py) | Naive Bayes do zero, com Laplace e softmax |
| 5 | [`algoritmos/busca/tfidf.py`](aprendiz/algoritmos/busca/tfidf.py) | TF-IDF e cosseno, conta a conta |
| 6 | [`algoritmos/busca/bm25.py`](aprendiz/algoritmos/busca/bm25.py) · [`hibrido.py`](aprendiz/algoritmos/busca/hibrido.py) | BM25 no SQLite e Reciprocal Rank Fusion |
| 6b | [`algoritmos/busca/calibrado.py`](aprendiz/algoritmos/busca/calibrado.py) · [`ferramentas/treinar_calibrado.py`](ferramentas/treinar_calibrado.py) | Aprendizado de máquina sem pesar no dispositivo: treino fora, inferência em Python puro |
| 7 | [`algoritmos/resposta/extrativa.py`](aprendiz/algoritmos/resposta/extrativa.py) | TextRank |
| 7b | [`core/teia.py`](aprendiz/core/teia.py) · [`resposta/trabalhada.py`](aprendiz/algoritmos/resposta/trabalhada.py) | Grafo de porquês: busca em largura com freios de sentido |
| 7c | [`core/padroes.py`](aprendiz/core/padroes.py) | Sentido pela estrutura da frase (lacunas = exemplos) |
| 8 | [`memoria/banco.py`](aprendiz/memoria/banco.py) | SQLite, FTS5, transações e migrações |
| 9 | [`addons.py`](aprendiz/addons.py) · [`configuracoes.py`](aprendiz/configuracoes.py) | Leitura segura de arquivos não confiáveis e lista fechada de ajustes |
| 10 | [`core/recomendacao.py`](aprendiz/core/recomendacao.py) | Escolher um algoritmo medindo, não chutando |
| 11 | [`api/servidor.py`](aprendiz/api/servidor.py) · [`web/app.js`](aprendiz/web/app.js) | Como a interface conversa com o núcleo |
| 12 | [`core/monitor.py`](aprendiz/core/monitor.py) · [`web/monitor.js`](aprendiz/web/monitor.js) | Telemetria ao vivo (produtor-consumidor, NDJSON) e contagem de parâmetros |

**Documentação:**

| Documento | Conteúdo |
|---|---|
| [Algoritmos](docs/algoritmos.md) | Como cada um funciona, com um exemplo calculado de ponta a ponta |
| [Linguagem](docs/linguagem.md) | O pipeline de PLN, etapa por etapa |
| [Arquitetura](docs/arquitetura.md) | Camadas, decisões de projeto, tabelas e migrações |
| [Estrutura](docs/estrutura.md) | Mapa indentado de **todos** os arquivos, com o papel de cada um |
| [Criar um algoritmo](docs/criar-algoritmo.md) | Como adicionar o seu ao seletor |
| [Monitor](docs/monitor.md) | O painel técnico, o fluxo ao vivo (NDJSON) e a ficha de parâmetros |
| [Addons](docs/addons.md) | Formato `.aprendiz`, classificação, origem, dicionários, recomendação, grupos, exportação e segurança |
| [Empacotamento](docs/empacotamento.md) | Instaladores, executável e problemas comuns |

## Os algoritmos

```
pergunta ─► normalização ─► BUSCA ─► candidatos ─► limiar ─► RESPOSTA ─► texto
```

Cada modelo tem um **apelido** (como aparece no seletor), o nome técnico e um custo de
processamento por pergunta. A tela **Como funcionam os algoritmos** (botão **?** no topo)
explica cada um passo a passo.

| Busca | Apelido | Ideia | Quando usar | Custo |
|---|---|---|---|---|
| **BM25** (padrão) | Rápido | Ranking clássico de buscadores, calculado pelo SQLite (FTS5) | Bases grandes, perguntas com as mesmas palavras do que foi ensinado | leve |
| **TF-IDF + cosseno** | Didático | Vetores de pesos comparados pelo ângulo | Estudar como uma busca funciona; bases pequenas e médias | leve |
| **Fuzzy** | Tolerante | Similaridade letra a letra (Levenshtein, RapidFuzz) | Perguntas curtas com muitos erros de digitação | médio |
| **Híbrido (RRF)** | Equilibrado | Junta os três pela posição e só aceita com **consenso** | Uso geral | pesado |
| **Calibrado** | Calibrado | Pesa todos os sinais com pesos **aprendidos** (regressão logística); a confiança é a chance de acerto | Uso geral, quando errar custa caro | pesado |

| Resposta | Apelido | Ideia | Custo |
|---|---|---|---|
| **Direta** | Fiel | O conhecimento mais relevante, como foi ensinado | leve |
| **Extrativa** | Resumo | As frases mais relevantes de vários conhecimentos (relevância + TextRank) | médio |
| **Trabalhada** | Explica | O fato e a cadeia de porquês da teia dos addons, dita com as frases de expressão | médio |

Benchmark com os dados de exemplo (`python benchmarks/comparar.py`):

| Algoritmo | Acerto@1 | Não inventou (5 perguntas sem resposta) |
|---|---|---|
| BM25 | 100% | 3/5 |
| TF-IDF | 100% | 3/5 |
| Fuzzy | 83% | 4/5 |
| Híbrido | 100% | 3/5 |
| Calibrado | 100% | 4/5 |

Com perguntas que o modelo nunca viu (o conjunto de teste da Calibrada), a diferença aparece:

| Busca | Acertou | Errou | Inventou (sem resposta) |
|---|---|---|---|
| BM25 | 58,7% | 34,9% | 83,8% |
| Híbrido | 52,9% | 40,1% | 83,8% |
| Calibrado | 59,9% | 22,1% | 57,4% |

## Estrutura do projeto

Resumo. O mapa completo, com **todos** os arquivos comentados, está em
[docs/estrutura.md](docs/estrutura.md), gerado a partir dos docstrings do código.

```
aprendiz/
├── aprendiz/                  # o pacote Python
│   ├── core/                  #   assistente.py: o pipeline; compreensao.py; revisao.py; dicionario.py…
│   ├── linguagem/             #   PLN clássico: normalizador, stemmer, léxico, Naive Bayes, entidades
│   ├── algoritmos/            #   o seletor (padrão Strategy)
│   │   ├── busca/             #     bm25, tfidf, fuzzy, hibrido, calibrado
│   │   └── resposta/          #     direta, extrativa, trabalhada
│   ├── memoria/               #   SQLite: conhecimento, linguagem, conversas, addons
│   ├── addons.py              #   formato .aprendiz: leitura segura e criação
│   ├── recursos.py            #   arquivos dos addons de compreensão e vetores
│   ├── normas.py              #   arquivos dos addons de norma (vocabulário, regras de gramática)
│   ├── configuracoes.py       #   parâmetros e personalização (dono > addon > padrão)
│   ├── api/servidor.py        #   API local (FastAPI, só em 127.0.0.1)
│   ├── web/                   #   interface: HTML, CSS e JS puros, offline
│   └── desktop.py             #   sobe o servidor e abre a janela
├── tests/                     # pytest: unidade, API, addons, documentação
├── benchmarks/                # comparação dos algoritmos
├── ferramentas/               # verificar instalação, criar e conferir addons, gerar estrutura
├── exemplos/addons/           # addons de exemplo (fonte + .aprendiz)
├── docs/                      # documentação de estudo
├── .github/                   # CI e modelos de issue/PR
└── instalar.* · executar.* · empacotar.*   # scripts para Linux (.sh) e Windows (.bat)
```

## Desenvolvimento

```bash
bash instalar.sh --dev                          # ambiente com pytest e PyInstaller
.venv/bin/pip install -r requirements-treino.txt  # scikit-learn, só para treinar a Calibrada
.venv/bin/python ferramentas/treinar_calibrado.py ../aprendiz-addons   # treina e mede
.venv/bin/python ferramentas/homologar.py ../aprendiz-addons --busca calibrado
.venv/bin/python -m pytest                      # testes
.venv/bin/python benchmarks/comparar.py         # benchmark dos algoritmos
.venv/bin/python ferramentas/gerar_estrutura.py # atualiza docs/estrutura.md
.venv/bin/python ferramentas/conferir_addons.py addons/*.aprendiz  # conflitos de linguagem entre addons
.venv/bin/python -m aprendiz --modo servidor    # só o servidor: http://127.0.0.1:8765
```

Com o servidor rodando, a documentação interativa da API fica em `http://127.0.0.1:8765/docs`.
Essa página carrega componentes da internet, então só funciona online.

**Executável:** `bash empacotar.sh` (Linux) ou `empacotar.bat` (Windows) gera `dist/Aprendiz/`,
que inclui o próprio Python. Ao criar uma tag `v*`, o GitHub Actions gera os executáveis dos
dois sistemas.

**Integração contínua:** a cada push, o GitHub instala o projeto com os próprios scripts e roda
os testes no Windows (com e sem Python) e em contêineres Ubuntu, Fedora e Debian que partem
**sem Python** ([testes.yml](.github/workflows/testes.yml)).

## Onde ficam os dados

Toda a memória fica em **um único arquivo SQLite**, fora da pasta do programa:

| Sistema | Pasta |
|---|---|
| Linux | `~/.local/share/aprendiz/aprendiz.db` |
| Windows | `%APPDATA%\Aprendiz\aprendiz.db` |
| macOS | `~/Library/Application Support/Aprendiz/aprendiz.db` |

Para fazer backup, basta copiar esse arquivo. O reset salva antes uma cópia em `backups/`, na
mesma pasta. Para usar outra pasta, defina a variável de ambiente `APRENDIZ_DADOS`.

## Contribuindo

Contribuições são bem-vindas, principalmente as que deixam o código mais fácil de entender.
Leia o [CONTRIBUTING.md](CONTRIBUTING.md) (ambiente, padrões, commits e tags) e o
[Código de conduta](CODE_OF_CONDUCT.md). Falhas de segurança: veja o [SECURITY.md](SECURITY.md).
Mudanças por versão: [CHANGELOG.md](CHANGELOG.md).

## Licença

[MIT](LICENSE): use, estude, modifique e distribua à vontade.
