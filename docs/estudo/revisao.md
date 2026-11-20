# Revisão de texto e normas da língua

A partir da versão 0.8, o Aprendiz aceita addons de **norma**: cada um traz o jeito de
escrever o português de um país (o vocabulário, a ortografia em vigor, as palavras que lá se
dizem de outro jeito e regras de gramática), e o app passa a **revisar textos**. O motor está
no app (`aprendiz/capacidades/revisao.py`); os addons trazem só dados, validados por
`aprendiz/addons/normas.py`.

A loja oficial distribui uma norma em cada addon de país:

| Addon | Norma | Ortografia | Vocabulário |
|---|---|---|---|
| Português do Brasil (`girias-brasil`) | `pt-BR` | Acordo de 1990 | ~2,9 milhões de formas (VERO, LibreOffice) |
| Português de Portugal (`girias-portugal`) | `pt-PT` | Acordo de 1990 | ~420 mil formas (Projeto Natura) |
| Português de Angola (`girias-angola`) | `pt-AO` | anterior ao Acordo | ~420 mil formas |
| Português de Moçambique (`girias-mocambique`) | `pt-MZ` | anterior ao Acordo | ~420 mil formas |
| Português de Cabo Verde (`expressoes-cabo-verde`) | `pt-CV` | Acordo de 1990 | ~420 mil formas |
| Português da Guiné-Bissau (`expressoes-guine-bissau`) | `pt-GW` | as duas | ~425 mil formas |
| Português de São Tomé e Príncipe (`expressoes-sao-tome-e-principe`) | `pt-ST` | Acordo de 1990 | ~420 mil formas |
| Português de Timor-Leste (`expressoes-timor-leste`) | `pt-TL` | Acordo de 1990 | ~420 mil formas |

Os dicionários oficiais (VOLP, VOC, dicionários das academias) não têm licença aberta; os
vocabulários vêm dos verificadores ortográficos livres do LibreOffice, que seguem as mesmas
normas. Angola e Moçambique não ratificaram o Acordo de 1990, então as suas normas usam a
grafia anterior, montada a partir das anotações do próprio Projeto Natura.

## Como pedir

| Na conversa | O que acontece |
|---|---|
| `revise: Fazem dois anos que não o vejo.` | revisa pela norma escolhida em Configurações (ou pela que mais combina com o texto) |
| `revise em português de Angola: O projeto atual…` | revisa pela norma pedida |
| `corrija o texto no Brasil: …` · `verifique: …` · `confira: …` | também revisam |
| `o certo é exceção ou excessão?` | diz qual das formas está certa na norma |
| `como se escreve económico no Brasil?` | mostra a grafia em cada norma instalada |
| `está certo escrever menas?` | revisa a palavra ou frase |

Também há a tela **Revisar texto** (menu lateral), com o texto marcado e a lista de pontos,
e a rota `POST /api/revisar` (`{"texto": "...", "norma": "pt-PT"}`).

As perguntas curtas ("o certo é…", "como se escreve…") cedem a vez ao que o dono ensinou: se
você ensinou exatamente essa pergunta, vale a sua resposta. Pedidos com dois-pontos
("revise: …") são sempre revisão.

## O que é apontado

Do mais grave ao mais leve (os níveis também aparecem na interface):

| Nível | Exemplo | Entra no texto revisado? |
|---|---|---|
| **Erro** | "fazem dois anos" → faz; "excessão" → exceção | sim |
| **Ortografia** | palavra fora do vocabulário, com sugestões ("carrro" → carro) | sim (primeira sugestão) |
| **Grafia de outra norma** | "facto" no Brasil, "acção" em Portugal, "ação" em Angola | sim |
| **Fora da norma-padrão** | "a gente vamos", "vou no mercado", "Me empresta" | sim |
| **Uso de outra variante** | "autocarro" no Brasil, "estou fazendo" em Portugal | sim |
| **Estilo** | "subir para cima", "há dez anos atrás" | não |
| **Atenção** | falsos amigos ("rapariga" no Brasil), "para mim fazer" | não |

Não são apontados: números, siglas (tudo em maiúsculas), nomes próprios (maiúscula fora do
começo da frase), as palavras que o dono usou no que ensinou e os termos dos verbetes ativos
(gírias e palavras regionais existem!).

## Como funciona

```
texto
  ├─ 1. Tokens ............ palavras com posição, começo de frase, vírgula antes, frase com "?"
  ├─ 2. Várias palavras ... erros comuns e equivalências ("casa de banho", "café da manhã")
  ├─ 3. Cada palavra ...... grafias de outra norma → vocabulário → sugestões
  ├─ 4. Regras ............ padrões de palavras, um a um
  └─ 5. Resultado ......... sem sobreposição (fica o mais grave) + texto revisado
```

### Vocabulário por busca binária

O vocabulário do Brasil tem quase 3 milhões de formas. Montar um `set` com elas custaria
centenas de MB de memória. Em vez disso, o addon guarda as formas **ordenadas**, uma por
linha, num único bloco de bytes (`addon_recursos`, nome `vocabulario`). Para saber se uma
palavra existe, o app faz uma **busca binária** direto nos bytes: escolhe um ponto no meio,
volta até o começo da linha, compara e descarta metade. São ~22 comparações por palavra. Como
o UTF-8 preserva a ordem dos caracteres, a ordem dos bytes é a mesma da lista ordenada em
Python (`normas.Vocabulario`).

Formas como "dá-me", "fazê-lo" e "dir-te-ei" não estão no vocabulário (seriam milhões a
mais): o app separa o verbo do pronome e confere o verbo (`Revisor._existe`).

### Sugestões

Para uma palavra desconhecida, o app gera **candidatas** e fica com as que existem no
vocabulário (a ideia do corretor de Peter Norvig): primeiro a mesma palavra com outros
acentos ("acao" → ação), depois tudo o que está a **uma edição** de distância (letra
apagada, trocada, inserida, duas invertidas) e trocas de som comuns (ss/ç, s/z, x/ch, g/j).
Com o addon de vetores ativo, as mais frequentes vêm primeiro.

### Regras de gramática

Uma regra é uma sequência de **elementos** de tipos fixos — nada de expressão regular ou
código vindo do addon:

```json
{
  "id": "fazer-tempo-inicio", "nivel": "erro", "titulo": "Fazer indicando tempo",
  "padrao": [
    {"classe": "inicio"},
    {"palavras": ["fazem", "faziam", "fizeram"]},
    {"classe": "numero"},
    {"palavras": ["anos", "meses", "dias"]}
  ],
  "sugestao": "{2:troca} {3} {4}",
  "troca": {"fazem": "faz", "faziam": "fazia", "fizeram": "fez"},
  "mensagem": "Indicando tempo decorrido, o verbo «fazer» é impessoal: fica no singular."
}
```

- **Elementos**: `palavras` (uma lista), `classe` (lista fechada do app: `inicio`, `fim`,
  `numero`, `pronome_obliquo`, `pronome_reto`, `gerundio`, `infinitivo`, `participio`,
  `verbo_com_pronome`, `maiuscula`, `qualquer`) e `nao` (um elemento ou uma lista de até 5:
  "nenhum destes"). Opções: `opcional` e `na_pergunta` (a frase termina com "?").
- **Sugestão**: `{n}` é a n-ésima palavra casada; `{n:transformação}` aplica uma da lista
  fechada: `troca` (pelo mapa da regra), `infinitivo` (fazendo → fazer), `gerundio`,
  `proclise` (disse-me → me disse), `capital`, `minuscula`.
- Um padrão **não atravessa vírgula nem fim de frase** ("Estou, fazendo isso" não é
  "estou fazendo").
- O casamento usa retrocesso para os elementos opcionais (`Revisor._casar`).

As classes `gerundio` e `infinitivo` usam a lista de verbos que o addon traz (`verbos`):
assim "mundo" não é gerúndio e "lugar" não é infinitivo.

### Qual norma usar

1. a pedida na mensagem ("em Portugal", "no Brasil", "português de Angola", "pt-PT"; também
   valem as variedades, como "kriol" ou "tétum");
2. a escolhida em **Configurações → Norma da revisão de texto**;
3. a única ativa;
4. a que tem **menos marcas de outra variante** no texto; num empate, a do Brasil e depois a
   de Portugal (`Revisor._mais_provavel`).

## Formato dos arquivos

Descrito em detalhe no início de `aprendiz/addons/normas.py`:

| Arquivo | Classificação | Conteúdo |
|---|---|---|
| `norma.json` | `norma` | `norma` (id, nome, país, ortografia), `fontes`, `grafias` (+ `tipos_grafia`), `erros_comuns`, `equivalencias`, `verbos` e `regras` |
| `vocabulario.tsv` | (junto com `norma.json`) | uma forma por linha, minúsculas, com acentos |

Segurança: tudo é validado como dado não confiável. As formas só aceitam letras, hífen e
apóstrofo; regras só usam tipos, classes e transformações de listas fechadas; o vocabulário é
lido linha a linha (sem montar listas gigantes) e tem limite de 6 milhões de formas.

## Variedades nos dicionários

Os dicionários também ganharam **variedades** (0.8+): regiões dentro do país ("Nordeste",
"Madeira") ou línguas que convivem com o português ("kriol", "tétum", "forro"). Elas ficam no
manifesto (`regiao.variedades`), e cada verbete pode dizer a sua (linha `L:` no
`verbetes.txt`). "Como se diz mandioca no Nordeste?" → macaxeira; "como se diz batata na
Madeira?" → semilha.

## Criar ou atualizar as normas oficiais

No repositório da loja (`aprendiz-addons`):

1. Edite as fontes em `fontes/normas/` (regras, equivalências, erros comuns, grafias e
   palavras extras de cada país; `paises.json` diz o que entra em cada norma).
2. `python ferramentas/dados_normas.py` baixa os dicionários do LibreOffice, gera as formas e
   grava `norma.json` e `vocabulario.tsv` em cada addon (esses dois arquivos não vão para o
   git: saem sempre iguais das fontes).
3. `ferramentas/criar_addon.py` (do app) empacota cada pasta de `fontes/`.

## Licenças dos dados

- **pt-BR**: vocabulário derivado do VERO (Verificador Ortográfico do LibreOffice), de
  Raimundo Santos Moura e colaboradores, sob LGPL-3.0 / MPL.
- **pt-PT e normas africanas e de Timor-Leste**: vocabulário derivado do dicionário do
  Projeto Natura (Universidade do Minho) — José João Almeida, Rui Vilela e Alberto Simões —,
  sob GPL-2.0 / LGPL-2.1 / MPL-1.1.
- Regras, equivalências, erros comuns, verbetes e respostas: Jano Projects, CC BY 4.0.
