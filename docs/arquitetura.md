# Arquitetura

O Aprendiz tem três camadas que conversam por interfaces simples:

```
┌──────────────────────────────────────────────────────────────┐
│  Interface (web/)   HTML + CSS + JS puros                    │
│        │  fetch() em JSON                                    │
├────────┼─────────────────────────────────────────────────────┤
│  API (api/servidor.py)   FastAPI, só em 127.0.0.1            │
│        │                                                     │
├────────┼─────────────────────────────────────────────────────┤
│  Núcleo (core/assistente.py)                                 │
│        ├── linguagem/   normaliza e interpreta               │
│        ├── padroes, teia, expressao (2.0): sentido da frase, │
│        │                porquês e o jeito de dizer           │
│        ├── algoritmos/  busca e monta a resposta             │
│        └── memoria/     SQLite: um arquivo, toda a memória   │
└──────────────────────────────────────────────────────────────┘
```

`desktop.py` sobe a API numa thread e abre a interface numa janela.

## Decisões de projeto

**Servidor web local em vez de uma interface nativa (Tkinter, Qt etc.)**
A interface é uma página web servida localmente. HTML/CSS é o jeito mais
acessível de fazer uma interface bonita, e quem estuda o projeto consegue abrir o
DevTools do navegador e ver cada requisição.

**SQLite**
Um arquivo só, sem servidor, embutido no Python, com busca textual (FTS5) e ranking BM25
nativos. Copiar o arquivo é copiar toda a memória.

**Sem modelo de linguagem**
Técnicas clássicas resolvem bem o problema de "achar o que foi ensinado", rodam em
milissegundos e cabem em qualquer máquina.

**Banco separado da linguagem**
`Banco` só lê e grava. Quem entende texto é `Linguagem`. Quem decide é o `Assistente`.
Cada peça é testável isoladamente.

**Algoritmos como plugins (padrão Strategy)**
Todos os algoritmos de busca têm o mesmo método `buscar()`, e todos os de resposta têm
`responder()`. O decorador `@registrar` os coloca no seletor. Veja
[criar-algoritmo.md](criar-algoritmo.md).

## Caminho de uma mensagem

1. A interface faz `POST /api/chat/fluxo` (2.4) com a mensagem e os algoritmos escolhidos. A
   resposta chega em NDJSON: uma linha por etapa, assim que ela termina, e no fim a resposta
   completa, igual à de `POST /api/chat` (a rota comum, que continua existindo). Veja
   [monitor.md](monitor.md).
2. `Assistente.responder()` grava a mensagem do usuário e executa o pipeline:
   1. **Normalização**: `Linguagem.processar()`, incluindo números e contas numa forma só
      (`linguagem/numeros.py`: "dois mais dois" → `2 soma 2`)
   2. **Ensino explícito**: regex para "aprenda que…", "pergunta: … resposta: …", "anote: …"
      — e, com addon de norma, **revisão de texto** ("revise: …", "o certo é X ou Y?")
   3. **Diálogo** (com addon de diálogo): reações à resposta anterior ("não entendi" vai um nível
      mais fundo pela teia), continuações ("e o limit?") e atos de fala
   4. **Interpretação**: classificador Naive Bayes + extração de entidades
   5. **Intenção social**: "oi", "obrigado", "ajuda" recebem resposta pronta — **a não ser** que
      a mensagem tenha um assunto que a base conhece ("me fala de banco de dados")
   6. **Compreensão** (com addon de compreensão): tipo da pergunta, assunto, necessidades e
      perguntas sobre o próprio Aprendiz
   7. **Padrões de frase** (2.0, `core/padroes.py`): estruturas como "quantos * cada *" dizem o
      conceito; as lacunas são exemplos e saem da busca. A pergunta só é trocada se a reescrita
      achar resposta
   8. **Busca**: algoritmo escolhido, e depois as regras do assunto (2.0): o candidato precisa
      falar do assunto da pergunta, quem bate no **assunto declarado** (pergunta, variações e
      `A:`) ganha folga no limiar e vem antes (2.3.1: a folga exige duas palavras do assunto
      ou uma palavra forte, e palavras que só começam igual, como "indicar" e "índice", não
      contam como flexão quando o addon de vetores diz que são de famílias diferentes)
      Com a busca **Calibrada** (2.4), as folgas fixas não se aplicam: os mesmos sinais entram
      na conta dela com o peso que o treino mediu (`aprendido = True`); o filtro do assunto
      continua valendo
   9. **Modo estrito**: sem candidato aceito, responde "ainda não fui ensinado". Com addon de
      compreensão, antes disso: fora de alcance, busca por sentido (vetores) e recomendação de
      addon (`meta.recomendacao`)
   10. **Teia de porquês** (2.0, `core/teia.py`): a partir do melhor candidato, o caminho de
       porquês até as raízes, guardado em `ContextoBusca.caminho`
   11. **Resposta**: algoritmo escolhido monta o texto; a **Trabalhada** usa o caminho da teia e
       as frases de expressão dos addons de linguagem (`core/expressao.py`)
3. Cada etapa registra dados e tempo. Isso vira o campo `meta.explicacao`, que a interface
   mostra no Monitor.
4. A resposta é gravada e devolvida.

## Caches e versões

`Banco` mantém dois contadores: `versao_conhecimento` e `versao_linguagem`. Eles aumentam a
cada alteração. Quem guarda algo em memória (índice TF-IDF, índice fuzzy, vocabulário do
corretor, classificador de intenções) compara o contador e só recalcula quando ele muda.
É uma forma barata e simples de invalidar cache.

Quando sinônimos ou abreviações mudam, os radicais de toda a base mudam também. Por isso a
API chama `Assistente.reindexar()` nesses casos. Lemas e expressões de um addon de
compreensão também mudam os radicais: `meta.assinatura_indice` guarda a versão das regras de
normalização e os addons de compreensão ativos, e `Assistente._garantir_indice()` reindexa
quando ela muda (ao abrir o app, instalar, ativar, desativar ou remover um addon).

## Tabelas do banco

| Tabela | Conteúdo |
|---|---|
| `conhecimentos` | o que o dono ensinou (`pergunta`, `nota` ou `trecho`) + `texto_busca` (radicais) + `teia` (2.0: ref, assuntos, porquês e raiz, em JSON) |
| `conhecimentos_fts` | índice FTS5 do `texto_busca` |
| `abreviacoes`, `sinonimos`, `stopwords` | banco de linguagem |
| `intencoes_exemplos`, `respostas_padrao` | treino do classificador e respostas sociais |
| `conversas`, `mensagens` | histórico; `mensagens.meta` guarda a explicação em JSON |
| `addons` | addons instalados (manifesto completo em JSON, ativo/desativado, hash do arquivo) |
| `addon_linguagem` | sinônimos e abreviações de addons (valem só com o addon ativo) |
| `configuracoes` | parâmetros e personalização: `addon_id` vazio = do dono; preenchido = de um addon |
| `addon_recursos` | arquivos de compreensão de cada addon (`compreensao.json`, informações e bloco de vetores) e de norma (`norma.json` e o bloco ordenado `vocabulario`) |
| `addon_lexico` | palavras dos addons de compreensão e vetores: lema e número do vetor (consultadas palavra a palavra) |

Conhecimentos de addons ficam na própria tabela `conhecimentos`, com a coluna `addon_id`
preenchida. A busca filtra os addons desativados dentro do SQL (BM25) ou ao montar os índices
(TF-IDF, fuzzy).

## Teia, padrões e expressão (2.0)

Três peças novas, todas alimentadas por **dados** dos addons, e não por regras no código:

| Peça | Arquivo | De onde vêm os dados | Cache |
|---|---|---|---|
| Teia de porquês | `core/teia.py` | linhas `F:`, `A:`, `Q:`, `N:` do `perguntas.txt` → coluna `teia` | `versao_conhecimento` |
| Padrões de frase | `core/padroes.py` | seção `padroes` do `compreensao.json` | `versao_linguagem` |
| Expressão | `core/expressao.py` | seção `expressao` do `compreensao.json` | `versao_linguagem` |

A teia liga fragmentos pela `ref` (mesmo addon) ou por `addon:ref` (outro addon); uma ligação
para addon desativado é cortada, mas o texto do porquê continua valendo. A medida de qualidade
do conjunto é a homologação (`ferramentas/homologar.py`), que roda perguntas reais contra os
addons da loja.

## Monitor (2.4)

```
Assistente.responder(…, ouvinte) ──► Etapas.marcar() ──► ouvinte(etapa) ──► queue.Queue
                                                                              │
interface (monitor.js) ◄── ReadableStream ◄── StreamingResponse (NDJSON) ◄────┘
```

- `Etapas` (em `core/assistente.py`) chama o **ouvinte** a cada etapa marcada; a rota
  `/api/chat/fluxo` roda o `Assistente` numa thread e envia cada evento da fila assim que ele
  chega (produtor-consumidor).
- `core/monitor.py` monta a ficha técnica (`GET /api/modelo`): componentes, parâmetros por tipo,
  treino da Calibrada e ambiente; também mede a memória do processo, gravada em
  `meta.explicacao.memoria_mb` de cada resposta.
- `web/monitor.js` é o painel: Pipeline, Busca, Modelo, Desempenho e Glossário, nos níveis
  Iniciante e Avançado. Ele só lê dados; nada do que mostra muda a resposta.

## Busca aprendida (2.4)

A busca **Calibrada** (`algoritmos/busca/calibrado.py`) é o único algoritmo com parâmetros
aprendidos. O treino fica fora do app:

```
ferramentas/treinar_calibrado.py ──► algoritmos/busca/calibrado_pesos.py ──► calibrado.py
 (scikit-learn, na máquina de          (números: média, desvio e peso       (soma ponderada e
  quem desenvolve)                      de cada sinal; 2ª etapa)              sigmoide, Python puro)
```

Os sinais do assunto declarado são medidos pelo `Assistente` (`_sinais_assunto`), que os
entrega pela função `ContextoBusca.sinais_assunto`. Assim o algoritmo usa as mesmas medidas das
regras fixas sem depender do `Assistente`. O `calibrado_pesos.py` é gerado: não se edita à mão.
As perguntas do treino e do teste ficam em `benchmarks/conjunto_calibrado.json`.

## Configurações (parâmetros e personalização)

`aprendiz/configuracoes.py` define uma **lista fechada** de chaves (limiares, algoritmos padrão,
margem de prioridade do dono, nome, cor e boas-vindas), cada uma com validador e valor padrão.
`Configuracoes.efetivas()` resolve, para cada chave, o valor em vigor na ordem
**dono > addon ativo mais recente > padrão** e informa a origem, que a interface mostra.

A cada pergunta, o `Assistente` lê as configurações uma vez e preenche
`ContextoBusca.limiares`; os algoritmos consultam `ctx.limiar(nome)` em vez do atributo da
classe, que passa a ser só o padrão.

## Dicionário

`aprendiz/core/dicionario.py` atende os pedidos de dicionário antes da etapa de intenções
(senão "como se diz obrigado em Timor?" viraria um agradecimento). Ele separa a região do fim
da frase, testa alguns padrões ("como se diz X", "o que significa X", "qual a gíria para X"…)
e compara o termo por igualdade de radicais com o índice de verbetes dos addons ativos: pelo
termo e suas grafias (sentido direto) e pelas traduções (sentido inverso). Se nada bater,
devolve `None` e o pipeline segue normalmente. O índice é refeito quando a base muda.

Na resposta Trabalhada, `Assistente._teia_dos_verbetes` acrescenta os elos da teia de cada
verbete (`equivale` e `diferente-de`, só o nível 1), com as frases de expressão.

As colunas `variacoes` e `traducoes` da tabela `conhecimentos` guardam essas listas em JSON. As
variações entram no texto de busca (BM25, TF-IDF) e viram alvos extras no Fuzzy.

## Compreensão

`aprendiz/core/compreensao.py` é o motor dos addons de compreensão; `aprendiz/linguagem/lexico.py`
consulta lemas e vetores no SQLite com cache LRU; `aprendiz/recursos.py` valida os arquivos.
Detalhes em [compreensao.md](compreensao.md).

## Revisão de texto

`aprendiz/core/revisao.py` é o motor dos addons de norma: tokens com posição, grafias de
outra norma, vocabulário por busca binária num bloco de bytes, sugestões por edição e regras de
gramática de tipos fixos. `aprendiz/normas.py` valida os arquivos. Detalhes em
[revisao.md](revisao.md).

## Recomendação de algoritmos e grupos

`aprendiz/core/recomendacao.py` cria um banco temporário com os itens de um addon e mede o
acerto@1 de cada algoritmo de busca, usando `Assistente.buscar()`, a mesma etapa de busca do
pipeline. `addons.chave_de_grupo()` define o grupo de cada addon pela recomendação (ou pelos
parâmetros `busca.padrao`/`resposta.padrao`), e `Assistente.grupos_de_addons()` monta os grupos
mostrados na tela de Addons.

## Exportação

`aprendiz/core/exportacao.py` monta a prévia (o que o dono ensinou, a linguagem que difere das
sementes, as configurações do dono e os addons instalados como dependências) com avisos de
possível dado pessoal, e gera o `.aprendiz` com `addons.criar_pacote()`, que valida o arquivo
com as mesmas regras da importação.

## Migrações

`Banco._migrar()` atualiza bancos criados por versões anteriores ao abrir o app. Por exemplo,
ele acrescenta a coluna `addon_id` em bancos da versão 0.1. Os passos são idempotentes, e a
versão da estrutura fica em `meta.versao_esquema` (7 a partir da 0.7: tabelas
`addon_recursos` e `addon_lexico`; 9 a partir da 2.0: coluna `conhecimentos.teia`).

## Reset e cópias de segurança

`POST /api/resetar` exige o texto de confirmação `RESETAR`. Antes de apagar, a API chama
`Banco.fazer_backup()`, que usa a API de backup do próprio SQLite (`Connection.backup`). Ela
copia o banco página por página de forma consistente, mesmo com o app em uso, diferente de
copiar o arquivo "na mão". Depois, `Banco.resetar()` apaga as partes escolhidas e chama
`semear()` para regravar o banco de linguagem inicial. Os contadores de versão aumentam, então
todos os caches (TF-IDF, fuzzy, vocabulário, classificador) se reconstroem sozinhos.

Os IDs são UUIDs aleatórios: dois bancos nunca geram o mesmo id.
