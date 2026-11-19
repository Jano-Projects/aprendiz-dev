# Estrutura do projeto

Mapa de todas as pastas e arquivos, com o papel de cada um.

> Gerado automaticamente por `ferramentas/gerar_estrutura.py` a partir dos docstrings
> do código. **Não edite à mão:** rode `python ferramentas/gerar_estrutura.py`.

## Por onde começar a estudar

1. `aprendiz/core/assistente.py`: o pipeline completo de uma mensagem
2. `aprendiz/linguagem/normalizador.py`: como o texto é preparado
3. `aprendiz/linguagem/stemmer.py` e `intencoes.py`: radicais e Naive Bayes
4. `aprendiz/algoritmos/busca/tfidf.py`: o algoritmo mais didático
5. `aprendiz/algoritmos/busca/bm25.py` e `hibrido.py`: busca de verdade
6. `aprendiz/algoritmos/resposta/extrativa.py`: TextRank
7. `aprendiz/memoria/banco.py`: SQLite, FTS5, migrações
8. `aprendiz/api/servidor.py` e `aprendiz/web/app.js`: como a interface conversa com o núcleo

## Árvore

```
aprendiz/
├── .github/                             # Configurações do GitHub
│   ├── ISSUE_TEMPLATE/                  # Modelos para abrir issues
│   │   ├── bug.md                       # Modelo para relatar um erro
│   │   └── ideia.md                     # Modelo para sugerir uma melhoria
│   ├── workflows/                       # Integração contínua (GitHub Actions)
│   │   └── testes.yml                   # Testa a instalação em Windows, Ubuntu, Fedora e Debian
│   └── PULL_REQUEST_TEMPLATE.md         # Checklist de pull request
├── aprendiz/                            # Aprendiz — um assistente pessoal local, leve e offline.
│   ├── algoritmos/                      # Seletor de algoritmos.
│   │   ├── busca/                       # Algoritmos de busca. A ordem de importação define a ordem no seletor.
│   │   │   ├── __init__.py              # Algoritmos de busca. A ordem de importação define a ordem no seletor.
│   │   │   ├── bm25.py                  # Busca BM25 usando o índice FTS5 do próprio SQLite.
│   │   │   ├── fuzzy.py                 # Busca aproximada (fuzzy) com a biblioteca rapidfuzz.
│   │   │   ├── hibrido.py               # Busca híbrida: combina BM25, TF-IDF e Fuzzy com Reciprocal Rank Fusion (RRF).
│   │   │   └── tfidf.py                 # Busca TF-IDF + similaridade do cosseno, implementada em Python puro.
│   │   ├── resposta/                    # Algoritmos de resposta. A ordem de importação define a ordem no seletor.
│   │   │   ├── __init__.py              # Algoritmos de resposta. A ordem de importação define a ordem no seletor.
│   │   │   ├── direta.py                # Resposta direta: devolve o conteúdo do melhor conhecimento encontrado.
│   │   │   ├── extrativa.py             # Resposta extrativa: monta a resposta com as FRASES mais relevantes de vários…
│   │   │   └── trabalhada.py            # Resposta trabalhada (2.0): o fato encontrado + a cadeia de porquês da teia, dita com as…
│   │   ├── __init__.py                  # Seletor de algoritmos.
│   │   └── base.py                      # Contratos (interfaces) dos algoritmos e o registro do "seletor".
│   ├── api/                             # Servidor HTTP local que expõe o assistente para a interface.
│   │   ├── __init__.py                  # Servidor HTTP local que expõe o assistente para a interface.
│   │   └── servidor.py                  # Servidor HTTP local (FastAPI).
│   ├── core/                            # Núcleo: o pipeline que conecta linguagem, memória e algoritmos.
│   │   ├── __init__.py                  # Núcleo: o pipeline que conecta linguagem, memória e algoritmos.
│   │   ├── assistente.py                # O pipeline: a classe que junta linguagem, memória e algoritmos.
│   │   ├── compreensao.py               # Compreensão: o motor que usa os addons "compreensao" e "vetores" (0.7+).
│   │   ├── dialogo.py                   # Diálogo: o motor que usa a seção "dialogo" dos addons de compreensão (0.9+).
│   │   ├── dicionario.py                # Dicionário: consultas aos VERBETES dos addons, nos dois sentidos.
│   │   ├── exportacao.py                # Exportação: transforma o que o DONO ensinou num addon (.aprendiz) para compartilhar.
│   │   ├── expressao.py                 # Expressão (2.0): COMO dizer cada parte de uma resposta, com frases que vêm dos addons de…
│   │   ├── padroes.py                   # Padrões de frase (2.0): o SENTIDO que vem da estrutura da frase, não das palavras soltas.…
│   │   ├── recomendacao.py              # Recomendação de algoritmos para um addon: qual BUSCA e qual RESPOSTA usar.
│   │   ├── revisao.py                   # Revisão de texto pela NORMA de um país (Aprendiz 0.8+).
│   │   └── teia.py                      # Teia de porquês (2.0): a partir do conhecimento que a busca achou, desce pelos porquês…
│   ├── linguagem/                       # Processamento de linguagem natural (PLN) clássico, sem redes neurais.
│   │   ├── __init__.py                  # Processamento de linguagem natural (PLN) clássico, sem redes neurais.
│   │   ├── entidades.py                 # Extração de entidades com expressões regulares (regex).
│   │   ├── intencoes.py                 # Classificador de intenções — Naive Bayes Multinomial, escrito do zero.
│   │   ├── lexico.py                    # Léxico: lemas e vetores de palavras trazidos pelos addons de compreensão.
│   │   ├── normalizador.py              # Normalizador: transforma a mensagem crua em algo que o computador compara bem.
│   │   ├── numeros.py                   # Números e contas escritos de jeitos diferentes viram uma forma só.
│   │   ├── resolucao.py                 # Junta as abreviações e os sinônimos de VÁRIOS addons sem que um estrague o outro.
│   │   └── stemmer.py                   # Radicalizador (stemmer) para português — versão simplificada do RSLP.
│   ├── memoria/                         # Memória do assistente: tudo fica num único arquivo SQLite.
│   │   ├── __init__.py                  # Memória do assistente: tudo fica num único arquivo SQLite.
│   │   ├── banco.py                     # Camada de acesso ao banco SQLite.
│   │   └── sementes.py                  # Dados iniciais ("sementes") do banco de linguagem.
│   ├── web/                             # Interface de chat: HTML, CSS e JS puros, 100% offline
│   │   ├── app.js                       # Lógica da interface: chat, explicação, addons, configurações
│   │   ├── estilo.css                   # Visual: temas claro/escuro, layout, responsivo
│   │   ├── icone.svg                    # Ícone do aplicativo
│   │   ├── index.html                   # Estrutura da página, ícones SVG e diálogos
│   │   └── markdown.js                  # Mini renderizador de Markdown com proteção contra XSS
│   ├── __init__.py                      # Aprendiz — um assistente pessoal local, leve e offline.
│   ├── __main__.py                      # Permite executar com `python -m aprendiz`.
│   ├── addons.py                        # Addons: pacotes prontos, distribuídos em arquivos .aprendiz.
│   ├── atualizacao.py                   # Atualização sob pedido (2.2): o app e os addons da loja oficial.
│   ├── config.py                        # Configurações globais do Aprendiz.
│   ├── configuracoes.py                 # Configurações ajustáveis: parâmetros dos algoritmos e personalização da interface.
│   ├── desktop.py                       # Inicializador do app de desktop.
│   ├── normas.py                        # Normas da língua (Aprendiz 0.8+): os arquivos que os addons "norma" trazem e a validação…
│   └── recursos.py                      # Recursos de compreensão: os arquivos que os addons "compreensao" e "vetores" trazem…
├── benchmarks/                          # Comparação dos algoritmos de busca
│   ├── comparar.py                      # Benchmark: compara os algoritmos de busca num mesmo conjunto de perguntas.
│   └── dados_exemplo.json               # Base e perguntas usadas no benchmark
├── docs/                                # Documentação de estudo
│   ├── imagens/                         # Imagens usadas no README
│   │   └── tela-principal.png           # Captura da tela principal (README)
│   ├── addons.md                        # Formato .aprendiz, como criar addons e segurança
│   ├── algoritmos.md                    # Como funciona cada algoritmo, com exemplo calculado
│   ├── arquitetura.md                   # Camadas, decisões de projeto e tabelas do banco
│   ├── compreensao.md                   # Addons de compreensão e vetores: lemas, tipos de pergunta, recomendação
│   ├── criar-algoritmo.md               # Passo a passo para adicionar um algoritmo ao seletor
│   ├── empacotamento.md                 # Instaladores, executável e problemas comuns
│   ├── estrutura.md                     # Este mapa (gerado por ferramentas/gerar_estrutura.py)
│   ├── linguagem.md                     # O pipeline de PLN, etapa por etapa
│   └── revisao.md                       # Addons de norma e revisão de texto: vocabulário, grafias, regras de gramática
├── exemplos/                            # Exemplos prontos para usar e estudar
│   └── addons/                          # Addons de exemplo (oficiais): fontes e arquivos .aprendiz gerados
│       ├── conversoes-medidas/          # Fonte de um addon de memória e linguagem
│       │   ├── forno.md                 # Texto livre, dividido em trechos
│       │   ├── linguagem.json           # Sinônimos e abreviações do addon
│       │   ├── manifesto.json           # Identidade do addon (id, nome, versão, origem…)
│       │   └── perguntas.txt            # Pares P:/R: (o jeito mais fácil de escrever)
│       ├── modo-exigente/               # Fonte de um addon só de parâmetros
│       │   ├── manifesto.json           # Identidade do addon (origem oficial)
│       │   └── parametros.json          # Limiares de confiança mais exigentes
│       ├── conversoes-medidas.aprendiz  # Addon pronto para importar
│       └── modo-exigente.aprendiz       # Addon pronto para importar (limiares mais altos)
├── ferramentas/                         # Utilitários para usuários e desenvolvedores
│   ├── conferir_addons.py               # Confere se vários addons convivem bem antes de publicá-los ou ativá-los juntos.
│   ├── criar_addon.py                   # Cria (ou confere) um addon do Aprendiz — um arquivo .aprendiz.
│   ├── gerar_estrutura.py               # Gera docs/estrutura.md: a árvore indentada de pastas e arquivos do projeto, com uma linha…
│   ├── homologar.py                     # Homologação: perguntas de gente de verdade contra os addons REAIS da loja.
│   ├── instalar-windows.ps1             # Lógica do instalador Windows (baixa o Python se faltar)
│   └── verificar.py                     # Verificador de instalação do Aprendiz.
├── tests/                               # Testes automatizados (pytest)
│   ├── conftest.py                      # Fixtures compartilhadas: cada teste ganha um banco novo, num arquivo temporário.
│   ├── test_addons.py                   # Testes dos addons: formato, segurança, instalação, ativação e migração.
│   ├── test_algoritmos.py               # Testes dos algoritmos de busca e de resposta, e do pipeline completo.
│   ├── test_api.py                      # Testes da API HTTP (o mesmo caminho que a interface usa).
│   ├── test_atualizacao.py              # Atualização sob pedido (2.2): só com o gatilho, com SHA-256 conferido. Sem rede: baixar…
│   ├── test_compreensao.py              # Testes da compreensão (0.7): addons "compreensao" e "vetores".
│   ├── test_confusao.py                 # Testes da 2.3.1: confusão entre domínios.
│   ├── test_dialogo.py                  # Testes do diálogo (0.9): a seção "dialogo" dos addons de compreensão e a herança de grupo…
│   ├── test_dicionario.py               # Testes da 0.6: dicionário nos dois sentidos (traduções e regiões), variações de pergunta…
│   ├── test_documentacao.py             # Garante que o projeto continue documentado: todo arquivo tem explicação.
│   ├── test_exportacao.py               # Testes da exportação: prévia com avisos de privacidade, escolha de itens e ida e volta.
│   ├── test_formato2.py                 # Testes do formato 2: origem, classificação, versão do app, dependências e configurações.
│   ├── test_girias.py                   # Testes da 0.4.1: verbetes (dicionário), stopwords e intenções vindas de addons de…
│   ├── test_juntar.py                   # Testes de "juntar e reinterpretar" (1.0): panorama ("o que você sabe sobre X?"), pedido…
│   ├── test_linguagem.py                # Testes do processamento de linguagem: radicais, normalização, intenções, entidades.
│   ├── test_loja_oficial.py             # Testes do link da loja oficial: endereço fixo, aberto pelo servidor no navegador do…
│   ├── test_numeros.py                  # Números e contas escritos de jeitos diferentes viram uma forma só (fase 1 da 2.0).
│   ├── test_padroes.py                  # Padrões de frase (2.0): a estrutura da frase diz o conceito; as lacunas são exemplos.
│   ├── test_recomendacao.py             # Testes da 0.5: recomendação de algoritmos, grupos de addons e as opções ao instalar.
│   ├── test_resolucao.py                # Testes da junção de abreviações e sinônimos de vários addons (1.0).
│   ├── test_revisao.py                  # Testes das normas da língua e da revisão de texto (0.8).
│   ├── test_sentido.py                  # A resposta precisa falar do assunto da pergunta (2.0).
│   └── test_teia.py                     # Teia de porquês (2.0): leitura no perguntas.txt, validação e gravação.
├── .editorconfig                        # Padrão de indentação e fim de linha para qualquer editor
├── .gitattributes                       # Fins de linha corretos por tipo de arquivo (LF/CRLF)
├── .gitignore                           # O que nunca vai para o Git (ambiente, bancos, builds)
├── CHANGELOG.md                         # Histórico de versões
├── CODE_OF_CONDUCT.md                   # Código de conduta da comunidade
├── CONTRIBUTING.md                      # Como contribuir: ambiente, padrões e fluxo de PR
├── empacotar.bat                        # Gera o executável Windows com o PyInstaller
├── empacotar.sh                         # Gera o executável Linux com o PyInstaller
├── executar.bat                         # Abre o Aprendiz no Windows (instala na primeira vez)
├── executar.sh                          # Abre o Aprendiz no Linux/macOS (instala na primeira vez)
├── iniciar.py                           # Ponto de entrada usado pelo PyInstaller para gerar o executável. (Para rodar pelo…
├── instalar.bat                         # Instalador Windows (chama ferramentas/instalar-windows.ps1)
├── instalar.sh                          # Instalador Linux/macOS: instala o Python se faltar, cria o .venv
├── LICENSE                              # Licença MIT
├── pyproject.toml                       # Metadados do pacote Python e configuração do pytest
├── README.md                            # Apresentação, instalação e mapa do projeto
├── requirements-dev.txt                 # Dependências de desenvolvimento (pytest, httpx, PyInstaller)
├── requirements-janela.txt              # Dependência opcional da janela nativa (pywebview)
├── requirements.txt                     # Dependências essenciais (FastAPI, Uvicorn, RapidFuzz)
└── SECURITY.md                          # Política de segurança e como reportar falhas
```
