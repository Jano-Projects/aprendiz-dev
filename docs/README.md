# Documentação do Aprendiz

A documentação está dividida em três pastas, pelo que você quer fazer:

| Pasta | Para quê |
|---|---|
| [`estudo/`](estudo/) | Entender **como a IA do Aprendiz funciona**, com as contas feitas à mão |
| [`guias/`](guias/) | **Fazer** algo: criar um addon, criar um algoritmo, instalar e empacotar |
| [`referencia/`](referencia/) | **Consultar** o mapa do projeto: camadas, tabelas e todos os arquivos |

## Por onde começar

| Você é… | Leia nesta ordem |
|---|---|
| **Iniciante em IA** | [Algoritmos](estudo/algoritmos.md) (seções 1 a 4) → [Linguagem](estudo/linguagem.md) → [Monitor](estudo/monitor.md), usando o app no nível Iniciante |
| **Dev que quer entender PLN e busca** | [Arquitetura](referencia/arquitetura.md) → [Linguagem](estudo/linguagem.md) → [Algoritmos](estudo/algoritmos.md) → [Criar um algoritmo](guias/criar-algoritmo.md) |
| **Estudante de aprendizado de máquina** | [Algoritmos](estudo/algoritmos.md) (seção 5, busca Calibrada) → [Monitor](estudo/monitor.md) (parâmetros e fluxo ao vivo) → [Testes](estudo/testes.md) (como testar um modelo) |
| **Quem vai criar addons** | [Addons](guias/addons.md) → [Compreensão](estudo/compreensao.md) → [Revisão](estudo/revisao.md) |
| **Quem vai distribuir o app** | [Empacotamento](guias/empacotamento.md) |

## Trilha do código

**Trilha sugerida**, do geral para o específico:

| # | Arquivo | O que você aprende |
|---|---|---|
| 1 | [`core/assistente.py`](../aprendiz/core/assistente.py) | O pipeline completo de uma mensagem |
| 2 | [`linguagem/normalizador.py`](../aprendiz/linguagem/normalizador.py) | Acentos, abreviações, correção, sinônimos, stopwords |
| 3 | [`linguagem/stemmer.py`](../aprendiz/linguagem/stemmer.py) | Radicalização (RSLP simplificado) |
| 4 | [`linguagem/intencoes.py`](../aprendiz/linguagem/intencoes.py) | Naive Bayes do zero, com Laplace e softmax |
| 5 | [`algoritmos/busca/tfidf.py`](../aprendiz/algoritmos/busca/tfidf.py) | TF-IDF e cosseno, conta a conta |
| 6 | [`algoritmos/busca/bm25.py`](../aprendiz/algoritmos/busca/bm25.py) · [`hibrido.py`](../aprendiz/algoritmos/busca/hibrido.py) | BM25 no SQLite e Reciprocal Rank Fusion |
| 6b | [`algoritmos/busca/calibrado.py`](../aprendiz/algoritmos/busca/calibrado.py) · [`ferramentas/treinar_calibrado.py`](../ferramentas/treinar_calibrado.py) | Aprendizado de máquina sem pesar no dispositivo: treino fora, inferência em Python puro |
| 7 | [`algoritmos/resposta/extrativa.py`](../aprendiz/algoritmos/resposta/extrativa.py) | TextRank |
| 7b | [`core/teia.py`](../aprendiz/core/teia.py) · [`resposta/trabalhada.py`](../aprendiz/algoritmos/resposta/trabalhada.py) | Grafo de porquês: busca em largura com freios de sentido |
| 7c | [`core/padroes.py`](../aprendiz/core/padroes.py) | Sentido pela estrutura da frase (lacunas = exemplos) |
| 8 | [`memoria/banco.py`](../aprendiz/memoria/banco.py) | SQLite, FTS5, transações e migrações |
| 9 | [`addons/pacote.py`](../aprendiz/addons/pacote.py) · [`configuracoes.py`](../aprendiz/aplicativo/configuracoes.py) | Leitura segura de arquivos não confiáveis e lista fechada de ajustes |
| 10 | [`addons/recomendacao.py`](../aprendiz/addons/recomendacao.py) | Escolher um algoritmo medindo, não chutando |
| 11 | [`api/servidor.py`](../aprendiz/api/servidor.py) · [`web/app.js`](../aprendiz/web/app.js) | Como a interface conversa com o núcleo |
| 12 | [`core/monitor.py`](../aprendiz/core/monitor.py) · [`web/monitor.js`](../aprendiz/web/monitor.js) | Telemetria ao vivo (produtor-consumidor, NDJSON) e contagem de parâmetros |

## Todos os documentos

### Estudo: como a IA funciona

| Documento | Conteúdo |
|---|---|
| [Algoritmos](estudo/algoritmos.md) | BM25, TF-IDF, Fuzzy, Híbrido e Calibrado; respostas Direta, Extrativa e Trabalhada; homologação e benchmark |
| [Linguagem](estudo/linguagem.md) | O pipeline de PLN: normalização, correção, sinônimos, stopwords, radicais, intenções |
| [Compreensão](estudo/compreensao.md) | Addons de compreensão e vetores: lemas, tipos de pergunta, padrões de frase, diálogo, recomendação |
| [Revisão](estudo/revisao.md) | Addons de norma: vocabulário, grafias de cada país, regras de gramática |
| [Monitor](estudo/monitor.md) | O painel técnico, os níveis Iniciante e Avançado, o fluxo ao vivo e o que conta como parâmetro |
| [Testes](estudo/testes.md) | Testes metamórficos, fuzz, invariantes, propriedades dos modelos e homologação com a loja |

### Guias: como fazer

| Documento | Conteúdo |
|---|---|
| [Addons](guias/addons.md) | O formato `.aprendiz`, como escrever e gerar um addon, teia de porquês, segurança |
| [Criar um algoritmo](guias/criar-algoritmo.md) | Os quatro passos para pôr o seu algoritmo no seletor |
| [Empacotamento](guias/empacotamento.md) | O que os instaladores fazem, o executável e problemas comuns |
| [Recursos](guias/recursos.md) | Tudo o que o Aprendiz faz, com o link para cada explicação |
| [Desenvolvimento](guias/desenvolvimento.md) | Comandos do dia a dia, integração contínua, executável e onde ficam os dados |

### Referência: o mapa

| Documento | Conteúdo |
|---|---|
| [Arquitetura](referencia/arquitetura.md) | Camadas, decisões de projeto, caminho de uma mensagem, tabelas e migrações |
| [Estrutura](referencia/estrutura.md) | Todos os arquivos do projeto, com o papel de cada um (gerado pelo código) |
| [Homologação](referencia/homologacao.md) | Homologação automática e manual em Debian, Fedora, Ubuntu e Windows, com o roteiro e o registro |
| [Versionamento](referencia/versionamento.md) | O que faz cada número da versão subir, branches, pré-versões e versões dos addons |

Para contribuir, veja o [guia de contribuição](../.github/CONTRIBUTING.md).
