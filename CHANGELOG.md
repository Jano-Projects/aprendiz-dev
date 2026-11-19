# Histórico de versões

Todas as mudanças relevantes do projeto ficam registradas aqui.
O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/), e as versões
seguem o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Adicionado
- **Números e contas numa forma só** (`aprendiz/linguagem/numeros.py`): "2+2", "dois mais dois"
  e "2 mais dois" viram `2 soma 2`; números por extenso viram algarismos. Datas, hexadecimal e
  "um" como artigo ficam como estão.
- **Teia de porquês nos addons** (início do formato da 2.0): no `perguntas.txt`, linhas `F:`
  (ref), `A:` (assuntos), `Q:` (porquê: `relação | explicação | -> ref`) e `N: raiz`, antes do
  `R:`. O app valida relações e ligações e grava a teia na coluna `conhecimentos.teia`
  (esquema 9). Os assuntos entram no texto de busca.
- **Percurso da teia** (`aprendiz/core/teia.py`): a partir do conhecimento achado, segue os
  porquês ligados em largura, até 3 níveis, parando nas raízes, sem repetir fragmento e cortando
  o elo que já não tem palavra em comum com a pergunta. Atravessa addons (`addon:ref`) e ignora
  os desativados. O caminho aparece em "Por que respondi isso?" (etapa "Teia de porquês").
- **Resposta Trabalhada** (`aprendiz/algoritmos/resposta/trabalhada.py`): o fato achado e a
  cadeia de porquês, contada em profundidade (cada porquê seguido dos porquês do fragmento que
  ele liga). Sem teia, responde como a Direta.
- **Expressão** (`aprendiz/core/expressao.py`): seção `expressao` no `compreensao.json` dos
  addons de linguagem, com frases para abertura, fechamento e cada relação (`{x}` = conteúdo).
  Os addons ativos somam frases e uma é sorteada a cada resposta; sem nenhum, vale um conjunto
  mínimo embutido. A mesma frase não se repete duas vezes seguidas.
- A recomendação de um addon com teia em pelo menos metade dos itens passa a ser a resposta
  **Trabalhada**.

### Mudado
- Percurso da teia: só as relações de causa (`porque`, `regra`, `definicao`, `parte-de`) descem
  até a raiz; as laterais (`diferente-de`, `consequencia`, `exemplo-de`, `antes-de`, `depois-de`)
  valem só no nível 1. O freio de assunto compara os assuntos (`A:`) dos fragmentos, não o texto
  inteiro. Na Trabalhada, o resumo do fragmento ligado só entra quando o porquê não tem texto.
- Versão do app: 2.0.0 (em desenvolvimento).
- **A resposta precisa falar do assunto**: um candidato só é aceito (e só é sugerido) se tiver
  alguma palavra forte da pergunta, comparada pela palavra e não só pelo radical. "O que é um
  ponteiro em C?" não é mais respondido com SQL por causa do apelido de tabela "c" ou do radical
  de "ponto". Palavras curtas valem quando são o assunto declarado (pergunta, variações, `A:`).
- **Palavra informativa**: a regra do assunto ignora as palavras mais comuns da língua (com o
  addon de vetores: "fazer", "quero") e aceita erro de digitação (85% de semelhança: "lefet" →
  "left", mas "where" não vira "while"). Em "o que é X?", o X precisa estar no que o
  conhecimento declara tratar (pergunta, variações, `A:`), não só citado no texto.
- **"Não entendi" vai mais fundo**: com teia, se a resposta anterior não tinha os porquês, ele
  explica os porquês; se já tinha, explica a base (cada conceito em que ela se apoiou).
- **Assunto declarado pesa mais**: a palavra da pergunta que está no que o conhecimento declara
  tratar (pergunta, variações, `A:`) é evidência mais forte do que a solta no texto. Quem bate no
  assunto é aceito até 80% do limiar e, entre os aceitos, vem antes quem bate em mais palavras.
- **Padrões de frase** (`aprendiz/core/padroes.py`): seção `padroes` no `compreensao.json`, com
  estruturas de frase que dizem um conceito ("quantos|quantas * cada|por *" → agrupar, contar).
  As lacunas (`*`) são o EXEMPLO e saem da busca; os conceitos entram. A pergunta só é trocada
  quando a reescrita acha resposta. Aparece em "Por que respondi isso?" (etapa "Padrão de frase").
- **Correção determinística**: o vocabulário do corretor é uma lista ordenada e, entre correções
  igualmente parecidas, vence a que forma um par existente na base ("grup by" → "group by"),
  depois a mais frequente. A mesma pergunta é sempre corrigida do mesmo jeito.
- **Sem resposta pelo corpo do texto**: sem palavra da pergunta no assunto declarado, o texto
  precisa ter todas as palavras informativas; digitação só em palavra que não existe; a busca
  por sentido (vetores) só vale se a troca chegar ao assunto declarado de um conhecimento.
- **Recomendação mede falsos positivos**: perguntas fora do assunto respondidas mesmo assim
  descontam da nota (`acerto − 0,5 × falsos`). O Híbrido só perde se outro tiver 5 pontos a mais
  (na homologação, com perguntas ditas de outro jeito, ele ganhou em todas as levas), e o
  `criar_addon.py --junto` mede com os addons essenciais de linguagem instalados.
- **Cobertura e o melhor no assunto**: no peso do assunto declarado, cada palavra da pergunta
  coberta soma 0,5; o ÚNICO candidato que bate mais que todos no assunto é aceito até 60% do
  limiar ("menor caminho entre duas cidades" → Dijkstra). As folgas não valem quando o DONO
  definiu o limiar (modo estrito respeitado à risca).
- **Gerúndio casa com o infinitivo** na comparação de assuntos ("dividindo" → "dividir"). Só essa
  flexão exata: juntar por radical misturava sentidos ("ligações" e "lista ligada").
- **Padrão mais específico vence**: se um padrão de frase tem palavra fixa onde outro tem lacuna
  ("colocar * no ar" x "colocar o * no *"), vale o mais específico; artigos e preposições não
  decidem.
- **Quem é o assunto vence quem só cita**: no peso do assunto declarado, a palavra na pergunta
  do fragmento (ou nas variações) vale 2 e nos assuntos relacionados (`A:`) vale 1, multiplicado
  pela raridade da palavra entre as perguntas da base ("estrangeira" distingue; "dados" não).
  Palavras comuns da língua ("começa", "zero") entram com metade do peso, em vez de nenhum.
- **Homologação** (`ferramentas/homologar.py`): perguntas de gente de verdade (variações,
  digitação, porquês, resumos, fora do assunto, conversa e um grupo de perguntas INÉDITAS, que
  não estão em addon nenhum, em três levas escritas em momentos diferentes) contra os addons
  reais da loja.
- **Assunto conhecido não é conversa social**: "me fala de banco de dados" não vira resposta de
  ajuda quando a base conhece o assunto, seja qual for o jeito de pedir.

## [1.0.0] - 2026-11-18

Primeira versão estável. A compreensão e o diálogo do português passam a conviver com vários
addons de linguagem ao mesmo tempo, e a interface explica melhor cada modelo.

### Adicionado
- **Vários addons de linguagem juntos** (`aprendiz/linguagem/resolucao.py`): abreviações e
  sinônimos de todos os addons ativos são juntados com regras fixas: o dono vence; o mesmo
  termo com valores diferentes em addons diferentes vira **conflito** e não é trocado até o
  dono escolher; cadeias de sinônimos (`a → b → c`) são seguidas e ciclos são resolvidos pelo
  menor termo. Veja "Vários addons juntos" em `docs/linguagem.md`.
- **Tela Linguagem**: quadro de conflitos (um clique escolhe a opção) e a lista, só leitura, das
  entradas vindas dos addons ativos, com a origem. `GET /api/linguagem` ganhou `de_addons` e
  `conflitos`.
- **Nomes dos modelos**: cada algoritmo tem apelido (Rápido, Didático, Tolerante, Equilibrado,
  Fiel, Resumo), "quando usar" e custo (leve, médio, pesado), exibidos no seletor e em "Como
  funcionam os algoritmos". `GET /api/algoritmos` ganhou `apelido`, `quando_usar` e `custo`.
- **Juntar e reinterpretar** (etapa 5b do pipeline, `docs/compreensao.md`):
  - **panorama**: "o que você sabe sobre o carro?" junta numa lista tudo o que a base sabe sobre o
    assunto. Novo tipo de pergunta `panorama` (`recursos.TIPOS_PERGUNTA`);
  - **pedido composto**: "qual a senha do wifi e o horário da farmácia?" responde as duas partes;
    se uma parte não tem resposta, entrega o resto e diz o que faltou;
  - **só o assunto**: "quero fazer um bolo" busca de novo só por "bolo" quando a frase inteira
    não acha nada.
- **`ferramentas/conferir_addons.py`**: confere conflitos, cadeias e ciclos de linguagem entre
  arquivos `.aprendiz` antes de publicar (sai com código 1 se houver conflito).

### Mudado
- **Sinônimos pelo lema**: sem sinônimo para a palavra escrita, o pipeline tenta o lema dela
  ("automóveis" → "automóvel" → "carro"). A versão da normalização foi para 4, então a base é
  reindexada sozinha ao abrir.
- **Visual 1.0**: resposta do assistente sem balão (lida como texto), compositor flutuante,
  cantos e sombras mais suaves (seção 9 de `aprendiz/web/estilo.css`).

### Corrigido
- **Híbrido (RRF)** exige consenso para aceitar um resultado: um algoritmo confiante sozinho
  não basta mais. "Você tem nome?" e "nome de cachorro" deixam de responder com a regra do
  trema ("nomes estrangeiros"). O motivo aparece em "Por que respondi isso?" (`consenso`).
  Veja `docs/algoritmos.md`.
- **Autoconhecimento** ignora marcadores de conversa no começo ("mas", "e aí", "então") e
  reconhece variações pelas palavras-chave: "mas você tem nome?" e "como você se chama?"
  respondem quem é o Aprendiz, em vez de cair na busca ou num cumprimento.
- **"Talvez você esteja procurando"** só sugere conhecimentos com pelo menos uma palavra em
  comum com a pergunta ("o que é um animal?" não sugere mais "me empresta ou empresta-me").

## [0.9.0] - 2026-11-18

### Adicionado
- **Diálogo** (`aprendiz/core/dialogo.py`): seção `dialogo` no `compreensao.json`, com
  aberturas, palavras de conversa, continuações e **atos de fala** (pedir ajuda, desabafar,
  pedir opinião, pergunta reflexiva, elogio, crítica, "não entendi", "não era isso", "sim",
  "não" e crise). A ação de cada ato é de uma lista fechada (`recursos.ACOES_DIALOGO`). Veja
  "Diálogo" em `docs/compreensao.md`.
- **Contexto da conversa**: a última troca (pergunta, resposta, fontes, candidatos e
  recomendação) é usada por "não entendi" (texto inteiro da fonte), "não era isso" (outros
  candidatos), "sim" (ativa o addon recomendado e responde de novo) e pelas continuações
  ("e em Portugal?" reescreve a pergunta anterior; a resposta mostra como foi entendida).
- Etapa **4c · Sem assunto**: mensagem só com palavras de conversa ("consegue fazer isso?")
  não dispara a busca.
- Cumprimento no começo da frase ("Olá, consegue me ajudar?") vira o começo da resposta, e
  o resto é tratado como mensagem.
- Assunto vago ("me ajuda com uma gíria de Angola?"): o Aprendiz pergunta qual.
- Manifesto: campo opcional **`complementa`** (ids de addons que este completa sem depender).
- "O que você sabe fazer?" e "o que você não faz?" mencionam o diálogo quando ele está ativo.
- `criar_addon.py`: blocos de código (três crases) nas respostas do `perguntas.txt` e do
  `verbetes.txt` são copiados como estão: indentação, linhas em branco e linhas com `#`
  (`#include`, comentários do Python) são mantidas. Bloco aberto e não fechado é recusado.
  Veja "Código nas respostas" em `docs/addons.md`.

### Mudado
- **Grupos de addons**: addons sem recomendação própria (compreensão, diálogo, vetores,
  personalização) herdam o grupo dos addons de que dependem ou que complementam, e, se
  preciso, dos que dependem deles. Antes, todos ficavam em "Sem recomendação".
- `compreensao.json` sem diálogo continua sendo gerado sem a chave `dialogo`, para seguir
  aceito pelas versões 0.7 e 0.8.
- Normalização: `c++` → `cpp`, `g++` → `gpp`, `c#` → `csharp` (antes, "C", "C++" e "C#"
  viravam a mesma palavra "c"). `VERSAO_NORMALIZACAO` 3: a base é reindexada ao abrir.

## [0.8.0] - 2026-11-18

### Adicionado
- **Addons de norma** (classificação `norma`, arquivos `norma.json` e `vocabulario.tsv`): o
  português de um país — vocabulário, ortografia em vigor (Acordo de 1990, anterior ou as
  duas), grafias de outras normas, erros comuns, equivalências entre variantes, verbos e
  regras de gramática. Validados por `aprendiz/normas.py`. Veja `docs/revisao.md`.
- **Revisão de texto** (`aprendiz/core/revisao.py`): erros comuns, grafias de outra norma,
  palavras fora do vocabulário (com sugestões por acento e por uma edição), regras de
  gramática e palavras de outra variante, com o texto revisado. O vocabulário é consultado
  por **busca binária** num bloco de bytes ordenado (milhões de formas sem montar listas na
  memória); "dá-me", "fazê-lo" e "dir-te-ei" são conferidos pelo verbo.
- Regras de gramática só com dados: elementos `palavras`, `classe` (lista fechada) e `nao`
  (um ou vários), opções `opcional` e `na_pergunta`, sugestão com transformações de lista
  fechada (`troca`, `infinitivo`, `gerundio`, `proclise`, `capital`, `minuscula`). Um padrão
  não atravessa vírgula nem fim de frase.
- Na conversa: `revise: …` (também "corrija", "verifique", "confira", com "em Portugal",
  "no Brasil"…), `o certo é X ou Y?`, `como se escreve X?` e `está certo escrever X?`.
- Tela **Revisar texto** (menu lateral), com o texto marcado por nível e o botão **Copiar
  texto revisado**.
- Configuração **Norma da revisão de texto** (`revisao.norma`); sem ela, vale a norma que
  mais combina com o texto (no empate, Brasil e depois Portugal).
- Rotas `GET /api/normas` e `POST /api/revisar`; `GET /api/algoritmos` traz as normas ativas.
- **Variedades nos dicionários**: `regiao.variedades` no manifesto e `variedade` nos verbetes
  (linha `L:` no `verbetes.txt`): "como se diz mandioca no Nordeste?", "batata na Madeira".
- `criar_addon.py` empacota `norma.json` e `vocabulario.tsv` e mostra o resumo da norma.
- "O que você sabe fazer?" menciona a revisão quando há normas ativas.

### Mudado
- Banco: `versao_esquema` 8 (coluna `variedade` em `conhecimentos`; normas em
  `addon_recursos`). Addons de norma não fazem a base ser reindexada.

## [0.7.0] - 2026-11-18

### Adicionado
- **Addons de compreensão** (classificação `compreensao`, arquivos `compreensao.json` e
  `lemas.tsv`) e de **vetores** (classificação `vetores`, arquivo `vetores.bin`). O motor fica
  no app (`aprendiz/core/compreensao.py`, `aprendiz/linguagem/lexico.py`); os addons trazem só
  dados, validados por `aprendiz/recursos.py`. Veja `docs/compreensao.md`.
- Na normalização: **expressões** de várias palavras ("dar um jeito" → resolver), **lemas**
  ("fui" → ser, "fiz" → fazer) e **léxico** (a correção de digitação não troca palavras que
  existem, como "carro" por "caro").
- **Tipo de pergunta e assunto** (o que é, como fazer, onde fica, quanto…), no painel e no
  "ainda não sei" ("Entendi que você quer saber o que é **fotossíntese**…").
- **Autoconhecimento**: perguntas sobre o próprio Aprendiz (versão, addons, o que sabe, o que
  não faz, privacidade, hora, data, como ensinar…), com respostas calculadas na hora.
- **Fora de alcance**: explica por que não atende pedidos impossíveis offline (internet,
  clima, notícias, cotações, lembretes…), só quando a busca não encontrou nada.
- **Necessidades deduzidas** ("estou com fome" → receitas).
- **Recomendação de addon** quando não sabe responder: compara o assunto com o catálogo da
  loja que vem no addon e mostra **Ver na loja oficial** (abre a loja filtrada no addon) ou,
  se ele já estiver instalado e desativado, **Ativar e perguntar de novo**.
- **Busca por sentido** com vetores: troca palavras que não estão na base pelas de sentido
  mais próximo e avisa na resposta.
- `POST /api/loja-oficial` aceita `{"addon": id}` para abrir a loja já filtrada.
- `criar_addon.py` empacota `compreensao.json`, `lemas.tsv` e `vetores.bin`.

### Mudado
- Banco: `versao_esquema` 7 (tabelas `addon_recursos` e `addon_lexico`).
- A base é reindexada quando muda a **assinatura do índice** (regras de normalização + addons
  de compreensão ativos), guardada em `meta.assinatura_indice`.
- Uma frase que começa como pergunta e tem assunto ("como selecionar tudo no windows") não é
  mais respondida como cumprimento quando há addon de compreensão.

## [0.6.0] - 2026-11-18

### Adicionado
- **Dicionário nos dois sentidos** (`aprendiz/core/dicionario.py`): além de "o que significa
  kota?", o app entende "como se diz dinheiro em Angola?", "como se fala aldeia em kriol",
  "qual a gíria pra dinheiro em Moçambique?", "como os angolanos chamam o dinheiro?", "traduza
  aldeia para kriol", "kota em Angola" e "como se diz kota em português?". Sem região, lista o
  termo de cada dicionário instalado.
- Verbetes com **traduções** (`traducoes`, linha `T:`) e **outras grafias** (linhas `V:` a mais).
- Manifesto com **região** do dicionário (`regiao`: nome, artigo e termos).
- **Variações de pergunta** em qualquer addon (`variacoes`, várias linhas `P:` no mesmo bloco):
  jeitos diferentes de perguntar que levam à mesma resposta, nos quatro algoritmos de busca.
- O teste de recomendação de algoritmos usa as variações.
- Botão **Abrir loja oficial** (em Addons, em Configurações e na confirmação de um addon
  oficial): abre no navegador padrão do sistema o endereço fixo da loja
  (`config.URL_LOJA_OFICIAL`), pela rota `POST /api/loja-oficial`, que não aceita outro
  endereço.

### Mudado
- Banco: `versao_esquema` 6 (colunas `variacoes` e `traducoes` em `conhecimentos`).
- Textos do app e da documentação: addons oficiais são distribuídos só pela loja oficial da
  Jano Projects; addons de terceiros são compartilhados diretamente, como arquivo. A tela de
  instalação de um addon "oficial" lembra de conferir o SHA-256 com o da loja.

## [0.5.0] - 2026-11-17

### Adicionado
- **Algoritmo recomendado** no manifesto dos addons (`recomendado`: busca, resposta e acerto).
  `criar_addon.py` e a exportação calculam a recomendação testando os quatro algoritmos de
  busca com o próprio conteúdo (`aprendiz/core/recomendacao.py`).
- Na instalação: a recomendação aparece na confirmação, com as opções **Usar como padrão** e
  **Ativar também os addons do mesmo grupo**.
- **Grupos de addons** na tela de Addons, pela recomendação: ativar ou desativar o grupo
  inteiro e **Usar este grupo** (ativa, aplica o padrão e oferece desativar os de outros
  padrões).
- Na exportação: resultado do teste, escolha da busca e da resposta recomendadas e o botão
  **Testar de novo**.
- Rotas `GET /api/addons/grupos`, `POST /api/addons/grupo`, `PUT /api/padrao` e
  `POST /api/exportar/recomendar`.

### Mudado
- A etapa de busca do pipeline virou o método `Assistente.buscar()`, reaproveitado pelo teste
  de recomendação.
- README e documentação descrevem só o que o projeto faz hoje (sem roteiro de planos).

## [0.4.1] - 2026-11-17

### Adicionado
- **Verbetes** (tipo de conhecimento para dicionários): respondem só à palavra sozinha ou a
  "o que significa…"; numa frase com outras palavras, são ignorados. Se vários dicionários
  tiverem a mesma palavra, a resposta mostra todos.
- `linguagem.json` dos addons aceita `stopwords` e `intencoes` (frases de treino do
  classificador), válidos só com o addon ativo.
- `criar_addon.py`: blocos `V:` (verbete) e o arquivo `verbetes.txt`.

### Mudado
- Banco: `versao_esquema` 5 (tabelas `conhecimentos` e `addon_linguagem` aceitam os tipos
  novos; bancos antigos são convertidos ao abrir, sem perder dados).

## [0.4.0] - 2026-11-17

### Adicionado
- **Formato de addon 2**: o manifesto registra `origem` (`oficial` da Jano Projects ou
  `terceiros`), `classificacao` (memória, linguagem, parâmetros, personalização; algoritmo e
  aplicação ficam reservados e são recusados), `app` (versão que gerou e versão mínima) e
  `dependencias` (addons que ele complementa). Addons do formato 1 continuam sendo lidos.
- **Exportar meu conhecimento** (Addons): gera um `.aprendiz` com os itens escolhidos.
  Itens com cara de dado pessoal vêm desmarcados; addons instalados entram só como
  dependências (id, versão e nome), sem copiar o conteúdo.
- **Confirmação antes de instalar**: origem, classificação, totais, versão do app,
  dependências (instalada, desativada, desatualizada ou ausente), parâmetros e amostra.
- **Configurações de parâmetros e personalização**: algoritmos padrão, limiares de cada
  busca, margem de prioridade do dono, nome, cor e mensagem de boas-vindas. Valem na ordem
  dono > addon ativo > padrão, e a interface mostra de onde vem cada valor.
- Addons podem trazer `parametros.json` e `personalizacao.json` (lista fechada de chaves).
- Rotas `POST /api/addons/inspecionar`, `GET/POST /api/exportar` e `/api/configuracoes`.
- Opção "Configurações" no reset da memória.
- Addon de exemplo `modo-exigente` (só parâmetros).

### Mudado
- A escolha de algoritmo nos seletores agora fica no servidor (Configurações), e não mais no
  navegador.
- `/api/algoritmos` mostra o limiar em vigor (e o padrão em `limiar_padrao`).
- O addon de exemplo `conversoes-medidas` passou para a versão 1.1.0, marcado como oficial.
- Banco: `versao_esquema` 4 (coluna `addons.manifesto` e tabela `configuracoes`).

### Corrigido
- Instalador do Windows: depois de instalar o Python, localiza o `python.exe` pelo Registro
  do Windows (PEP 514) e pelo lançador `py`, em vez de supor a pasta. Antes, falhava quando
  já havia outro Python da mesma série instalado em outra pasta. Em caso de erro, mostra o
  final do log do instalador oficial.
- Links do README, CONTRIBUTING e CHANGELOG apontando para `Jano-Projects/aprendiz-dev`, e
  `git clone` do CONTRIBUTING criando a pasta `aprendiz`.
- Nome do job de executáveis no GitHub Actions quando ele é pulado.

## [0.3.0] - 2026-11-17

Primeira versão pública.

### Adicionado
- Explicação de cada algoritmo dentro do app (botão **?** ao lado dos seletores).
- `docs/algoritmos.md` reescrito com um exemplo completo, com números calculados pelo código.
- `docs/estrutura.md`: mapa indentado de pastas e arquivos, gerado a partir dos docstrings
  (`ferramentas/gerar_estrutura.py`). Um teste garante que nenhum arquivo fique sem descrição.
- Sublistas no renderizador de Markdown da interface.
- Arquivos de comunidade: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, modelos
  de issue e de pull request, `.editorconfig`.

### Melhorado
- Sinônimo padrão "hora/horas → horário": "que horas abre?" agora encontra "horário de…".
  O BM25 passou de 89% para 100% de acerto no benchmark, e o Fuzzy de 72% para 83%.
- "wi-fi" e "e-mail" viram "wifi" e "email" na normalização (prefixos de até 2 letras).
- Bancos de versões anteriores recebem os sinônimos novos e são reindexados ao abrir.

## 0.2.0 - 2026-11-17 (desenvolvimento, sem tag)

### Adicionado
- **Addons**: pacotes de conhecimento `.aprendiz` com importação, ativar/desativar,
  atualização por versão, remoção e indicação da origem em cada resposta.
- Prioridade do dono: o que ele ensina vence o conteúdo de addons.
- `ferramentas/criar_addon.py` para criar e conferir addons, e um addon de exemplo
  ("Conversões de medidas").
- Migração automática de bancos da versão 0.1.

## 0.1.0 - 2026-11-17 (desenvolvimento, sem tag)

### Adicionado
- Assistente local e offline: normalização, radicais (RSLP simplificado), intenções
  (Naive Bayes), entidades (regex).
- Seletor de algoritmos: BM25, TF-IDF, Fuzzy e Híbrido (RRF); respostas Direta e Extrativa
  (TextRank).
- Interface de chat com painel "Por que respondi isso?", temas claro e escuro, ícones,
  configurações e reset da memória com cópia de segurança.
- Instaladores para Linux e Windows que instalam o Python se faltar, verificador de
  instalação, executável via PyInstaller e CI em Windows, Ubuntu, Fedora e Debian.

[Não lançado]: https://github.com/Jano-Projects/aprendiz-dev/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/Jano-Projects/aprendiz-dev/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/Jano-Projects/aprendiz-dev/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/Jano-Projects/aprendiz-dev/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/Jano-Projects/aprendiz-dev/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/Jano-Projects/aprendiz-dev/releases/tag/v0.3.0
