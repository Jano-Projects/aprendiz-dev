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

1. A interface faz `POST /api/chat` com a mensagem e os algoritmos escolhidos.
2. `Assistente.responder()` grava a mensagem do usuário e executa o pipeline:
   1. **Normalização**: `Linguagem.processar()`
   2. **Ensino explícito**: regex para "aprenda que…", "pergunta: … resposta: …", "anote: …"
   3. **Interpretação**: classificador Naive Bayes + extração de entidades
   4. **Intenção social**: "oi", "obrigado", "ajuda" recebem resposta pronta
   5. **Busca**: algoritmo escolhido; candidatos abaixo do limiar são descartados
   6. **Modo estrito**: sem candidato aceito, responde "ainda não fui ensinado"
   7. **Resposta**: algoritmo escolhido monta o texto
3. Cada etapa registra dados e tempo. Isso vira o campo `meta.explicacao`, que a interface
   mostra no painel "Por que respondi isso?".
4. A resposta é gravada e devolvida.

## Caches e versões

`Banco` mantém dois contadores: `versao_conhecimento` e `versao_linguagem`. Eles aumentam a
cada alteração. Quem guarda algo em memória (índice TF-IDF, índice fuzzy, vocabulário do
corretor, classificador de intenções) compara o contador e só recalcula quando ele muda.
É uma forma barata e simples de invalidar cache.

Quando sinônimos ou abreviações mudam, os radicais de toda a base mudam também. Por isso a
API chama `Assistente.reindexar()` nesses casos.

## Tabelas do banco

| Tabela | Conteúdo |
|---|---|
| `conhecimentos` | o que o dono ensinou (`pergunta`, `nota` ou `trecho`) + `texto_busca` (radicais) |
| `conhecimentos_fts` | índice FTS5 do `texto_busca` |
| `abreviacoes`, `sinonimos`, `stopwords` | banco de linguagem |
| `intencoes_exemplos`, `respostas_padrao` | treino do classificador e respostas sociais |
| `conversas`, `mensagens` | histórico; `mensagens.meta` guarda a explicação em JSON |
| `addons` | addons instalados (manifesto completo em JSON, ativo/desativado, hash do arquivo) |
| `addon_linguagem` | sinônimos e abreviações de addons (valem só com o addon ativo) |
| `configuracoes` | parâmetros e personalização: `addon_id` vazio = do dono; preenchido = de um addon |

Conhecimentos de addons ficam na própria tabela `conhecimentos`, com a coluna `addon_id`
preenchida. A busca filtra os addons desativados dentro do SQL (BM25) ou ao montar os índices
(TF-IDF, fuzzy).

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

As colunas `variacoes` e `traducoes` da tabela `conhecimentos` guardam essas listas em JSON. As
variações entram no texto de busca (BM25, TF-IDF) e viram alvos extras no Fuzzy.

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
versão da estrutura fica em `meta.versao_esquema` (6 a partir da 0.6: colunas `variacoes` e
`traducoes` em `conhecimentos`).

## Reset e cópias de segurança

`POST /api/resetar` exige o texto de confirmação `RESETAR`. Antes de apagar, a API chama
`Banco.fazer_backup()`, que usa a API de backup do próprio SQLite (`Connection.backup`). Ela
copia o banco página por página de forma consistente, mesmo com o app em uso, diferente de
copiar o arquivo "na mão". Depois, `Banco.resetar()` apaga as partes escolhidas e chama
`semear()` para regravar o banco de linguagem inicial. Os contadores de versão aumentam, então
todos os caches (TF-IDF, fuzzy, vocabulário, classificador) se reconstroem sozinhos.

Os IDs são UUIDs aleatórios: dois bancos nunca geram o mesmo id.
