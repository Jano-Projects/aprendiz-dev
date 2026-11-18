# Addons

Addons são **pacotes prontos** para o Aprendiz. Alguém prepara um assunto (conversões de
medidas, atalhos do Linux, regras de um jogo…) ou um ajuste (um tema de cores, limiares mais
exigentes), gera um arquivo `.aprendiz` e publica. Quem baixa importa pelo app, em
**Addons → Importar addon**.

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

Todo addon exportado pelo app sai com `"origem": "terceiros"`.

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
| `algoritmo` | habilita um novo algoritmo | (código) | **recusado** |
| `aplicacao` | modifica a aplicação | (código) | **recusado** |

`algoritmo` e `aplicacao` já existem no formato, pensando na loja futura, mas esta versão só
aceita **addons de dados**. Um addon que declare um desses tipos é recusado com uma mensagem
clara.

## Origem: oficial ou de terceiros

| Origem | Quem publica | Selo na interface |
|---|---|---|
| `oficial` | a Jano Projects | **Oficial Jano** |
| `terceiros` | qualquer outra pessoa (padrão) | **Terceiros**, com aviso para conferir a fonte |

> **Importante:** por enquanto a origem é só uma **declaração do arquivo**. Qualquer pessoa
> pode escrever `"oficial"` num manifesto. A confirmação virá da loja: o catálogo vai indicar
> quais addons são oficiais e, mais adiante, os arquivos poderão ser assinados.

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
├── verbetes.txt         (opcional) dicionário: blocos V:/R:
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
- `classificacao`, `formato` e `app` são **preenchidos pela ferramenta** a partir dos arquivos e
  da versão do Aprendiz. Para exigir uma versão mínima diferente da atual, informe
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
R: **bué** (Angola): muito, bastante. Ex.: «Tem bué de gente na festa.»
```

E coloque no `linguagem.json` as stopwords da pergunta, para "o que **significa** bué" virar
só "bué": `"stopwords": ["significa", "significado", "quer", "dizer"]`.

Se dois dicionários ativos tiverem a mesma palavra (ex.: "bué" em Portugal e em Angola), a
resposta mostra os dois. Um verbete exato só perde para algo que **o dono** tenha ensinado com
exatamente aquela palavra. Uma palavra que também é cumprimento (ex.: "bondia") recebe resposta
social quando digitada sozinha; "o que significa bondia" traz o verbete.

**Gerar e conferir o arquivo:**

```bash
python ferramentas/criar_addon.py meu-addon                        # gera meu-addon.aprendiz
python ferramentas/criar_addon.py --conferir meu-addon.aprendiz    # mesma validação do app
```

### Dicas para um bom addon

- Escreva as perguntas do jeito que as pessoas perguntam ("quantos ml tem uma xícara"), não
  como títulos ("Xícara (volume)").
- Uma informação por resposta. Respostas curtas funcionam melhor com a resposta *Direta*;
  textos longos, com a *Extrativa*.
- Use `linguagem.json` para abreviações e grafias comuns do assunto.
- Teste com o benchmark: crie um JSON de perguntas no formato de
  `benchmarks/dados_exemplo.json` e rode `python benchmarks/comparar.py --dados ...`.

## O formato `.aprendiz` (versão 2)

É um **ZIP comum** com arquivos JSON (UTF-8):

| Arquivo | Obrigatório | Conteúdo |
|---|---|---|
| `manifesto.json` | sim | o manifesto completo (abaixo) |
| `conhecimentos.json` | se `memoria` | lista de `{"pergunta"?, "conteudo", "tipo"?}`; `tipo` é `pergunta`, `nota`, `trecho` ou `verbete` (0.4.1+) |
| `linguagem.json` | se `linguagem` | `{"sinonimos": {...}, "abreviacoes": {...}}` |
| `parametros.json` | se `parametros` | `{"chave": valor}` da lista fechada |
| `personalizacao.json` | se `personalizacao` | `{"chave": valor}` da lista fechada |

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
  trariam código são recusados.
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

## A loja de addons (planejamento)

A loja será um site estático, sem servidor:

1. Um repositório com os arquivos `.aprendiz` e um `catalogo.json` com nome, descrição,
   versão, classificação, origem, versão mínima do app, link de download e o **SHA-256** de cada
   arquivo. É o catálogo que vai **confirmar** quais addons são oficiais.
2. Uma página (GitHub Pages) que lê o catálogo, permite buscar e baixar.
3. Mais adiante: o app lê o catálogo, confere o SHA-256 antes de instalar e verifica a
   assinatura dos addons oficiais. O comando `criar_addon.py --conferir` já mostra o hash.
