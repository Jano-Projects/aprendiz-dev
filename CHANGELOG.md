# Histórico de versões

Todas as mudanças relevantes do projeto ficam registradas aqui.
O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/), e as versões
seguem o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

Versão em preparação: **2.6.0** (branch `aprendiz-2.6`).

### Mudado
- **A busca padrão passa a ser a Calibrada** (era a BM25). No teste ela acerta 63,0% (BM25
  58,4%) e inventa em 66,2% das perguntas sem resposta (BM25 83,8%); na homologação, 232/249
  (BM25 227). Quem escolheu outra busca nas Configurações continua com a sua.

### Adicionado
- **Jeitos de ensinar vindos do addon**: a seção `ensino` do `compreensao.json` traz outros
  começos de ensino ("a partir de agora…", "fica sabendo que…", "anota aí:…"), que viram fato
  ou nota pelas regras de sempre. Pergunta (`?`) nunca é ensino. Ver
  [Compreensão](docs/estudo/compreensao.md#jeitos-de-ensinar-26).
- **O mais recente vale**: "a partir de agora a senha do wifi é casa456" substitui o fato antigo
  de mesma pergunta e mostra o que era antes. Sem "a partir de agora" (ou "de agora em diante",
  "daqui pra frente"), os dois fatos continuam valendo juntos.
- **Ajuste pessoal da Calibrada**: 👍/👎 nas respostas, "não era isso" e Corrigir viram
  exemplos (tabela `avaliacoes`). A partir de 5, a Calibrada treina no próprio aparelho, em
  Python puro, com os pesos puxados de volta para os oficiais (regularização L2 em direção ao
  modelo oficial). Nova seção em Configurações, rotas `/api/avaliar` e `/api/ajuste`. Ver
  [Algoritmos](docs/estudo/algoritmos.md#ajuste-pessoal-a-calibrada-aprende-com-você-26).
- **Ajuste no addon** (`ajuste.json`, classificação `parametros`): exportar leva os pesos do
  ajuste pessoal para outra máquina, só números. Vale o do dono, depois o de um addon ativo,
  depois o oficial; quem treina por cima de um addon parte dos pesos dele.
- **Calibrada, sinal `pares`**: pares de palavras vizinhas da pergunta que também são
  vizinhos no texto. O treino (`ferramentas/treinar_calibrado.py`) passa a juntar a cada pergunta
  de treino cópias com ruído (cortesia, abreviação, sem acento, letras trocadas); o teste
  continua limpo. `--limiar` em `homologar.py` e em `treinar_calibrado.py` mede outros limiares
  sem mudar o app.
- **Decisão de responder com sinais do 1º lugar**: a 2ª etapa da Calibrada também lê
  `topo_cobertura_idf`, `topo_pares`, `topo_cobre_assunto`, `topo_melhor_assunto`,
  `topo_consenso_hibrido` e `topo_termos`. Modelos antigos seguem com os dois sinais de antes.
- Casos de ensino na homologação (`ferramentas/homologar.py`, grupo "ensino").
- Documento [Versionamento](docs/referencia/versionamento.md): o que faz cada número subir.

## [2.5.1] - 2026-11-22

Uma suíte de testes nova, mais dura, procurou erros que ninguém tinha pensado em escrever, e
achou vários. Esta versão traz os testes e as correções. A homologação com os addons da loja
continua igual (Híbrido 231/243) e as perguntas reescritas (com "por favor", letras trocadas,
abreviações) passaram a acertar como as originais.

### Adicionado
- **Testes metamórficos** (`tests/test_metamorficos.py`): maiúsculas, acentos, cortesia, "me
  explica", letras trocadas, singular/plural e espaços não podem mudar a resposta, nos cinco
  algoritmos de busca, inclusive numa base com armadilhas ("favor", "milhas" × "linhas").
- **Fuzz** (`tests/test_robustez.py`): emoji, SQL, HTML, números gigantes, textos de 5 mil
  palavras e texto aleatório em todas as combinações de busca × resposta.
- **Invariantes** (`tests/test_invariantes.py`): determinismo, ordem de ensino, ensinar e
  esquecer, instalar/remover/desativar addon, exportar e importar, banco reaberto e seis
  threads perguntando ao mesmo tempo.
- **Propriedades dos modelos** (`tests/test_modelos.py`): Naive Bayes, regressão logística da
  Calibrada, TF-IDF, RRF e TextRank, com dados gerados por semente fixa.
- **Homologação como teste** (`tests/test_loja_homologacao.py`, opcional:
  `pytest --loja ../aprendiz-addons`): pisos de acerto por busca e pisos metamórficos.
- Documento [Como o Aprendiz é testado](docs/estudo/testes.md).

### Corrigido
- **Correção de digitação:** letras trocadas de lugar ("snhea", "lihnas") contam como um erro
  só (distância OSA), e não dois. Num empate, ganha a palavra que forma par com a vizinha e a
  mais frequente. O texto corrigido agora também chega ao dicionário e aos padrões de frase.
- **Plurais:** "animais", "papéis", "lençóis", "azuis", "homens", "meses", "países", "pães",
  "limões", "mulheres", "mães", "bois", "leis" e outros passam a ter o mesmo radical do
  singular. Uma palavra de três letras que é o assunto ("pão" → "pães da padaria") passa a
  valer como assunto.
- **Números:** "2 mil", "3 milhões", "dois bilhões" e o separador de milhar ("1.234.567").
- **Cortesia:** "por favor", "por gentileza", "pfv", "obrigado", "valeu" no começo ou no fim
  não entram mais na busca ("por favor" achava o conhecimento sobre "favor").
- **Diálogo:** "me fala qual é a senha do wifi" não é mais tratado como assunto vago.
- **Entidades:** datas ISO ("2026-03-12") e CEP ("01310-100") são reconhecidos; datas e
  horários impossíveis ("31/02", "29/02/2023", "25:99") são descartados.

### Limitações conhecidas
- Plurais que dependem do acento ("fácil"/"fáceis", "herói"/"heróis") ficam registrados como
  `xfail` em `tests/test_correcoes_251.py`.

## [2.5.0] - 2026-11-19

Reorganização do repositório: cada pasta responde a uma pergunta, a raiz ficou só com o que
quem chega precisa ver, e a documentação ganhou um índice. **Nenhum comportamento mudou**: as
respostas, o banco e os addons são os mesmos.

### Mudado
- **Raiz:** de 24 para 16 itens. Ficam os instaladores e executores (`instalar.*`,
  `executar.*`), `README`, `CHANGELOG`, `LICENSE`, `pyproject.toml`, `requirements.txt` e as pastas.
  - `empacotar.sh`, `empacotar.bat`, `iniciar.py` e `ferramentas/instalar-windows.ps1` →
    `distribuicao/` (os scripts de empacotamento voltam sozinhos para a raiz do projeto).
  - `requirements-dev.txt`, `-janela.txt` e `-treino.txt` → `requirements/dev.txt`,
    `janela.txt` e `treino.txt`.
  - `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` e `SECURITY.md` → `.github/`, onde o GitHub
    continua a mostrá-los.
  - `benchmarks/comparar.py` → `ferramentas/comparar.py`; os dados vão para `ferramentas/dados/`.
- **Pacote `aprendiz/`:** nenhum módulo solto na raiz do pacote.
  - `aplicativo/`: `config.py`, `configuracoes.py`, `atualizacao.py` e `desktop.py`.
  - `addons/`: `pacote.py` (o antigo `addons.py`), `recursos.py`, `normas.py` e, saindo de
    `core/`, `exportacao.py` e `recomendacao.py`.
  - `capacidades/`: saindo de `core/`, `compreensao.py`, `dialogo.py`, `dicionario.py` e
    `revisao.py`.
  - `core/` fica só com o pipeline: `assistente.py`, `teia.py`, `padroes.py`, `expressao.py`
    e `monitor.py`.
- **Documentação:** `docs/README.md` (índice, com por onde começar em cada nível) e três pastas:
  `docs/estudo/` (algoritmos, linguagem, compreensão, revisão, Monitor), `docs/guias/` (addons,
  criar algoritmo, empacotamento) e `docs/referencia/` (arquitetura e estrutura). A arquitetura
  ganhou uma tabela com a pergunta que cada pasta responde.

### Para quem tem código que importa o Aprendiz
| Antes | Agora |
|---|---|
| `from aprendiz import addons` | `from aprendiz.addons import pacote` |
| `from aprendiz import recursos, normas` | `from aprendiz.addons import recursos, normas` |
| `from aprendiz import config, configuracoes` | `from aprendiz.aplicativo import config, configuracoes` |
| `aprendiz.atualizacao`, `aprendiz.desktop` | `aprendiz.aplicativo.atualizacao`, `aprendiz.aplicativo.desktop` |
| `aprendiz.core.exportacao`, `aprendiz.core.recomendacao` | `aprendiz.addons.exportacao`, `aprendiz.addons.recomendacao` |
| `aprendiz.core.compreensao`, `dialogo`, `dicionario`, `revisao` | `aprendiz.capacidades.…` |
| `bash empacotar.sh` | `bash distribuicao/empacotar.sh` |
| `pip install -r requirements-dev.txt` | `pip install -r requirements/dev.txt` |
| `python benchmarks/comparar.py` | `python ferramentas/comparar.py` |

`python -m aprendiz`, `instalar.*` e `executar.*` continuam iguais. Quem instalou pelo código
recebe a mudança com "verifique e atualize", como sempre.

## [2.4.0] - 2026-11-19

O repositório passa a ser voltado a **desenvolvedores e estudantes de IA**, do iniciante ao
avançado: uma atualização interna (busca Calibrada, com pesos aprendidos) e uma de interface (o
Monitor, que mostra o que acontece por dentro de cada resposta).

### Adicionado (interface)
- **Monitor** (`aprendiz/web/monitor.js`): painel fixo à direita do chat, no lugar do "Por que
  respondi isso?". Cada mensagem tem o botão **Ver no monitor**.
  - **Pipeline ao vivo:** cada etapa aparece assim que termina, com tempo, início (gráfico de
    Gantt) e dados. A **câmera lenta** espaça as etapas para acompanhar o raciocínio.
  - **Busca:** candidatos, confiança × limiar e, na busca Calibrada, a conta inteira
    (`z = viés + Σ peso·sinal`, `p = σ(z)`), a contribuição de cada sinal num gráfico e a 2ª
    etapa, que decide se responde.
  - **Modelo:** ficha técnica com a **contagem de parâmetros** por componente e por tipo
    (aprendidos, estatísticas, pré-treinados, hiperparâmetros), o treino da Calibrada e o
    ambiente. Com os addons da homologação, ≈ 1,77 milhão de parâmetros, menos de mil aprendidos.
  - **Desempenho:** tempo médio de cada etapa, p90 e memória do processo na sessão.
  - **Glossário:** 34 termos técnicos, de *token* a *validação cruzada*.
  - Dois níveis de leitura: **Iniciante** (palavras simples) e **Avançado** (nomes técnicos,
    fórmulas e o JSON bruto de cada etapa).
- `POST /api/chat/fluxo`: o pipeline ao vivo em NDJSON (uma linha por etapa e, no fim, a
  resposta). `Etapas` ganhou um *ouvinte*, e `Assistente.responder()` aceita `ouvinte=`.
- `GET /api/modelo` e `aprendiz/core/monitor.py`: a ficha técnica e a memória do processo
  (`meta.explicacao.memoria_mb` em cada resposta).
- `docs/monitor.md`: as abas, o fluxo ao vivo, o que conta como parâmetro e exercícios.
- README reescrito para o novo público: para quem é, o Monitor e a trilha de estudo.

### Corrigido
- Na explicação da busca, **aceito** passa a dizer se o candidato passou de verdade (limiar,
  folgas e regra do assunto), e não só se a confiança chegou ao limiar.

### Adicionado (busca)
- **Busca Calibrada** (`aprendiz/algoritmos/busca/calibrado.py`), o primeiro algoritmo com
  pesos **aprendidos**. Em vez das regras fixas do assunto (folgas de 80% e 60%, palavra
  forte, consenso), uma regressão logística pesa os sinais de cada candidato: confiança e
  posição em BM25, TF-IDF e Fuzzy, cobertura ponderada pela raridade, quanto a pergunta bate
  no assunto declarado, pergunta idêntica a uma variação e as próprias regras fixas, que
  viram sinais como os outros.
  - **Duas etapas:** a 1ª dá a chance de cada candidato ser a resposta e ordena; a 2ª olha a
    nota do 1º lugar e a distância para o 2º e dá a chance de o 1º estar certo. Essa chance é
    a confiança.
  - **Limiar 0,25, tirado do custo:** certo vale +1, errado −1 e "não sei" −0,5; responder
    compensa quando a chance passa de 0,25. Ajustável em Configurações (`limiar.calibrado`).
  - No painel "Por que respondi isso?", cada candidato mostra a chance e os sinais que mais
    pesaram.
  - Nenhuma dependência nova no app: os pesos ficam em `calibrado_pesos.py` (gerado) e a conta
    é uma soma em Python puro.
- **Treino** (`ferramentas/treinar_calibrado.py`, com scikit-learn em `requirements-treino.txt`,
  separado para não pesar na instalação de desenvolvimento):
  monta perguntas rotuladas a partir das variações dos addons (uma variação de cada fragmento
  sai do índice e vira pergunta; 10% dos fragmentos são removidos para ensinar a recusar),
  separa treino e teste pelo fragmento, escolhe a regularização por validação cruzada e mede
  o resultado no teste. As 772 perguntas ficam em `benchmarks/conjunto_calibrado.json`.
- `ContextoBusca.sinais_assunto`: as medidas do assunto declarado, entregues pelo `Assistente`
  a qualquer algoritmo que queira usá-las.

### Resultados
- **No teste** (240 perguntas que o modelo não viu): o Calibrado acerta 59,9% (BM25 58,7%,
  Híbrido 52,9%), erra 22,1% (34,9% e 40,1%) e inventa resposta em 57,4% das perguntas sem
  resposta (83,8% nos dois); em troca, recusa 18,0% (6,4% e 7,0%).
- **Benchmark de exemplo:** 100% de acerto e não inventa em 4 de 5, o melhor resultado.
- **Homologação:** 221 de 243 (Híbrido 231, BM25 227). As regras fixas foram ajustadas com
  essas mesmas perguntas; o teste mede melhor a generalização. O padrão continua sendo o BM25.

### Testes
- `tests/test_calibrado.py`: sigmoide, cobertura ponderada, soma dos sinais, 2ª etapa, pesos
  gravados conferem com os sinais medidos, seletor, configurações e limiar do dono.

## [2.3.1] - 2026-11-19

### Corrigido
- **Confusão entre domínios.** "É possível listar ou indicar traduções ou variações da palavra
  aldeia em português?" era respondida com um índice de SQL. Três causas, três correções:
  - **Falsa flexão:** "indicar" casava com "índice" pelo começo igual. Com o addon de
    vetores, palavras de mesmo começo só contam como flexão se forem da mesma família de
    sentido (`Lexico.sem_relacao()`, cosseno ≥ 0,15). O mesmo valia para "numerar"/"número".
  - **Folga com pouca evidência:** quem batia numa única palavra de contexto ("português")
    era aceito abaixo do limiar. A folga agora exige duas palavras do assunto ou uma
    palavra forte (`PALAVRA_FORTE`).
  - **Pedido de dicionário não reconhecido:** o dicionário agora entende pedidos educados
    ("é possível listar…", "você pode me mostrar…"), listas ("traduções ou variações") e
    "sinônimos", "traduções" e "equivalentes" de uma palavra. A pergunta da aldeia responde
    *tabanka* (Guiné-Bissau) e *suku* (tétum).
- **Pedido sobre a palavra sem verbete** ("sinônimos de vilarejo"): responde que não encontrou
  a palavra nos dicionários, em vez de mostrar um texto qualquer que cita "sinônimos". O que o
  dono ensinou com exatamente essa pergunta continua valendo.

### Testes
- `tests/test_confusao.py` e o grupo **confusão** na homologação. Na homologação com os addons
  da loja, todos os algoritmos melhoraram e nenhum caso piorou: Híbrido 226 → 231 de 243,
  BM25 222 → 227, TF-IDF 206 → 211, Fuzzy 159 → 162.

## [2.3.0] - 2026-11-19

### Adicionado
- **Pacote de addons** (`.aprendiz-pacote`): a loja oficial deixa marcar vários addons (ou
  "Marcar todos" num grupo) e baixar um arquivo só, com as dependências incluídas e já na
  ordem de instalação. No Aprendiz, **Importar addon** aceita o pacote: uma confirmação com a
  lista (novo, atualiza ou reinstala) e a instalação de todos; um addon com problema não
  impede os outros. Cada addon do pacote é conferido pelo SHA-256 do `pacote.json`; se algum
  não confere, o pacote inteiro é recusado.

## [2.2.0] - 2026-11-19

### Adicionado
- **Atualização sob pedido** (`aprendiz/atualizacao.py`): um gatilho, nunca automático.
  - No chat: "verifique atualizações" mostra o que há de novo; "verifique e atualize" (ou
    "atualize") aplica. Na janela de addons, o botão **Verificar e atualizar** faz o mesmo.
  - Addons: lê o `catalogo.json` da loja oficial, baixa os instalados com versão maior, confere
    o SHA-256 e instala pelo caminho de sempre (versão mínima do app, dependências). Um addon
    com problema não impede os outros.
  - App: instalado pelo código (pasta com `.git`), faz `git pull --ff-only`, reinstala as
    dependências e pede para reiniciar; executável, aponta a página da última release.

## [2.1.1] - 2026-11-19

### Corrigido
- **"Quais as variações de aldeia em português?"** respondia sobre o português de Moçambique. O
  dicionário passa a entender "variações de X", "outras formas de dizer X" e "X nos países"
  como "como se diz X" em todos os lugares (e "em português" aqui não é a região).
- Em "como se diz X", a lista de lugares já responde: a teia dos verbetes (equivalências) só
  entra no sentido direto ("o que é grana").

### Homologação
- Grupo **contexto**: 12 perguntas em sequência na mesma conversa ("o que é git" → "e como salvo
  uma versão do código?"), escritas antes de mexer no código.
- Testados e descartados (não mudaram nenhum acerto): peso extra para o addon da resposta
  anterior, busca mais funda só nesse addon e juntar a pergunta anterior quando há pronome
  ("por ele"). As falhas que sobram são de palavra, não de contexto: flexão ("salvo" x
  "salvar"), assunto em outro addon (`ROW_NUMBER` no SQL avançado depois do GROUP BY do básico)
  e padrão de frase que leva para outro assunto ("3 primeiros" → LIMIT).

## [2.1.0] - 2026-11-19

Todos os addons de conhecimento da loja passam a ter teia de porquês (C, C++, utilidades e
idiomas). Os addons de idiomas e o `dialogo-portugues` 2.1.0 exigem este app (relação
`equivale`).

### Mudado
- O operador seta do C (`p->campo`) vira "seta" na normalização, em vez de sumir com a
  pontuação (versão 6 das regras de normalização: a base é reindexada ao abrir).
- **Erro de digitação só para palavra desconhecida também no assunto**: "seta" existe, então
  não conta como "set" mal digitado ao comparar a pergunta com o assunto de cada fragmento
  (antes, "usar -> em c" caía no `std::set` do C++).

- **Quem declarou exatamente a pergunta vem primeiro**: se a pergunta é a de um fragmento (ou
  uma variação dele), ele passa à frente dos que só batem no assunto.
- **Definição desempata pelo fragmento que define**: em "o que é c?", vale "o que é a linguagem
  c", e não "laço for em c" ("for" é palavra vazia em português e some da comparação).

- **Relação `equivale` na teia**: liga a mesma ideia em variedades diferentes da língua
  ("grana", no Brasil; "kumbu", em Angola). Os addons de linguagem podem dar frases para ela.
- **Dicionário com teia (resposta Trabalhada)**: depois do verbete, vêm as equivalências em
  outros lugares e os falsos amigos ("mina": moça no Brasil, filho em São Tomé), até 5 de cada,
  só de addons ativos. Com mais de um sentido, cada grupo diz de qual sentido é.

- `criar_addon.py` avisa quando um addon de idioma (com `regiao`) não tem `norma.json`, que é
  gerado e fica fora do git.

### Homologação
- Leva idiomas: 12 perguntas novas e os oito addons de gírias e expressões na lista; o
  esperado `texto:` confere o que a resposta diz.
- Leva utilidades: 15 perguntas novas (terminal Linux, atalhos do Windows e conversões).
- Leva C++: 15 perguntas novas (escritas antes dos porquês) e os três addons de C++ na lista.

## [2.0.1] - 2026-11-19

### Mudado
- **Fragmento com teia precisa bater no assunto**: se o conhecimento declara o que trata (teia),
  citar a palavra no meio do texto não basta ("qual a capital da França?" não é respondida por um
  tutorial que usa a frase de exemplo).
- **Conversa social só vira pergunta pelo assunto declarado**: "valeu, ajudou muito" continua
  conversa, mesmo com "ajudou" num texto da base.
- **Começo comum mais rígido em palavras curtas**: em palavras de 5 letras, a folga de flexão
  juntava palavras diferentes ("valeu" e "vale").

### Documentação
- `docs/arquitetura.md`: o caminho de uma mensagem com as etapas da 2.0 e a seção "Teia,
  padrões e expressão"; `docs/linguagem.md`: números e contas e o desempate do corretor;
  `docs/criar-algoritmo.md`: a resposta Trabalhada como exemplo.
- Os cinco addons "Aprendiz por dentro" (loja) descrevem a 2.0 e têm teia de porquês; a
  homologação ganhou perguntas sobre o próprio Aprendiz.

## [2.0.0] - 2026-11-19

A 2.0 muda o Aprendiz de uma busca que devolve o texto guardado para um assistente que
entende o pedido e explica os porquês. Os addons ganham uma **teia de porquês**: cada fragmento
diz por que é assim e a que outros fragmentos se liga, inclusive em outros addons. Na
homologação com os addons reais da loja, a busca Híbrido acerta 150 de 158 perguntas de gente
de verdade, incluindo três baterias de perguntas inéditas.

### Adicionado
- **Resposta Trabalhada** (`algoritmos/resposta/trabalhada.py`): o fato achado e a cadeia de
  porquês, contada em profundidade, com frases dos addons de linguagem. Sem teia, responde como
  a Direta. "Não entendi" vai um nível mais fundo: os porquês ou a base de cada conceito.
- **Teia de porquês** (`core/teia.py`): percurso em largura a partir do conhecimento achado, até
  3 níveis, parando nas raízes, sem repetir fragmento e cortando o elo que sai do assunto. Só as
  relações de causa descem; as laterais valem no nível 1. Atravessa addons (`addon:ref`) e
  ignora os desativados. Aparece em "Por que respondi isso?".
- **Expressão** (`core/expressao.py`): seção `expressao` no `compreensao.json` dos addons de
  linguagem, com frases para abertura, fechamento e cada relação. Os addons somam frases, uma é
  sorteada a cada resposta, sem repetir a anterior.
- **Padrões de frase** (`core/padroes.py`): seção `padroes` no `compreensao.json`, com
  estruturas que dizem um conceito ("quantos * cada *" → agrupar). As lacunas são o exemplo e
  saem da busca; vence o padrão mais específico. Só troca a pergunta se a reescrita achar
  resposta.
- **Números e contas numa forma só** (`linguagem/numeros.py`): "2+2", "dois mais dois" e
  "2 mais dois" viram `2 soma 2`.
- **Homologação** (`ferramentas/homologar.py`): perguntas reais contra os addons da loja, com
  baterias de perguntas inéditas escritas antes de cada mudança.
- `criar_addon.py --junto`: mede a recomendação com os addons essenciais de linguagem instalados.

### Mudado
- **A resposta precisa falar do assunto**: o candidato precisa de uma palavra informativa da
  pergunta no que ele declara tratar (pergunta, variações, `A:`) ou, se não tiver, de todas elas
  no texto. Erro de digitação só em palavra que não existe ("copa" não é "cópia"). Em "o que é
  X?", o X precisa estar no assunto declarado.
- **Assunto declarado pesa na escolha**: palavra na pergunta do fragmento vale 2, nos assuntos
  vale 1, multiplicado pela raridade entre os títulos; palavras comuns valem metade, siglas de 3
  letras contam quando batem exatamente e o gerúndio casa com o infinitivo. Quem bate no assunto
  é aceito até 80% do limiar (o melhor de todos, até 60%), exceto quando o dono definiu o limiar.
- **Assunto conhecido não é conversa social**: "me fala de banco de dados" vira pergunta.
- **Correção determinística**: a mesma pergunta é sempre corrigida do mesmo jeito; entre
  correções iguais, vence a que forma um par existente na base ("grup by" → "group by").
- **Recomendação de algoritmo**: desconta perguntas fora do assunto respondidas mesmo assim, e o
  Híbrido só perde se outro for 5 pontos melhor.
- Esquema do banco 9 (coluna `conhecimentos.teia`); bancos antigos são migrados ao abrir.

### Formato de addon
- `perguntas.txt` aceita, antes do `R:`, as linhas `F:` (ref), `A:` (assuntos: os nomes do
  próprio conceito), `Q:` (porquê: `relação | explicação | -> ref`) e `N: raiz`.
- `compreensao.json` aceita as seções `expressao` e `padroes`.
- Addons convertidos pedem o Aprendiz 2.0 (`app.versao_minima`); os do formato anterior seguem
  funcionando na 2.0.

### Limitações conhecidas
- A busca é por palavras: perguntas com o assunto escondido atrás de um verbo genérico
  ("transformar meu script em um .exe") ou com palavras muito comuns ("numerar as linhas")
  podem cair noutro fragmento. As perguntas que ainda falham estão na homologação.
- O contexto da conversa ainda não pesa na escolha do assunto.
- A busca por vetores na ordenação foi testada e descartada (piorou a homologação).

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

[Não lançado]: https://github.com/Jano-Projects/aprendiz-dev/compare/v2.5.1...HEAD
[2.5.1]: https://github.com/Jano-Projects/aprendiz-dev/compare/v2.5.0...v2.5.1
[2.5.0]: https://github.com/Jano-Projects/aprendiz-dev/compare/v2.4.0...v2.5.0
[2.4.0]: https://github.com/Jano-Projects/aprendiz-dev/compare/v2.3.1...v2.4.0
[2.3.1]: https://github.com/Jano-Projects/aprendiz-dev/compare/v2.3.0...v2.3.1
[2.3.0]: https://github.com/Jano-Projects/aprendiz-dev/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/Jano-Projects/aprendiz-dev/compare/v2.1.1...v2.2.0
[2.1.1]: https://github.com/Jano-Projects/aprendiz-dev/compare/v2.1.0...v2.1.1
[2.1.0]: https://github.com/Jano-Projects/aprendiz-dev/compare/v2.0.1...v2.1.0
[2.0.1]: https://github.com/Jano-Projects/aprendiz-dev/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/Jano-Projects/aprendiz-dev/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/Jano-Projects/aprendiz-dev/compare/v0.9.0...v1.0.0
[0.9.0]: https://github.com/Jano-Projects/aprendiz-dev/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/Jano-Projects/aprendiz-dev/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/Jano-Projects/aprendiz-dev/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/Jano-Projects/aprendiz-dev/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/Jano-Projects/aprendiz-dev/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/Jano-Projects/aprendiz-dev/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/Jano-Projects/aprendiz-dev/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/Jano-Projects/aprendiz-dev/releases/tag/v0.3.0
