# Como funcionam os algoritmos

Todos os algoritmos ficam em `aprendiz/algoritmos/`. A mesma explicação, em versão curta,
aparece no app, no botão **?** ao lado dos seletores.

Toda resposta passa por duas etapas:

```
pergunta ──► normalização ──► BUSCA ──► candidatos ──► limiar ──► RESPOSTA ──► texto final
             (radicais)       (bm25,     (com          (descarta   (direta,
                               tfidf,     confiança)    os fracos)  extrativa)
                               fuzzy,
                               hibrido)
```

Cada algoritmo de busca devolve candidatos com dois números:

- **pontuação**: o valor "bruto" do algoritmo, usado para ordenar;
- **confiança**: de 0 a 1, comparada com o **limiar** do algoritmo. Abaixo do limiar, o
  candidato é descartado. Se nenhum sobrar, o assistente diz que não sabe (modo estrito).

Todos os números deste documento foram **calculados pelo próprio código**. Para reproduzir,
ensine os três itens abaixo num banco vazio e use o painel "Por que respondi isso?".

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
em "Por que respondi isso?" (campo `consenso`), mas não vira resposta. Já "o que é trema?" passa
pela condição 4.

**Bom para:** o resultado mais robusto. **Limite:** roda os três algoritmos, então é o mais lento.

---

## 5. Resposta direta (`resposta/direta.py`)

Devolve o conteúdo do melhor candidato aceito, como foi ensinado.
No exemplo: **"8h às 20h, de segunda a sábado."**

## 6. Resposta extrativa (`resposta/extrativa.py`)

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

## 7. Resposta trabalhada e teia de porquês (2.0)

A **teia** (`core/teia.py`) liga os fragmentos dos addons pelos porquês escritos no
`perguntas.txt` (linhas `F:`, `A:`, `Q:`, `N:`; veja [addons.md](addons.md)). A partir do
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

## 8. Entender a pergunta antes de buscar (2.0)

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

`python benchmarks/comparar.py --detalhes`, com os dados de exemplo (14 conhecimentos,
18 perguntas com resposta e 5 sem):

| Algoritmo | Acerto@1 | Recusas indevidas | Estrito (não inventou) |
|---|---|---|---|
| BM25 | 100% | 0 | 3/5 |
| TF-IDF | 100% | 0 | 3/5 |
| Fuzzy | 83% | 2 | 4/5 |
| Híbrido | 100% | 0 | 3/5 |

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
5. Crie o seu algoritmo seguindo [criar-algoritmo.md](criar-algoritmo.md).
