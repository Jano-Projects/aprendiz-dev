# Addons

Addons são **pacotes prontos** para o Aprendiz: um assunto (conversões de medidas, atalhos do
Linux, regras de um jogo…) ou um ajuste (um tema de cores, limiares mais exigentes) num arquivo
`.aprendiz`, importado pelo app em **Addons → Importar addon**.

Há dois caminhos de distribuição:

- **Addons oficiais:** feitos pela Jano Projects e distribuídos **somente** pela
  [loja oficial](https://jano-projects.github.io/aprendiz-addons/). No app, o botão
  **Addons → Abrir loja oficial** (também em Configurações e na confirmação de um addon
  oficial) abre a loja no navegador do sistema. O endereço é fixo no código
  (`aprendiz/config.py`, `URL_LOJA_OFICIAL`): a interface só pede ao servidor local "abra a
  loja", sem mandar endereço, então nenhum addon ou página consegue redirecionar para outro
  lugar.
- **Addons de terceiros:** feitos por qualquer pessoa (inclusive pela exportação do app) e
  compartilhados **diretamente**, como arquivo. A loja oficial não publica addons de terceiros.

- **Antes de instalar**, o app mostra o que o addon traz: origem, classificação, totais,
  versão do Aprendiz usada, dependências, parâmetros que ele ajusta e uma amostra.
- Cada addon pode ser **ativado ou desativado** a qualquer momento. Desativar só esconde o
  addon; nada é apagado.
- **O que o dono ensina e configura tem prioridade.** Se você e um addon souberem a mesma
  coisa, vale a sua resposta. O mesmo vale para sinônimos, abreviações, parâmetros e
  personalização.
- Importar de novo um addon com o mesmo `id` **atualiza** o addon: o conteúdo é substituído e a
  escolha de ativo/desativado é mantida.
- Cada resposta mostra de qual addon veio a informação.
- O reset da memória tem opções separadas para addons e para configurações.

## Exportar o seu conhecimento

Em **Addons → Exportar meu conhecimento…** o app gera um `.aprendiz` com o que **você**
ensinou, para compartilhar:

1. Escolha nome, versão, autor, licença e descrição.
2. Marque os itens: conhecimentos, sinônimos e abreviações que você acrescentou, parâmetros e
   personalização que você definiu.
3. Os **addons instalados** aparecem como **dependências**: vai só o nome e a versão de cada
   um, nunca o conteúdo. Quem receber instala cada dependência da fonte original (isso respeita
   a licença de cada addon e evita cópias desatualizadas).

Itens com cara de **dado pessoal** vêm **desmarcados** e com um aviso: senha, e-mail, telefone,
CPF, número longo, endereço, chave Pix… É uma heurística (`aprendiz/core/exportacao.py`):
ajuda a revisar, mas não substitui a sua leitura.

Todo addon exportado pelo app sai com `"origem": "terceiros"`. Os algoritmos padrão que você
escolheu não vão como parâmetros: vão como **recomendação** (veja abaixo), que quem instala
aceita ou não.

## Algoritmo recomendado e grupos

Cada addon pode dizer **qual busca e qual resposta funcionam melhor com ele**:

```json
"recomendado": {"busca": "bm25", "resposta": "direta", "acerto": 1.0}
```

A recomendação não é um palpite: `ferramentas/criar_addon.py` e a exportação do app montam um
Aprendiz temporário só com os itens do addon e fazem perguntas parecidas com as de uma pessoa
(a própria pergunta, a pergunta com um erro de digitação, "o que significa…" nos verbetes, o
começo do texto nas notas). O algoritmo de busca que mais acerta em primeiro lugar é o
recomendado; num empate, vale o mais leve (BM25, TF-IDF, Híbrido, Fuzzy). A resposta é a
**Extrativa** quando a maior parte do conteúdo são textos longos, e a **Direta** nos outros
casos. O `acerto` é a fração das perguntas do teste que aquele algoritmo acertou
(`aprendiz/core/recomendacao.py`).

**Ao instalar**, a tela de confirmação mostra a recomendação e oferece:

- **Usar como padrão:** troca os algoritmos de busca e resposta do app. Vem marcada, a não
  ser que outros addons ativos recomendem um padrão diferente.
- **Ativar também os addons do mesmo grupo** que estiverem desativados.

**Grupos.** Na tela de Addons, os addons aparecem agrupados pela recomendação (por exemplo,
"BM25 · Direta"). Um addon sem `recomendado` que traga `busca.padrao`/`resposta.padrao` em
`parametros.json` entra no grupo desses parâmetros; addons só de personalização ficam em
"Sem recomendação". Em cada grupo:

- **Ativar grupo / Desativar grupo** liga ou desliga todos de uma vez.
- **Usar este grupo** ativa os addons do grupo, aplica o padrão dele e pergunta se deve
  desativar os addons de outros padrões, para todos funcionarem no mesmo ambiente de busca.

**Ao exportar**, o app mostra o resultado do teste com os itens marcados e deixa trocar a busca
e a resposta antes de gerar o arquivo. O botão **Testar de novo** refaz o teste depois de mudar
a seleção.

Algoritmos que não existem na versão do app que instala são aceitos no manifesto, mas a tela
avisa e o padrão atual continua valendo.

## Classificação

O manifesto diz **o que o addon mexe** no Aprendiz. A classificação precisa bater com os
arquivos presentes: o app recusa um addon que declare algo que não traz, ou traga algo que não
declarou.

| Tipo | O que faz | Arquivo | Nesta versão |
|---|---|---|---|
| `memoria` | alimenta a memória | `conhecimentos.json` | aceito |
| `linguagem` | amplia o banco de linguagem | `linguagem.json` | aceito |
| `parametros` | ajusta parâmetros dos algoritmos | `parametros.json` | aceito |
| `personalizacao` | customiza nome, cor e boas-vindas | `personalizacao.json` | aceito |
| `compreensao` | interpretação de texto: tipos de pergunta, expressões, lemas, autoconhecimento, recomendação | `compreensao.json` (+ `lemas.tsv`) | aceito (0.7+) |
| `vetores` | vetores de sentido das palavras | `vetores.bin` | aceito (0.7+) |
| `algoritmo` | habilita um novo algoritmo | (código) | **recusado** |
| `aplicacao` | modifica a aplicação | (código) | **recusado** |

`algoritmo` e `aplicacao` fazem parte do formato, mas o Aprendiz só instala **addons de
dados**: um addon que declare um desses tipos é recusado com uma mensagem clara.

Os addons de **compreensão** e **vetores** não trazem respostas: ensinam o app a interpretar
as perguntas e a indicar o addon certo quando não sabe algo. Veja
[compreensao.md](compreensao.md).

## Origem: oficial ou de terceiros

| Origem | Quem publica | Selo na interface |
|---|---|---|
| `oficial` | a Jano Projects, só pela loja oficial | **Oficial Jano** |
| `terceiros` | qualquer outra pessoa, direto como arquivo (padrão) | **Terceiros**, com aviso para conferir a fonte |

> **Importante:** a origem é uma **declaração do arquivo**. Qualquer pessoa pode escrever
> `"oficial"` num manifesto, e o app não tem como confirmar quem o publicou. Um addon oficial
> verdadeiro vem da loja oficial da Jano Projects, que confere cada arquivo e publica o SHA-256
> dele; um "oficial" recebido por outro caminho merece desconfiança.

## Parâmetros e personalização

Só chaves de uma **lista fechada** (`aprendiz/configuracoes.py`) são aceitas, sempre
validadas. Um addon nunca consegue alterar algo fora desta lista:

| Chave | Tipo | Valores |
|---|---|---|
| `busca.padrao` | parametros | `bm25`, `tfidf`, `fuzzy`, `hibrido` |
| `resposta.padrao` | parametros | `direta`, `extrativa` |
| `limiar.bm25` · `limiar.tfidf` · `limiar.fuzzy` · `limiar.hibrido` | parametros | 0,05 a 1,0 |
| `prioridade_dono.margem` | parametros | 0,5 a 1,0 |
| `personalizacao.nome` | personalizacao | texto de 1 a 30 caracteres |
| `personalizacao.cor` | personalizacao | cor `#RRGGBB` |
| `personalizacao.boas_vindas` | personalizacao | texto de 1 a 200 caracteres |

De onde vem o valor em vigor de cada chave (da maior para a menor prioridade):

1. **o dono**, em Configurações;
2. **um addon ativo** (se vários definirem a mesma chave, vale o instalado mais recentemente);
3. **o padrão** do app.

Em Configurações, cada item mostra de onde vem o valor, e o botão **Padrão** apaga a escolha do
dono (o valor volta a ser o do addon ou o padrão).

## Criar um addon

Crie uma pasta com os arquivos abaixo. Veja os exemplos em `exemplos/addons/`:
`conversoes-medidas/` (memória e linguagem) e `modo-exigente/` (só parâmetros).

```
meu-addon/
├── manifesto.json       (obrigatório)
├── perguntas.txt        pares de pergunta e resposta: o jeito mais fácil
├── verbetes.txt         (opcional) dicionário: blocos V:/T:/R:
├── linguagem.json       (opcional) sinônimos e abreviações
├── parametros.json      (opcional) {"limiar.bm25": 0.6}
├── personalizacao.json  (opcional) {"personalizacao.cor": "#0f766e"}
└── *.md / *.txt         (opcional) textos livres, divididos em trechos
```

**manifesto.json** (o que você escreve)

```json
{
  "id": "conversoes-medidas",
  "nome": "Conversões de medidas",
  "versao": "1.1.0",
  "autor": "Seu nome",
  "descricao": "Uma frase sobre o addon.",
  "licenca": "CC0-1.0",
  "site": "https://exemplo.org",
  "dependencias": [
    {"id": "atalhos-linux", "versao": "1.0.0", "nome": "Atalhos do Linux"}
  ]
}
```

- `id`: de 2 a 63 caracteres, só letras minúsculas, números e hífen. É o que identifica o addon
  nas atualizações, então **não mude o id entre versões**.
- `nome` e `versao` são obrigatórios. Os outros campos são opcionais.
- `origem`: deixe de fora (vira `terceiros`). Só a Jano Projects usa `oficial`, junto com
  `"editor": "Jano Projects"`.
- `dependencias`: addons que este complementa. Não bloqueiam a instalação; a tela de
  confirmação mostra se cada um está instalado, desativado, desatualizado ou ausente.
- `classificacao`, `formato`, `app` e `recomendado` são **preenchidos pela ferramenta** a partir
  dos arquivos, da versão do Aprendiz e do teste dos algoritmos. Para fixar outra recomendação,
  escreva `"recomendado": {"busca": "hibrido", "resposta": "extrativa"}` no manifesto. Para exigir uma versão mínima diferente da atual, informe
  `"app": {"versao_minima": "0.4.0"}`.

**perguntas.txt**

```
# Comentários começam com #
P: quantos ml tem uma xícara de chá
R: Uma xícara de chá tem cerca de 240 ml.

P: quanto vale uma polegada
R: 1 polegada = 2,54 cm.
```

**linguagem.json** (todas as chaves são opcionais)

```json
{
  "sinonimos":   { "chicara": "xicara" },
  "abreviacoes": { "pol": "polegada", "lb": "libra" },
  "stopwords":   ["significa", "significado"],
  "intencoes":   { "saudacao": ["e ai mano", "fala ai"], "agradecimento": ["valeu mano"] }
}
```

- `stopwords` (0.4.1+): palavras que a **busca** ignora enquanto o addon estiver ativo.
- `intencoes` (0.4.1+): frases que treinam o classificador, para o assistente reconhecer
  cumprimentos e agradecimentos regionais. Só as intenções que o Aprendiz já conhece:
  `saudacao`, `despedida`, `agradecimento`, `ajuda`, `pergunta` e `ensinar`.

Tudo isso vale só com o addon ativo, e o que o dono cadastrou tem prioridade.

### Dicionários (verbetes)

Para gírias, regionalismos e termos de um assunto, use **verbetes** (0.4.1+). Um verbete só
responde quando a pessoa digita **a palavra sozinha** ou pergunta **"o que significa…"**; numa
frase com outras palavras ele é ignorado, para não "sequestrar" perguntas sobre outros assuntos:

| A pessoa escreve | Resultado |
|---|---|
| `bué` · `o que significa bué?` · `qual o significado de bué` | o verbete |
| `tem bué de gente na festa` | o verbete é ignorado |

No `verbetes.txt` (ou `perguntas.txt`), escreva `V:` no lugar de `P:`:

```
V: bué
V: bwe
T: muito, bastante
R: **bué** (Angola): muito, bastante. Ex.: «Tem bué de gente na festa.»
```

- Linhas `V:` a mais no mesmo bloco são **outras grafias** do termo (0.6+).
- A linha `T:` traz as **traduções** para o português padrão, separadas por vírgula (0.6+).
  São elas que permitem perguntar no sentido inverso.

Coloque no `linguagem.json` as stopwords da pergunta, para "o que **significa** bué" virar só
"bué": `"stopwords": ["significa", "significado", "quer", "dizer"]`.

E declare no `manifesto.json` a **região** do dicionário (0.6+):

```json
"regiao": {"nome": "Guiné-Bissau", "artigo": "a",
           "termos": ["guine", "guine bissau", "guineense", "guineenses", "kriol"]}
```

- `termos`: como as pessoas se referem ao lugar ou à língua ("em Angola", "no kriol", "os
  angolanos", "a gíria angolana"). Escreva sem acento; o app compara sem acento.
- `artigo`: `o`, `a` ou vazio, para as respostas dizerem "**no** Brasil", "**na**
  Guiné-Bissau", "**em** Angola".

**O que a pessoa pode perguntar** (`aprendiz/core/dicionario.py`):

| Sentido | Exemplos | Resposta |
|---|---|---|
| direto | `kota` · `o que é kota?` · `kota significa o quê?` · `significado de kota` · `o que significa kota em Angola?` · `kota em Angola` | o significado |
| inverso | `como se diz dinheiro em Angola?` · `como se fala aldeia em kriol` · `qual a gíria pra dinheiro em Moçambique?` · `como os angolanos chamam o dinheiro?` · `traduza aldeia para kriol` · `aldeia em kriol` | o termo da região, com o significado |
| inverso, sem região | `como se diz ônibus?` | o termo em cada dicionário instalado |
| "em português" | `como se diz kota em português?` | o significado |

- O termo e as traduções são comparados por **igualdade** (sem acento, no singular ou plural),
  nunca por semelhança: o dicionário só responde quando tem certeza.
- Se a região pedida não tem a palavra, a resposta diz isso e mostra os outros dicionários.
- Se o lugar não tem dicionário instalado ("como se diz dinheiro em inglês?"), a resposta avisa
  e mostra o que existe.
- Frases comuns continuam no caminho normal: "como se chama a capital da França?" ou "fui de
  ônibus em Portugal" não são tratadas como pedidos de dicionário.
- Se o dono ensinou exatamente a mesma pergunta, vale a resposta dele.

Se dois dicionários ativos tiverem a mesma palavra (ex.: "bué" em Portugal e em Angola), a
resposta mostra os dois. Um verbete exato só perde para algo que **o dono** tenha ensinado com
exatamente aquela palavra. Uma palavra que também é cumprimento (ex.: "bondia") recebe resposta
social quando digitada sozinha; "o que significa bondia" traz o verbete.

**Gerar e conferir o arquivo:**

```bash
python ferramentas/criar_addon.py meu-addon                        # gera meu-addon.aprendiz
python ferramentas/criar_addon.py --conferir meu-addon.aprendiz    # mesma validação do app
```

### Variações de pergunta (0.6+)

Num `perguntas.txt`, várias linhas `P:` no mesmo bloco são **jeitos diferentes de perguntar a
mesma coisa**. Todas levam à mesma resposta, em todos os algoritmos de busca:

```
P: como tirar um print de uma parte da tela no windows
P: como fazer captura de tela no windows
P: como tirar print no windows
P: o que faz win shift s
R: Win+Shift+S abre a Ferramenta de Captura…
```

No `conhecimentos.json`, isso é o campo `"variacoes": ["…", "…"]`. A primeira linha `P:` é a
pergunta principal, a que aparece na base de conhecimento. O teste de recomendação também usa
as variações para medir o acerto dos algoritmos.

### Dicas para um bom addon

- Escreva as perguntas do jeito que as pessoas perguntam ("quantos ml tem uma xícara"), não
  como títulos ("Xícara (volume)").
- Uma informação por resposta. Respostas curtas funcionam melhor com a resposta *Direta*;
  textos longos, com a *Extrativa*.
- Use `linguagem.json` para abreviações e grafias comuns do assunto.
- Teste com o benchmark: crie um JSON de perguntas no formato de
  `benchmarks/dados_exemplo.json` e rode `python benchmarks/comparar.py --dados ...`.

## O formato `.aprendiz` (versão 2)

É um **ZIP comum** com arquivos JSON (UTF-8) e, nos addons de compreensão, uma lista de
palavras (`lemas.tsv`) e um binário de vetores (`vetores.bin`):

| Arquivo | Obrigatório | Conteúdo |
|---|---|---|
| `manifesto.json` | sim | o manifesto completo (abaixo) |
| `conhecimentos.json` | se `memoria` | lista de `{"pergunta"?, "conteudo", "tipo"?, "variacoes"?, "traducoes"?}`; `tipo` é `pergunta`, `nota`, `trecho` ou `verbete` (0.4.1+); `variacoes` e `traducoes` (só em verbetes) são listas de textos (0.6+) |
| `linguagem.json` | se `linguagem` | `{"sinonimos": {...}, "abreviacoes": {...}}` |
| `parametros.json` | se `parametros` | `{"chave": valor}` da lista fechada |
| `personalizacao.json` | se `personalizacao` | `{"chave": valor}` da lista fechada |
| `compreensao.json` | se `compreensao` | regras de interpretação (0.7+; veja [compreensao.md](compreensao.md)) |
| `lemas.tsv` | não | léxico e lemas, junto com `compreensao.json` (0.7+) |
| `vetores.bin` | se `vetores` | vetores de palavras, binário validado byte a byte (0.7+) |

**Manifesto completo** (como fica dentro do arquivo):

```json
{
  "formato": 2,
  "id": "minha-casa",
  "nome": "Minha casa",
  "versao": "1.0.0",
  "autor": "Fulano",
  "descricao": "Coisas da casa",
  "licenca": "CC-BY-4.0",
  "origem": "terceiros",
  "classificacao": ["memoria", "linguagem", "parametros"],
  "app": {"criado_com": "0.4.0", "versao_minima": "0.4.0"},
  "dependencias": [{"id": "conversoes-medidas", "versao": "1.1.0", "nome": "Conversões de medidas"}],
  "recomendado": {"busca": "bm25", "resposta": "direta", "acerto": 1.0},
  "criado_em": "2026-11-17"
}
```

- `app.criado_com`: versão do Aprendiz que gerou o arquivo (informativo).
- `app.versao_minima`: se o Aprendiz for mais antigo que isso, o addon é recusado com a
  mensagem "precisa do Aprendiz X ou mais novo".
- Campos desconhecidos são ignorados.

**Formato 1** (Aprendiz 0.2 e 0.3) continua sendo lido: a classificação é deduzida dos arquivos
e a origem vira `terceiros`. Um Aprendiz 0.3 **não** lê o formato 2 e mostra "Formato de addon
não suportado".

Quem gera addons por programa pode usar `aprendiz.addons.criar_pacote()`, que preenche os
campos automáticos e valida o resultado.

## Segurança

Addons vêm da internet, então o Aprendiz os trata como **dados não confiáveis**
(`aprendiz/addons.py`):

- **Só dados, nunca código.** Não existe forma de um addon executar algo; os tipos que
  trariam código são recusados. Os addons de compreensão também não trazem expressões
  regulares (só listas de palavras), e as respostas calculadas pelo app vêm de uma lista
  fechada de funções.
- **Nada é extraído para o disco.** Só os nomes conhecidos são lidos de dentro do ZIP;
  qualquer outro arquivo, inclusive com caminhos como `../../`, é ignorado.
- **Limites:** 50 MB de arquivo, 200 MB descompactados (proteção contra *zip bombs*), 100 mil
  conhecimentos, 20 mil caracteres por conhecimento e 50 dependências.
- **Validação de cada campo**, com remoção de caracteres de controle. O `site` precisa começar
  com `https://`. Parâmetros e personalização só aceitam a lista fechada, com faixas de valor.
- **A classificação precisa bater com o conteúdo**, e o dono vê tudo antes de instalar.
- **Instalação atômica:** ou o addon entra inteiro, ou nada muda.
- Na interface, todo texto de addon é exibido **escapado**, sem risco de HTML ou script.

O que a validação **não** garante é que o conteúdo esteja **correto**, nem que um addon
"oficial" seja mesmo da Jano Projects. Instale addons de fontes em que você confia.
O comando `criar_addon.py --conferir` mostra o SHA-256 de um arquivo, para comparar com o
publicado na loja.
