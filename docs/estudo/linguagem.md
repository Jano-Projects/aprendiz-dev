# O pipeline de linguagem

Arquivo principal: `aprendiz/linguagem/normalizador.py`.

Vamos seguir a mensagem **"Vc sabe qual o HORÁRIO da farmásia?"** por todas as etapas.

| # | Etapa | Resultado |
|---|---|---|
| 1 | Minúsculas e sem acento | `vc sabe qual o horario da farmasia?` |
| 2 | Pontuação vira espaço | `vc sabe qual o horario da farmasia` |
| 3 | Tokens | `vc` `sabe` `qual` `o` `horario` `da` `farmasia` |
| 4 | Abreviações | `vc → voce` |
| 5 | Correção de digitação | `farmasia → farmacia` |
| 6 | Sinônimos | (nenhum) |
| 7 | Remover stopwords | `horario` `farmacia` |
| 8 | Radicais | `horari` `farmac` |

O Monitor mostra exatamente essas etapas.

## 1–2. Normalização

`unicodedata.normalize("NFKD", texto)` separa cada letra acentuada em letra + acento.
Depois é só descartar os acentos (caracteres "combinantes"). Por fim, uma expressão
regular troca tudo o que não é letra ou número por espaço.

Remover acentos parece perder informação, mas na prática melhora muito a busca: as pessoas
digitam sem acento o tempo todo.

Antes de a pontuação virar espaço, nomes de linguagem com símbolo ganham uma forma própria,
senão "C", "C++" e "C#" virariam a mesma palavra: `c++` → `cpp`, `g++` → `gpp`,
`c#` → `csharp`. (Mudar essa regra muda os radicais gravados; por isso
`VERSAO_NORMALIZACAO` aumenta e a base é reindexada ao abrir o app.)

### Números e contas (2.0)

Ainda nessa etapa, `linguagem/numeros.py` deixa numa forma só o que é a mesma conta escrita de
jeitos diferentes. Antes de a pontuação sumir, `+`, `*`, `×`, `÷` e os `-`, `/`, `x`, `=` entre
números viram palavras; depois, número por extenso vira algarismo e a operação entre dois
números ganha um nome fixo:

| Escrito | Normalizado |
|---|---|
| `2+2`, `dois mais dois`, `2 mais dois` | `2 soma 2` |
| `vinte e cinco` | `25` |
| `três vezes quatro`, `3x4` | `3 multiplicacao 4` |
| `oito dividido por quatro` | `8 divisao 4` |
| `2 mil`, `dois mil`, `2.000` | `2000` |
| `3 milhões`, `três milhões` | `3000000` |

"Um" só vira 1 perto de outro número ou operação (no resto, é artigo), e datas
(`16/11/2026`, `2026-11-16`) e hexadecimais (`0x10`) ficam como estão.

### Cortesia (2.5.1)

Antes de tudo, "por favor", "por gentileza", "pfv", "obrigado" e "valeu" no começo ou no fim da
mensagem saem da busca (`sem_cortesia` em `core/assistente.py`). Sem isso, "por favor, qual a
senha?" podia achar um conhecimento sobre "favor". Se a mensagem for só cortesia, ela fica.

## 4. Abreviações

Um dicionário simples (`vc → voce`, `oq → o que`). Pode virar mais de uma palavra.
Edite na interface, em **Linguagem → Abreviações**. As abreviações dos addons ativos são
juntadas com as suas pelas regras de [Vários addons juntos](#vários-addons-juntos-10).

## 5. Correção de digitação

Para cada palavra com 4 letras ou mais que **não existe na base de conhecimento**, a
RapidFuzz procura a palavra mais parecida no vocabulário da base. Se a similaridade for
pelo menos 80 (numa escala de 0 a 100), ela é trocada.

Desde a 2.5.1 a nota principal é a da distância **OSA** (*Optimal String Alignment*), uma
Levenshtein que conta a **troca de duas letras vizinhas** como um erro só. É o erro de
digitação mais comum, e a Levenshtein comum o contava como dois:

| Digitado | Levenshtein | OSA |
|---|---|---|
| `snhea` → `senha` | 2 erros (60%) | 1 erro (80%) ✔ |
| `lihnas` → `linhas` | 2 erros (67%) | 1 erro (83%) ✔ |

O texto corrigido (`reescrito`) também é o que o dicionário e os padrões de frase leem.

Quando duas correções empatam ("grup" → "grupo" ou "group"), vence a que forma com a palavra
vizinha um **par que existe na base** ("group by"); depois, a mais frequente; por fim, a ordem
alfabética. O vocabulário é uma lista ordenada, então a mesma pergunta é sempre corrigida do
mesmo jeito (2.0).

O detalhe importante é que o corretor só sugere palavras que **o assistente conhece**.
Ele não tenta "corrigir" para o português em geral, só para o que foi ensinado.

## 6. Sinônimos

Cada termo é trocado pela sua forma principal (`automovel → carro`). Como isso acontece
tanto ao ensinar quanto ao perguntar, os dois lados se encontram.

Desde a 1.0, se a palavra escrita não tem sinônimo, o pipeline tenta o **lema** dela (com o
addon de compreensão): com `automovel → carro` cadastrado, "automóveis" também vira "carro".

### Vários addons juntos (1.0)

Antes da 1.0, cada addon trazia pares "termo → valor" e o último instalado sobrescrevia os
outros. Com vários addons de idioma, um termo podia mudar de sentido sem aviso, e uma cadeia
(`automovel → carro`, `carro → veiculo`) parava no primeiro salto. Agora
(`aprendiz/linguagem/resolucao.py`):

| Situação | O que acontece |
|---|---|
| O dono cadastrou o termo | vale a entrada do dono, sempre |
| Vários addons, mesmo valor | vale esse valor (não é conflito) |
| Vários addons, valores diferentes | **conflito**: a palavra não é trocada até o dono escolher |
| Cadeia `a → b → c` (sinônimos) | vira `a → c` e `b → c` |
| Ciclo `a → b → a` (sinônimos) | vira o menor termo do ciclo, em ordem alfabética |

Na tela **Linguagem**, os conflitos aparecem num quadro amarelo: um clique na opção cadastra
a escolha como sua. Abaixo da lista ficam as entradas **vindas dos addons ativos**, com a
origem de cada uma (só leitura; para mudar uma, cadastre o mesmo termo).

Quem cria addons pode conferir isso antes de publicar:
`python ferramentas/conferir_addons.py addons/*.aprendiz` (sai com código 1 se houver conflito).

## 7. Stopwords

Palavras muito comuns (`o`, `de`, `qual`, `voce`) são removidas **da busca**, mas
continuam valendo para a **intenção**: "tudo bem?" é só stopword, e mesmo assim é uma
saudação. A palavra `nao` fica de fora da lista de propósito, porque negação muda o sentido.

## 8. Radicalização (stemming)

`aprendiz/linguagem/stemmer.py` implementa uma versão simplificada do **RSLP**
(Orengo & Huyck, 2001). As regras são aplicadas em passos:

1. plural (`farmacias → farmacia`, `animais → animal`, `homens → homem`, `paes → pao`;
   alguns irregulares, como `maes` e `bois`, ficam numa tabela)
2. feminino (`obrigada → obrigado`)
3. grau (`carrinho → carr`)
4. sufixos de substantivo (`atualizacao → atualiz`)
5. sufixos verbais, só se o passo 4 não agiu (`ensinando → ensin`)
6. vogal final (`carro → carr`)

Cada regra tem um **tamanho mínimo de radical**, para não destruir palavras curtas.

Sem acento, alguns plurais ficam ambíguos: `faceis` pode vir de `fácil` (-il átono) ou de
`fiel` (-el). Esses casos estão listados como limitação conhecida em
`tests/test_correcoes_251.py` (veja [Testes](testes.md)).

O radicalizador não precisa ser linguisticamente perfeito. Ele precisa ser
**consistente**: a mesma palavra sempre gera o mesmo radical, ao ensinar e ao perguntar.

## Com um addon de compreensão (0.7+)

Mais três passos entram no caminho, todos explicados em [compreensao.md](compreensao.md):

- **expressões** (antes dos sinônimos): "dar um jeito" → resolver;
- **lemas** (depois dos sinônimos, fora das stopwords): "fui" → ser, "fiz" → fazer;
- **léxico** na correção de digitação: palavra que existe no português não é corrigida.

## Intenções: Naive Bayes

`aprendiz/linguagem/intencoes.py`. Treinado com as frases de exemplo da tabela
`intencoes_exemplos` (editáveis em **Linguagem → Intenções**).

```
P(intenção | palavras) ∝ P(intenção) × Π P(palavra | intenção)
```

- **Suavização de Laplace (+1):** evita probabilidade zero para palavras inéditas numa intenção.
- **Logaritmos:** somar logs evita que o produto de muitos números pequenos vire zero (underflow).
- **Softmax:** converte as pontuações em probabilidades que somam 100%.

Uma resposta social só é dada se a mensagem for curta (até 6 palavras), a probabilidade
for de pelo menos 45% e ela for pelo menos o dobro da segunda colocada. Mensagens iguais a
uma frase de exemplo pulam o classificador ("frase exata").

### Palavra com erro de escrita (2.6)

O classificador só conhece as palavras dos exemplos. "obrigadoo" e "valew" não estão em nenhum,
então antes ele não tinha como opinar. Agora, uma palavra **desconhecida** com 4 letras ou mais é
trocada pela palavra mais parecida dos exemplos, se a semelhança letra a letra for de pelo menos
80% (`linguagem/intencoes.py`, com o RapidFuzz): "valew" vira "valeu". Uma palavra que não lembra
nenhum exemplo ("astronomia") fica como está e é ignorada, como sempre foi.

Antes disso foi testada outra ideia: dar ao classificador pedaços de 3 letras de cada palavra.
Ela reconhecia os erros de escrita, mas qualquer assunto novo também ganhava pedaços parecidos
com algum exemplo, e "tem algo sobre astronomia?" virava conversa social. Por isso ficou a
correção pela palavra mais parecida, que só age quando a semelhança é alta.

## Entidades: regex

`aprendiz/linguagem/entidades.py` reconhece e-mail, valor em reais, data (inclusive ISO,
`2026-03-12`), horário, CEP, telefone, percentual e número. Datas e horários impossíveis
(`31/02`, `29/02/2023`, `25:99`) são descartados. Um trecho já reconhecido não é reconhecido de novo por um padrão mais
genérico. As entidades aparecem no painel de explicação e ajudam a exportação a apontar
possíveis dados pessoais.

## Exercícios sugeridos

1. Troque o radicalizador pelo `nltk.stem.RSLPStemmer` e rode o benchmark. O que melhora?
2. Adicione bigramas (pares de palavras) como atributos no Naive Bayes.
3. Faça o corretor considerar a frequência das palavras na base.
4. Crie uma intenção `data` que responda "hoje é …" usando a entidade reconhecida.
