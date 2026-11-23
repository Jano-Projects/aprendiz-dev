# Como funcionam os algoritmos

Todos os algoritmos ficam em `aprendiz/algoritmos/`. A mesma explicação, em versão curta,
aparece no app, no botão **?** ao lado dos seletores.

Toda resposta passa por duas etapas:

```
pergunta ──► normalização ──► BUSCA ──► candidatos ──► limiar ──► RESPOSTA ──► texto final
             (radicais)       (bm25,     (com          (descarta   (direta,
                               tfidf,     confiança)    os fracos)  extrativa)
                               fuzzy,
                               hibrido,
                               calibrado)
```

Cada algoritmo de busca devolve candidatos com dois números:

- **pontuação**: o valor "bruto" do algoritmo, usado para ordenar;
- **confiança**: de 0 a 1, comparada com o **limiar** do algoritmo. Abaixo do limiar, o
  candidato é descartado. Se nenhum sobrar, o assistente diz que não sabe (modo estrito).

Todos os números deste documento foram **calculados pelo próprio código**. Para reproduzir,
ensine os três itens abaixo num banco vazio e use o Monitor.

## A base de exemplo

| # | O que foi ensinado | Texto de busca (radicais) |
|---|---|---|
| 1 | pergunta *"horário da farmácia"* → "8h às 20h, de segunda a sábado." | `horari farmac 8h 20h segund sab` |
| 2 | pergunta *"senha do wifi"* → "A senha do wifi é casa123." | `senh wifi senh wifi casa123` |
| 3 | nota "A farmácia do bairro entrega remédios em casa." | `farmac bairr entreg remedi cas` |

**Pergunta:** *"que horas a farmácia abre?"*

| Etapa | Resultado |
|---|---|
| tokens | `que` `horario` `a` `farmacia` `abre` ("horas" virou "horario" pelo sinônimo padrão) |
| sem stopwords | `horario` `farmacia` `abre` |
| radicais | `horari` `farmac` `abr` |

O desafio: os itens 1 e 3 falam de farmácia, mas só o 1 responde à pergunta.

---

## 1. BM25 (`busca/bm25.py`), o padrão

**Ideia:** um documento é relevante quando contém os termos da pergunta, e termos **raros**
valem mais que termos comuns.

```
score(D, Q) = Σ  IDF(q) · f(q,D)·(k1+1) / ( f(q,D) + k1·(1 − b + b·|D|/média) )
             q∈Q
```

| Parte | O que faz |
|---|---|
| `IDF(q)` | termo raro na base vale mais |
| `f(q,D)` | quantas vezes o termo aparece no documento |
| `k1` | saturação: repetir ajuda, mas cada vez menos |
| `b` | documentos mais longos que a média perdem um pouco |

Quem calcula é o **SQLite**, em C, no índice FTS5 (função `bm25()`). Por isso é o algoritmo
mais leve: nada é carregado na memória.

**Confiança = cobertura**, a fração dos termos da pergunta presentes no documento. A nota
BM25 não serve para isso, porque não tem escala fixa: depende do tamanho da base.

**No exemplo:**

| Candidato | Termos em comum | Cobertura | Limiar 0,5 |
|---|---|---|---|
| 1. horário da farmácia | `horari` `farmac` (2 de 3) | **0,667** | ✅ aceito |
| 3. farmácia do bairro | `farmac` (1 de 3) | 0,333 | ❌ |

**Bom para:** uso geral e máquinas fracas.
**Limite:** sinônimos que não estão no banco de linguagem não se encontram. Sem o sinônimo
"horas → horário", a cobertura do item 1 cairia para 1/3 e nada seria aceito.

---

## 2. TF-IDF + cosseno (`busca/tfidf.py`)

Implementado em Python puro: dá para conferir cada conta à mão.

**Passo 1: IDF de cada termo**, com N = 3 documentos:

```
IDF(t) = log((N + 1) / (df + 1)) + 1
```

| Termo | Aparece em (df) | IDF |
|---|---|---|
| `farmac` | 2 documentos | log(4/3) + 1 = **1,288** |
| todos os outros | 1 documento | log(4/2) + 1 = **1,693** |

**Passo 2: vetor de cada documento**, com peso = TF × IDF, normalizado para comprimento 1.
Documento 1: cinco termos com 1,693 e `farmac` com 1,288. A norma é √(5·1,693² + 1,288²) ≈ 4,0:

```
horari 0,423 · farmac 0,322 · 8h 0,423 · 20h 0,423 · segund 0,423 · sab 0,423
```

**Passo 3: vetor da pergunta.** `abr` não existe na base, então é ignorado:

```
horari 1,693 · farmac 1,288   →  normalizado: horari 0,796 · farmac 0,606
```

**Passo 4: cosseno** = soma dos produtos dos termos em comum:

| Candidato | Conta | Cosseno | Limiar 0,25 |
|---|---|---|---|
| 1 | 0,796 × 0,423 + 0,606 × 0,322 | **0,532** | ✅ |
| 3 | 0,606 × 0,355 | 0,215 | ❌ |

Repare que `farmac`, que aparece em dois documentos, pesa menos que `horari`. É o IDF
fazendo o trabalho: o termo que **diferencia** os documentos decide.

**Bom para:** estudar e para perguntas escritas de outro jeito.
**Limite:** o índice fica na memória e é reconstruído quando a base muda.

---

## 3. Fuzzy (`busca/fuzzy.py`)

**Ideia:** comparar **letras**, não termos. Tolera erros de digitação que escaparam do corretor.

A base é a **distância de Levenshtein**: o número mínimo de inserções, remoções e trocas de
letras para transformar um texto no outro. A RapidFuzz converte isso em nota de 0 a 100:

```
ratio("farmcia", "farmacia") = 93,3     ← falta 1 letra
```

O comparador usado é o **WRatio**, que combina várias estratégias: ignora a ordem das palavras
e lida com textos de tamanhos diferentes. Ele compara as palavras da pergunta (sem
radicalizar) com a **pergunta** de cada par ensinado (ou com o conteúdo, no caso de notas).

**No exemplo** ("horario farmacia abre"):

| Candidato | WRatio | Confiança | Limiar 0,75 |
|---|---|---|---|
| 1. horário da farmácia | 95,0 | **0,950** | ✅ |
| 3. farmácia do bairro… | 85,5 | 0,855 | ✅ (2º lugar) |
| 2. senha do wifi | 37,9 | 0,379 | ❌ |

Os dois sobre farmácia passam do limiar. A resposta *Direta* usa o primeiro.

**Bom para:** erros de digitação e textos curtos.
**Limite:** em notas longas, a pergunta é uma parte pequena do texto e a nota cai.

---

## 4. Híbrido (`busca/hibrido.py`): Reciprocal Rank Fusion

Como juntar três notas em escalas diferentes (BM25 sem limite, cosseno de 0 a 1, WRatio de
0 a 100)? O RRF **ignora as notas** e usa só a **posição** de cada documento em cada lista:

```
RRF(d) = Σ  1 / (60 + posição de d no algoritmo i)
```

**No exemplo:**

| Candidato | BM25 | TF-IDF | Fuzzy | RRF |
|---|---|---|---|---|
| 1. horário da farmácia | 1º → 1/61 | 1º → 1/61 | 1º → 1/61 | **0,04918** |
| 3. farmácia do bairro | 2º → 1/62 | 2º → 1/62 | 2º → 1/62 | 0,04839 |
| 2. senha do wifi | — | — | 3º → 1/63 | 0,01587 |

**Confiança:** a fórmula `0,5 × max(confiança_i / limiar_i)`, limitada a 1, vale exatamente
0,5 (o limiar) quando algum algoritmo atinge o próprio limiar. No item 1, o TF-IDF dá
0,532 / 0,25 = 2,13, então a confiança fica em **1,0**.

**Consenso:** o RRF só ordena, e sempre existe um 1º lugar, mesmo quando nada serve. Por isso,
para **aceitar** um documento o híbrido exige uma destas condições:

1. o Fuzzy quase idêntico (≥ 0,95): a mesma frase, com pequenos erros de digitação;
2. o BM25 (ou dois algoritmos) confiante **e** a pergunta falando do **assunto** do documento:
   alguma palavra dela está na pergunta/variações dele (sem pergunta, nas 12 primeiras palavras
   do conteúdo);
3. dois algoritmos confiantes **e** todas as palavras da pergunta no documento;
4. todas as palavras da pergunta no documento, **escritas exatamente igual**.

BM25 e TF-IDF medem quase a mesma coisa (palavras em comum), então a concordância deles,
sozinha, não basta. Exemplo: "nome de cachorro" contém "nome", e uma regra sobre o trema fala
de "nomes estrangeiros". Nenhuma condição vale, e o documento fica logo abaixo do limiar: aparece
no Monitor (campo `consenso`), mas não vira resposta. Já "o que é trema?" passa
pela condição 4.

**Bom para:** o resultado mais robusto. **Limite:** roda os três algoritmos, então é o mais lento.

---

## 5. Calibrado (`busca/calibrado.py`): pesos aprendidos (2.4)

O Híbrido e o `Assistente` decidem com **regras fixas**: aceitar até 80% do limiar quem bate no
assunto, até 60% quem bate mais que todos, exigir consenso de dois algoritmos… Cada regra
corrigiu um caso real, mas os números delas foram escolhidos à mão. O Calibrado troca essas
regras por **uma conta com pesos aprendidos** a partir de perguntas reais.

**Passo 1: o conjunto de candidatos.** Junta os 10 primeiros de BM25, TF-IDF e Fuzzy.

**Passo 2: os sinais.** Cada candidato vira uma lista de números:

| Sinal | O que mede |
|---|---|
| `bm25_conf`, `tfidf_conf`, `fuzzy_conf` | a confiança de cada algoritmo |
| `bm25_rank`, `tfidf_rank`, `fuzzy_rank` | 1 ÷ posição em cada lista (0 se não apareceu) |
| `cobertura_idf` | cobertura **ponderada pela raridade**: termos raros (ou que nem existem na base) pesam mais |
| `assunto`, `palavras_assunto`, `palavra_forte`, `melhor_assunto` | quanto a pergunta bate no assunto declarado (as mesmas medidas das folgas da 2.0) |
| `cobre_assunto`, `pergunta_exata`, `define` | fala do assunto; é igual a uma variação; é a definição pedida em "o que é X?" |
| `consenso_hibrido`, `regras_bm25` | se as regras fixas aceitariam o candidato |
| `termos` | quantos termos a pergunta tem |

De propósito, nenhum sinal diz **de onde** o conhecimento veio (dono ou addon, nota ou
pergunta, com teia ou sem): o treino só tem perguntas de addons, e o modelo aprenderia a
desconfiar do que o dono ensinou.

**Passo 3: 1ª etapa, a chance de cada candidato (ordena).** Cada sinal é padronizado
(`(x − média) ÷ desvio`, com a média e o desvio do treino) e entra numa soma ponderada,
passada pela **sigmoide**:

```
z = viés + Σ peso_i · sinal_padronizado_i          p = 1 / (1 + e^(−z))
```

Isso é uma **regressão logística**: `p` é a chance de o candidato ser a resposta.

**Passo 4: 2ª etapa, a chance de o 1º estar certo (decide).** Uma segunda regressão
logística olha só dois números, a nota do 1º lugar e a distância para o 2º (em logitos,
`log(p ÷ (1 − p))`), e dá a chance de o 1º lugar ser a resposta certa. Um 1º lugar com nota
média, mas muito à frente do 2º, merece mais confiança do que um empate. Essa chance é a
**confiança**; os outros candidatos ficam na mesma proporção, abaixo dele.

**Passo 5: o limiar sai do custo.** Responder certo vale +1, errado −1, e "ainda não fui
ensinado" −0,5 (recusar é ruim, mas metade de errar). Com chance `p`, responder vale
`p − (1 − p) = 2p − 1`, e compensa quando `2p − 1 > −0,5`, isto é, **`p > 0,25`**. Quem quer
mais cautela sobe o limiar em Configurações: com 0,5, só responde quando acertar é mais
provável do que errar.

**No exemplo** ("que horas a farmácia abre?"):

| Candidato | z | 1ª etapa (chance) | Sinais que mais pesaram |
|---|---|---|---|
| 1. horário da farmácia | 0,406 | **0,600** | `bm25_rank` +1,85, `tfidf_rank` +1,53, `melhor_assunto` +1,17, `assunto` −1,06 |
| 3. farmácia do bairro | −5,424 | 0,004 | `cobertura_idf` −0,66, `cobre_assunto` −0,43 |
| 2. senha do wifi | −7,828 | 0,0004 | `cobertura_idf` −1,44 |

Na 2ª etapa, a nota do 1º (logito 0,41) e a distância para o 2º (5,83 logitos) dão
**0,734** de chance de estar certo: acima de 0,25, responde "8h às 20h".

Repare no peso **negativo** de `assunto`: ele não quer dizer que bater no assunto atrapalha.
`assunto`, `palavras_assunto`, `melhor_assunto` e `palavra_forte` medem quase a mesma coisa, e a
regressão divide o efeito entre eles; somados, puxam para cima. É a **colinearidade**, comum
quando os sinais se parecem.

**De onde vêm os pesos?** De `ferramentas/treinar_calibrado.py`, que roda na máquina de quem
desenvolve, com scikit-learn:

1. instala os addons da homologação num banco temporário;
2. de cada fragmento com variações, separa **uma** variação, que vira pergunta e sai do índice
   (o fragmento não pode ser achado pela própria frase);
3. remove inteiros 10% dos fragmentos: as perguntas deles não têm resposta, e o certo é recusar;
4. divide em treino (70%) e teste (30%) **pelo fragmento**, por um hash, sem sorteio;
5. escolhe a regularização por validação cruzada e treina as duas etapas. A 2ª etapa aprende
   com notas de validação cruzada (cada pergunta pontuada por um modelo que não a viu);
6. grava os números em `calibrado_pesos.py` e as perguntas em `ferramentas/dados/conjunto_calibrado.json`.

O app leva **só os números**: a conta é uma soma por candidato, em Python puro.

**Resultado no teste** (240 perguntas que o modelo não viu: 172 com resposta e 68 sem):

| Busca | Acertou | Errou | Recusou | Inventou (sem resposta) |
|---|---|---|---|---|
| BM25 | 58,7% | 34,9% | 6,4% | 83,8% |
| Híbrido | 52,9% | 40,1% | 7,0% | 83,8% |
| **Calibrado** | **59,9%** | **22,1%** | 18,0% | **57,4%** |

Acerta mais, erra quase metade e inventa menos; recusa mais, que é o preço. Na homologação
(perguntas escritas à mão), faz 221 de 243, contra 231 do Híbrido e 227 do BM25. As regras
fixas foram ajustadas caso a caso com essas mesmas perguntas, então a homologação favorece
quem tem as regras; o conjunto de teste mede a generalização.

**Treinar de novo** quando os addons mudarem bastante:

```
pip install -r requirements/treino.txt   # scikit-learn: só para treinar
python ferramentas/treinar_calibrado.py ../aprendiz-addons
python ferramentas/treinar_calibrado.py ../aprendiz-addons --so-medir   # só mede os pesos atuais
```

**Bom para:** uso geral quando errar custa caro; o Monitor mostra a
chance e os sinais que mais pesaram. **Limite:** roda os três algoritmos, como o Híbrido; só
sabe o que o treino viu; e o filtro do assunto (`_cobre_palavra_forte`) continua valendo, porque
evita confusões entre domínios que o treino quase não tem ("indicar um livro" ≠ "índice").

---

### Ajuste pessoal: a Calibrada aprende com você (2.6)

O treino oficial só viu perguntas escritas a partir dos addons. O ajuste pessoal
(`busca/ajuste_pessoal.py`) continua esse treino **no seu aparelho**, com as suas avaliações:

| Você faz | Vira o exemplo |
|---|---|
| 👍 numa resposta | aquele conhecimento era o **certo**; os outros candidatos da mesma pergunta, **errados** |
| 👎 numa resposta, ou "não era isso" no chat | aquele conhecimento era o **errado** |
| **Corrigir** | o conhecimento novo era o **certo**, o que tinha respondido era o **errado** |

O banco guarda só a pergunta e o conhecimento (tabela `avaliacoes`). Os sinais são calculados
de novo a cada treino, com a base como ela está naquele momento.

**A conta** é a mesma regressão logística do treino oficial, resolvida por descida de gradiente
em Python puro, sem scikit-learn. A diferença está na regularização. O treino oficial puxa os
pesos para **zero**; o ajuste pessoal puxa os pesos para os **oficiais**:

    perda = média das perdas logísticas + λ / (2n) · Σ (peso − peso_oficial)²

Com λ = 5, poucas avaliações quase não mexem no modelo, e uma semana de uso não apaga o que o
treino oficial aprendeu. Quanto mais avaliações, mais a sua opinião pesa. Só a 1ª etapa (os
pesos de cada sinal e o viés) é ajustada; a decisão de responder ou não continua a oficial.

**Quando treina:** a partir de 5 avaliações, e de novo a cada 5 novas. Também dá para treinar
na hora, em **Configurações → Ajuste pessoal da busca**, que mostra:

- quantas avaliações você fez;
- em quantas das suas perguntas com 👍 o certo ficava em 1º lugar com os pesos oficiais e com o
  ajuste. A conta é feita sobre os próprios exemplos do treino, então mostra o que o ajuste
  aprendeu, não uma prova independente;
- a distância entre os pesos pessoais e os oficiais.

**Voltar aos pesos oficiais** desliga o ajuste e mantém as avaliações; dá para treinar de novo
depois. Um treino oficial novo, com outros sinais, descarta o ajuste antigo sozinho, porque os
pesos não teriam mais a que se referir. No Monitor, os detalhes de cada candidato dizem qual
modelo foi usado (`"modelo": "pessoal"` ou `"oficial"`).

O ajuste só vale quando a **Calibrada** é o algoritmo de busca. As avaliações são guardadas
com qualquer algoritmo.

**Levar o ajuste para outra máquina.** Em **Exportar**, o grupo "Ajuste pessoal da busca" põe
os pesos num `ajuste.json` dentro do addon. Vão só números, o peso de cada sinal e o viés;
nenhuma pergunta ou resposta. Média, desvio e a decisão de responder vêm sempre do modelo
oficial de quem instala, e um ajuste feito para uma Calibrada com outros sinais é recusado na
instalação. Quem vale, nesta ordem:

1. o ajuste do **dono**, treinado na própria máquina;
2. o de um **addon ativo** (o instalado por último);
3. o **oficial**.

Quem treina com um addon de ajuste ativo parte dele, e não do oficial: a âncora da
regularização passa a ser os pesos do addon. Desativar ou remover o addon volta ao oficial.

## 6. Resposta direta (`resposta/direta.py`)

Devolve o conteúdo do melhor candidato aceito, como foi ensinado.
No exemplo: **"8h às 20h, de segunda a sábado."**

## 7. Resposta extrativa (`resposta/extrativa.py`)

Para notas longas e arquivos importados. Ela escolhe as **frases** certas em vez de devolver
o texto inteiro.

1. Quebra os até 3 melhores conhecimentos em frases.
2. Dá uma nota a cada frase: **0,7 × relevância + 0,3 × centralidade**.
   - **Relevância:** fração dos termos da pergunta presentes na frase.
   - **Centralidade (TextRank):** o PageRank aplicado a frases. Cada frase "vota" nas frases
     parecidas com ela, e a conta é repetida até estabilizar:
     `nota(i) = (1 − d) + d · Σ_j sim(i,j) / Σ_k sim(j,k) · nota(j)`, com d = 0,85.
3. Devolve as 3 melhores frases, na ordem original.

**Exemplo:** o trecho *"O carro precisa trocar o óleo a cada 10 mil km. O filtro de ar também
deve ser trocado. A calibragem dos pneus é 35 psi na frente e 33 atrás."* e a pergunta
*"qual a calibragem dos pneus?"*:

| Frase | Relevância | Centralidade | Nota |
|---|---|---|---|
| A calibragem dos pneus é 35 psi… | 1,0 | 0,15 | **0,745** |
| O carro precisa trocar o óleo… | 0,0 | 1,0 | 0,300 |
| O filtro de ar também… | 0,0 | 1,0 | 0,300 |

Frases sem nenhum termo da pergunta só entram se não houver outra. Resposta:
**"A calibragem dos pneus é 35 psi na frente e 33 atrás."**

---

## 8. Resposta trabalhada e teia de porquês (2.0)

A **teia** (`core/teia.py`) liga os fragmentos dos addons pelos porquês escritos no
`perguntas.txt` (linhas `F:`, `A:`, `Q:`, `N:`; veja [addons.md](../guias/addons.md)). A partir do
conhecimento achado pela busca, ela desce em **largura** pelos porquês, com quatro freios:

1. **profundidade** máxima de 3 níveis;
2. **raiz**: um fragmento `N: raiz` é a base; não se desce além dele;
3. **assunto**: do nível 2 em diante, só se segue para um fragmento cujos assuntos têm palavra
   em comum com a pergunta ou com o fragmento de partida;
4. **causa x lado**: `porque`, `regra`, `definicao` e `parte-de` descem; `diferente-de`,
   `equivale`, `consequencia`, `exemplo-de`, `antes-de` e `depois-de` valem só no nível 1.

A **resposta trabalhada** (`resposta/trabalhada.py`) conta o fato e, em profundidade, cada
porquê seguido dos porquês do fragmento que ele liga, com as frases da seção `expressao` dos
addons de linguagem (`core/expressao.py`). Sem teia, responde como a Direta. "Não entendi" vai
um nível mais fundo: os porquês, ou a base de cada conceito.

No **dicionário**, a Trabalhada diz os elos diretos de cada verbete (2.1): a mesma ideia em
outras variedades (`equivale`: "grana" ↔ "kumbu") e a mesma palavra com outro sentido
(`diferente-de`: "mina"). São até 5 por relação, só de addons ativos e sem repetir o que já está
na resposta; com mais de um sentido, cada grupo diz de qual ("No sentido de moça: …").

## 9. Entender a pergunta antes de buscar (2.0)

- **Números e contas** (`linguagem/numeros.py`): "dois mais dois" e "2+2" viram `2 soma 2`.
- **Padrões de frase** (`core/padroes.py`): estruturas como "quantos * cada *" dizem o conceito
  (agrupar, contar); as lacunas são o exemplo e saem da busca. Veja [compreensao.md](compreensao.md).
- **A resposta precisa falar do assunto**: o candidato precisa de uma palavra informativa da
  pergunta no que ele declara tratar (pergunta, variações, `A:`) ou, se não tiver, de **todas**
  elas no texto. Erro de digitação só é aceito em palavra que não existe ("copa" não é "cópia").
  Quem bate no assunto declarado é aceito até 80% do limiar e vem antes. A mesma regra de
  digitação vale no peso do assunto: "seta" existe, então não conta como "set" mal digitado.
- **A folga abaixo do limiar exige evidência** (2.3.1): o candidato precisa bater em **duas**
  palavras do assunto ("menor" + "caminho" → Dijkstra) ou numa palavra **forte**, rara entre
  os títulos da base e presente na pergunta dele ("disco" → espaço livre no disco). Uma só
  palavra de contexto ("português", que está em vários títulos) não basta
  (`PALAVRA_FORTE` em `core/assistente.py`).
- **Flexão de verdade** (2.3.1): a folga de flexão aceita palavras de mesmo começo ("índices"
  → "índice"). Com o addon de vetores, o começo igual só conta se as duas palavras forem da
  mesma família de sentido (cosseno ≥ 0,15): "indicar" e "índice" (0,02) ou "numerar" e
  "número" (0,03) só se parecem na escrita. Veja `Lexico.sem_relacao()`.
- **Ordem dos aceitos** (2.1): primeiro quem declarou **exatamente** a pergunta (como pergunta
  ou variação); depois quem bate mais no assunto declarado; num empate em "o que é X", o
  fragmento que **define** ("o que é a linguagem c") vem antes do que só usa o assunto ("laço
  for em c": "for" é palavra vazia em português e some da comparação).
- **Correção determinística**: entre correções igualmente parecidas, vence a que forma um par
  que existe na base ("grup by" → "group by"), depois a mais frequente.

## Homologação

`ferramentas/homologar.py` instala os addons reais da loja e faz perguntas de gente de verdade:
variações, digitação, porquês, resumos, fora do assunto, conversa e três baterias de perguntas
**inéditas**, escritas em momentos diferentes e que não estão em addon nenhum. É a medida de
generalização; os testes do `tests/` medem cada peça isolada.

```
python ferramentas/homologar.py ../aprendiz-addons --busca hibrido
```

## Prioridade do dono sobre os addons

Depois da busca, se o primeiro candidato veio de um **addon** e existe algo ensinado pelo
**dono** com confiança de pelo menos 90% da dele, o do dono passa à frente
(`MARGEM_PRIORIDADE_DONO` em `core/assistente.py`). A margem existe porque respostas mais
longas pontuam um pouco menos em alguns algoritmos, mesmo respondendo à mesma pergunta.

## Benchmark

`python ferramentas/comparar.py --detalhes`, com os dados de exemplo (14 conhecimentos,
18 perguntas com resposta e 5 sem):

| Algoritmo | Acerto@1 | Recusas indevidas | Estrito (não inventou) |
|---|---|---|---|
| BM25 | 100% | 0 | 3/5 |
| TF-IDF | 100% | 0 | 3/5 |
| Fuzzy | 83% | 2 | 4/5 |
| Híbrido | 100% | 0 | 3/5 |
| Calibrado | 100% | 0 | 4/5 |

Os erros de "invenção" mostram o dilema clássico entre **precisão** (não inventar) e
**revocação** (não recusar à toa). "Qual a senha do **banco**?" devolve a senha do wifi,
porque metade dos termos ("senha") bate. Subir os limiares reduz as invenções, mas aumenta
as recusas.

## Exercícios

1. Faça a cobertura do BM25 ponderar cada termo pelo IDF: "banco" é um termo **inexistente**
   na base e deveria pesar mais. Rode o benchmark e compare.
2. Remova o sinônimo "horas → horário" (menu Linguagem) e refaça o exemplo deste documento.
   O que acontece com cada algoritmo?
3. Troque o `WRatio` do fuzzy por `token_set_ratio` e observe as notas longas.
4. Mude os pesos 0,7/0,3 da resposta extrativa.
5. Crie o seu algoritmo seguindo [criar-algoritmo.md](../guias/criar-algoritmo.md).
6. Treine o Calibrado sem `cobertura_idf` (apague o sinal em `calibrado.py`) e compare o
   resultado no teste. Depois, troque o custo de recusar: com −0,25, qual seria o limiar?
