# Compreensão

A partir da versão 0.7, o Aprendiz aceita addons de **compreensão**: em vez de trazer
respostas, eles ensinam o app a **interpretar** o que a pessoa escreve. O motor está no app
(`aprendiz/capacidades/compreensao.py` e `aprendiz/linguagem/lexico.py`); os addons trazem só dados.

A loja oficial distribui três:

| Addon | Classificação | Tamanho | O que traz |
|---|---|---|---|
| **Compreensão do português** (`compreensao-portugues`) | `compreensao`, `linguagem` | ~0,8 MB | tipos de pergunta, expressões, autoconhecimento, limites, necessidades, catálogo da loja e um léxico com mais de 300 mil palavras (139 mil com lema) |
| **Vetores de palavras do português** (`vetores-portugues`) | `vetores` | ~1,7 MB | vetores de sentido para cerca de 114 mil palavras (depende do anterior) |
| **Diálogo do português** (`dialogo-portugues`) | `compreensao` | ~5 KB | atos de fala, palavras de conversa, cumprimentos e continuações (Aprendiz 0.9+; veja [Diálogo](#diálogo)) |

Sem nenhum deles, o Aprendiz funciona exatamente como antes.

## O que muda na conversa

| Pergunta | Sem compreensão | Com compreensão |
|---|---|---|
| "qual a sua versão?" | procura na base | responde a versão, calculada na hora |
| "o que você não sabe fazer?" | procura na base | lista as limitações do app |
| "qual a previsão do tempo?" | "ainda não fui ensinado" | explica que não acessa a internet |
| "onde ele fez a prova?" (base: "onde eu fiz a prova") | radicais diferentes (`fez` ≠ `fiz`) | lema `fazer` nos dois: encontra |
| "qual a palavra-passe do wifi?" | não acha "senha" | expressão "palavra passe" → senha |
| "o que significa kota?" (dicionário desativado) | "ainda não fui ensinado" | "você tem o addon Gírias de Angola, mas ele está desativado" + botão **Ativar e perguntar de novo** |
| "como converter polegadas?" (sem o addon) | "ainda não fui ensinado" | indica **Conversões de medidas** + botão **Ver na loja oficial** |
| "moto" (base fala de "bicicleta"), com vetores | "ainda não fui ensinado" | busca por sentido: moto → bicicleta |

## Onde entra no pipeline

```
mensagem
  ├─ 1. Normalização ....... + expressões ("dar um jeito" → resolver)
  │                          + lemas ("fui" → ser), só fora das stopwords
  │                          + léxico: palavra que existe não é "corrigida"
  ├─ 2. Ensino, revisão, dicionário (como antes)
  ├─ 2c. Diálogo ........... cumprimento + pedido, desabafo, opinião, "não entendi",
  │                          "e em Portugal?" (addon de diálogo, 0.9+)
  ├─ 3. Intenções (como antes)
  ├─ 4. Intenção social .... não responde "oi" para "como selecionar tudo no windows"
  ├─ 4b. Compreensão ....... tipo da pergunta + assunto; perguntas sobre o Aprendiz
  ├─ 4c. Sem assunto? ...... só palavras de conversa: convida a perguntar, sem buscar
  ├─ 5. Busca (como antes)
  ├─ 6. Nada encontrado? ... a. fora de alcance?  → explica a limitação
  │                          b. busca por sentido (vetores)
  │                          c. recomendação de addon (catálogo da loja)
  └─ 7. Resposta
```

Cada etapa aparece no **Monitor**: lemas e expressões na Normalização,
e as etapas Compreensão, Busca por sentido, Fora de alcance e Recomendação de addon.

## As peças

### Lemas e léxico

O radicalizador (`stemmer.py`) junta "falar", "falei" e "falando", mas não junta formas
irregulares: "fui" e "foi", "fiz" e "fez", "tenho" e "tive". O **lema** é a forma de
dicionário da palavra, e resolve isso. Ele é aplicado depois dos sinônimos e só nas palavras
que não são stopwords, tanto na pergunta quanto no que é indexado. Por isso, ativar ou
desativar o addon **reindexa a base** (a "assinatura do índice" em `meta.assinatura_indice`
inclui os addons de compreensão ativos).

Quando uma forma tem mais de um lema ("casas" → casa ou casar?), o arquivo do addon já traz a
escolha: vence o lema mais frequente. Formas que são elas mesmas um lema ("canto") ficam como
estão, menos as de verbos irregulares muito comuns ("tinha" → ter), com uma lista de exceções
("faca", "sede", "dado", "ia").

O léxico também protege a **correção de digitação**: ela só corrige para palavras da base, e
antes trocava "carro" por "caro" se só "caro" estivesse na base. Agora uma palavra que existe
no português fica como está.

As palavras ficam numa tabela do SQLite (`addon_lexico`), não na memória: o app consulta só as
palavras de cada mensagem, com um cache das 50 mil mais recentes.

### Expressões

Sequências de palavras trocadas por uma forma simples, da mais longa para a mais curta:
"dar um jeito" → resolver, "deu pau" → travou, "pequeno almoço" e "café da manhã" →
desjejum, "carta de condução" → habilitação. A comparação é por palavras (tuplas), sem
expressões regulares vindas do addon.

### Tipo de pergunta e assunto

Frases-gatilho no começo da mensagem ("o que é", "como faço para", "onde fica", "quanto
custa"…), depois de no máximo três palavras de cortesia ("você sabe…", "por favor…"). O
gatilho mais longo vence. O **assunto** é o resto da frase, tirado da mensagem original (com
acentos), e deixa o "não sei" mais preciso: "Entendi que você quer saber o que é
**fotossíntese**, mas ainda não fui ensinado sobre isso."

### Juntar e reinterpretar (1.0)

Três comportamentos do motor (`aprendiz/core/assistente.py`, etapa 5b) para entregar o que a
pessoa quer quando existe na base, mesmo que ela não pergunte do jeito "certo":

| Situação | Exemplo | O que acontece |
|---|---|---|
| **Panorama** (tipo de pergunta `panorama`) | "o que você sabe sobre o carro?", "tem algo sobre o carro?", "me lembra o que tenho que fazer com o carro" | Junta, numa lista, todos os conhecimentos que têm **todas** as palavras do assunto (até 6; os do dono primeiro). Tenta o assunto inteiro ("acordo ortográfico") e, se nada servir, o assunto enxuto. |
| **Pedido composto** | "qual a senha do wifi e o horário da farmácia?" | Divide em "?", ";" ou num " e " seguido de artigo ou palavra de pergunta, busca cada parte sozinha e responde todas. Se uma parte que é claramente pergunta ("qual…", "quando…") não tem resposta, entrega o resto e avisa o que faltou. |
| **Só o assunto** | "quero fazer um bolo" | Se a mensagem inteira não achou nada, busca de novo só o assunto, sem as palavras mais comuns da língua ("fazer"), com o addon de vetores ("bolo"). |

Tudo passa pela mesma busca e pelo mesmo consenso do Híbrido: juntar nunca aceita algo que a
busca normal recusaria. O Monitor mostra as etapas **Panorama**,
**Pedido composto** e **Busca · só o assunto**. O tipo `panorama` exige o Aprendiz 1.0
(addon Compreensão do português 1.4.0+).

### Autoconhecimento

Perguntas sobre o próprio Aprendiz, comparadas com as do addon em duas tentativas:

1. **Frase parecida** (semelhança mínima de 90%), depois de tirar marcadores de conversa do
   começo ("mas", "e", "então", "aí", "tipo", "olha"...): "mas e aí, qual é o seu nome?" vira
   "qual é o seu nome".
2. **Mesmas palavras-chave**, falando com o Aprendiz: se a mensagem tem uma referência a ele
   (você, seu, teu, te, "aprendiz"...) e, sem as stopwords, exatamente as mesmas palavras de uma
   das perguntas do item. "Você tem nome?" casa com "qual o seu nome" (as duas se reduzem a
   `nome`); "nome de cachorro" não (não fala com ele) e "você tem nome de cachorro?" também não
   (sobra "cachorro").

Uma pergunta reconhecida aqui não é tratada como cumprimento ("como você se chama?").
Há dois tipos de item:

- **`funcao`**: a resposta é calculada pelo app na hora. A lista é fechada
  (`recursos.FUNCOES`): `versao`, `addons`, `conhecimentos`, `algoritmos`, `capacidades`,
  `limitacoes`, `privacidade`, `hora`, `data`, `recomendacoes`, `ensinar`.
- **`resposta`**: um texto fixo do addon ("você é uma IA?", "você acessa a internet?").

Se o dono ensinou exatamente aquela pergunta, vale a resposta dele.

### Fora de alcance

Pedidos que um assistente offline não atende: pesquisar na internet, clima, notícias,
cotações, ações no computador, lembretes, outras línguas, contas, escrever textos. Só entram
quando a busca **não** encontrou nada: se o dono ensinou "previsão do tempo", vale o que ele
ensinou.

### Necessidades

O que a pessoa precisa quando fala de um jeito indireto: "estou com fome" → receita, cozinha;
"meu computador travou" → atalhos, gerenciador de tarefas. As palavras deduzidas aparecem no
painel e ajudam a recomendar um addon.

### Jeitos de ensinar (2.6)

O app já reconhece alguns verbos de ensino ("aprenda que…", "anote:…", "lembre que…"). A
seção `ensino` do `compreensao.json` acrescenta outros jeitos de **começar** um ensino, como
as pessoas falam: "a partir de agora a senha do wifi é casa456", "fica sabendo que o portão
abre às 7h", "anota aí: revisão do carro em março". O começo é trocado pela forma padrão
("anote que…") e o resto segue as mesmas regras: com "é", "fica", "custa"… vira um fato com
pergunta; sem isso, uma nota.

Três cuidados evitam guardar o que não é ensino:

- mensagem que termina em `?` nunca é ensino ("anota aí o que eu disse?");
- o jeito de ensinar precisa terminar numa palavra inteira: "anota" não vale para "anotações";
- depois dele precisam vir pelo menos duas palavras.

A comparação é feita letra por letra, em minúsculas e sem acento, sem mudar a posição de
nenhuma letra. Assim o que é guardado mantém a escrita original da mensagem.

### Recomendação de addon

O addon de compreensão leva uma cópia resumida do catálogo da loja oficial (id, nome,
descrição e as palavras de que cada addon trata). Quando nada foi encontrado, o app compara o
**assunto** da pergunta com essas palavras:

- palavras raras pesam mais que as muito comuns ("kota" vale mais que "mudar");
- as primeiras palavras de cada addon (nome, etiquetas, região) pesam mais;
- com vetores, palavras de sentido parecido também contam (com peso menor);
- as necessidades deduzidas somam pontos;
- addons **ativos** não são indicados (a busca já olhou para eles); entre dois quase
  empatados, ganha o que já está instalado.

O resultado vai em `meta.recomendacao` (`id`, `nome`, `descricao`, `acao`: `loja` ou
`ativar`). A interface mostra **Ver na loja oficial** (abre a loja já filtrada no addon, pelo
endereço fixo do app) ou **Ativar e perguntar de novo**. Nada é baixado sozinho.

### Vetores e busca por sentido

Cada palavra vira uma lista de 100 números (um vetor). Palavras de sentido parecido têm
vetores que apontam para direções parecidas, e a semelhança é o **cosseno** do ângulo entre
eles (1 = mesmo sentido). Quando a busca não acha nada, o app procura, para cada palavra da
pergunta que **não** está na base, as palavras da base com cosseno acima de 0,62, e busca de
novo com elas. A resposta avisa: "Não encontrei exatamente essas palavras; procurei pelo
sentido (moto → bicicleta)."

Cuidados para não inventar:

- as mil palavras mais comuns ("quero", "fazer") não são trocadas;
- a nova busca precisa passar do **mesmo limiar** de confiança;
- palavras que só "emprestam" o vetor de outra (formas raras, os **apelidos**) valem menos.

Os vetores também evitam **falsas flexões** (2.3.1). A busca aceita palavras de mesmo começo
como flexão uma da outra ("índices" → "índice"), mas "indicar" e "índice" também começam
igual. Quando as duas palavras têm vetor e o cosseno fica abaixo de 0,15, elas são de
famílias diferentes e não contam como a mesma palavra (`Lexico.sem_relacao()`).

Os vetores ficam num bloco de bytes por addon (`addon_recursos`, ~1,4 MB), lido uma vez; a
tabela de palavras fica no SQLite.

## Diálogo

A compreensão entende **o que** a pessoa pergunta. O diálogo (0.9+, `aprendiz/capacidades/dialogo.py`)
entende **o que ela faz** com a frase, o que um ser humano percebe antes de tudo numa
conversa. Os dados vêm da seção `dialogo` do `compreensao.json`, no addon **Diálogo do
português**; sem ele, nada muda.

| Mensagem | Sem diálogo | Com diálogo |
|---|---|---|
| "Olá, consegue me ajudar?" | a busca acha "ajudei-lhe" (Angola) pela palavra "ajudar" | "Olá! Claro, posso tentar! Me diga o que você quer saber…" |
| "consegue me ajudar com uma gíria de Angola?" | chuta um verbete | "Claro! Me diga qual gíria de Angola você quer saber…" |
| "estou meio perdido hoje" | "Olá! Em que posso ajudar?" (o classificador achou um cumprimento) | acolhe e convida a contar o que está acontecendo |
| "o que você acha da vida?" | responde "leve-leve" | diz com franqueza que não tem opinião própria e mostra o que sabe do assunto |
| "qual o sentido da vida?" | uma regra de gramática com "sentido" | resposta reflexiva, a não ser que você tenha ensinado a sua |
| "não entendi" (depois de uma resposta) | "ainda não fui ensinado" | mostra o texto inteiro de onde a resposta saiu |
| "não era isso" | "ainda não fui ensinado" | lista os outros candidatos da busca anterior e lembra do **Corrigir** |
| "sim" (depois de "quer ativá-lo?") | cumprimento | ativa o addon e responde a pergunta anterior |
| "e em Portugal?" (depois de "o que significa kota em Angola?") | procura "Portugal" | "o que significa kota em Portugal" |

As peças:

- **Aberturas**: cumprimentos no começo da frase ("Olá,", "bom dia,") são separados do resto e
  viram o começo da resposta. Se a frase inteira é um ato ("tudo bem com você?"), o ato vence.
- **Palavras de conversa** ("conseguir", "ajudar", "explicar", "coisa", "hoje"…): sozinhas não
  são assunto. Uma mensagem só com elas não dispara a busca (etapa 4c).
- **Atos de fala**: cada um tem gatilhos, textos de resposta e uma **ação** de uma lista
  fechada do app (`recursos.ACOES_DIALOGO`): `convidar`, `responder`, `acolher`, `crise`,
  `opinar`, `refletir`, `reformular`, `outras_opcoes`, `confirmar` e `negar`. O gatilho aceita
  até duas palavras no meio ("estou **meio** perdido" casa com "estou perdido").
- **Assunto vago**: "uma gíria", "alguma receita" (artigo indefinido) fazem o Aprendiz
  perguntar qual, em vez de chutar.
- **Contexto**: o Aprendiz guarda só a **última troca** da conversa (a pergunta e a resposta,
  com as fontes e os candidatos da busca). É o que basta para "não entendi", "não era isso",
  "sim", "não" e as **continuações** ("e em…", "e no…", "e o…").
- **Crise**: frases de sofrimento grave são reconhecidas em qualquer posição e recebem, antes
  de tudo, os contatos de apoio (CVV 188 no Brasil, SNS 24 em Portugal, número de emergência).

O que o dono ensinou continua valendo mais: se você ensinou exatamente a pergunta, o diálogo
não interfere.

**Limites honestos.** O diálogo não "pensa": reconhece padrões de conversa e escolhe entre
respostas escritas no addon. Ele não cria opiniões, não lembra a conversa inteira e não
responde perguntas abertas com conteúdo que ninguém ensinou. O ganho é não responder fora de
contexto e conduzir a conversa até uma pergunta que a base sabe responder.

## Formato dos arquivos

Descritos em detalhe no início de `aprendiz/addons/recursos.py`:

| Arquivo | Classificação | Conteúdo |
|---|---|---|
| `compreensao.json` | `compreensao` | seções `expressoes`, `tipos_pergunta`, `autoconhecimento`, `fora_de_alcance`, `necessidades`, `catalogo`, `dialogo` (0.9+), `padroes` (2.0) e `ensino` (2.6) |
| `lemas.tsv` | (junto com `compreensao.json`) | `palavra<TAB>lema` ou só `palavra`, já normalizadas |
| `vetores.bin` | `vetores` | binário: cabeçalho, palavras, índice de cada palavra e vetores `int8` |

Segurança: tudo é validado como dado não confiável. Não há regex vinda de addon (só listas de
palavras), as funções de autoconhecimento são uma lista fechada do app, o tamanho do
`vetores.bin` precisa bater exatamente com o cabeçalho e os ids do catálogo só aceitam letras
minúsculas, números e hífen. No diálogo, as ações são uma lista fechada do app e o único
marcador nos textos é `{assunto}`, trocado por texto simples.

## Criar ou atualizar os addons oficiais

No repositório da loja (`aprendiz-addons`):

1. `ferramentas/dados_compreensao.py` gera `lemas.tsv` e `vetores.bin` a partir das fontes
   (lista de lemas de Michal Měchura, sob ODbL, e os vetores do modelo `pt_core_news_md` do
   spaCy). Só é preciso rodar quando essas fontes mudam.
2. `ferramentas/catalogo_compreensao.py` junta `compreensao-base.json` (escrito à mão) com o
   catálogo da loja e gera `compreensao.json`. Rode sempre que um addon da loja mudar.
3. `ferramentas/criar_addon.py` (do app) empacota cada pasta de `fontes/`.

## Licenças dos dados

- **Lemas**: derivados de [lemmatization-lists](https://github.com/michmech/lemmatization-lists),
  de Michal Měchura, sob a Open Database License (ODbL 1.0). O addon de compreensão mantém
  a mesma licença.
- **Vetores**: derivados do pacote `pt_core_news_md` do [spaCy](https://spacy.io/models/pt)
  (Explosion), redistribuídos sob CC BY-SA 4.0.


## Padrões de frase (2.0)

Algumas ideias estão na **estrutura** da frase, e não nas palavras. "Quantos pedidos cada
cliente fez?" é um pedido de contar por grupo; "pedidos" e "cliente" são só o exemplo. A seção
`padroes` do `compreensao.json` guarda essas estruturas:

```json
"padroes": [
  {"padrao": "quantos|quantas * cada|por *", "conceitos": ["agrupar", "contar", "por grupo"]},
  {"padrao": "os|as <n> * mais *", "conceitos": ["limitar", "primeiros", "ordenar"]}
]
```

Peças: a palavra, alternativas `a|b`, a lacuna `*` (de 1 a 3 palavras: o exemplo) e `<n>` (um
número). O padrão é escrito já normalizado (sem acento). Quando ele casa, as palavras das lacunas
saem da busca e os conceitos entram: "quantos pedidos cada cliente fez" é buscado como "quantos
cada fez agrupar contar por grupo". Se a reescrita não acha nada, vale a pergunta original.

Os conceitos precisam ser palavras que os addons de conteúdo usam nos assuntos (`A:`): é assim
que a estrutura da frase chega ao fragmento certo.
