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

O painel "Por que respondi isso?" mostra exatamente essas etapas.

## 1–2. Normalização

`unicodedata.normalize("NFKD", texto)` separa cada letra acentuada em letra + acento.
Depois é só descartar os acentos (caracteres "combinantes"). Por fim, uma expressão
regular troca tudo o que não é letra ou número por espaço.

Remover acentos parece perder informação, mas na prática melhora muito a busca: as pessoas
digitam sem acento o tempo todo.

## 4. Abreviações

Um dicionário simples (`vc → voce`, `oq → o que`). Pode virar mais de uma palavra.
Edite na interface, em **Linguagem → Abreviações**.

## 5. Correção de digitação

Para cada palavra com 4 letras ou mais que **não existe na base de conhecimento**, a
RapidFuzz procura a palavra mais parecida no vocabulário da base. Se a similaridade for
pelo menos 80 (numa escala de 0 a 100), ela é trocada.

O detalhe importante é que o corretor só sugere palavras que **o assistente conhece**.
Ele não tenta "corrigir" para o português em geral, só para o que foi ensinado.

## 6. Sinônimos

Cada termo é trocado pela sua forma principal (`automovel → carro`). Como isso acontece
tanto ao ensinar quanto ao perguntar, os dois lados se encontram.

## 7. Stopwords

Palavras muito comuns (`o`, `de`, `qual`, `voce`) são removidas **da busca**, mas
continuam valendo para a **intenção**: "tudo bem?" é só stopword, e mesmo assim é uma
saudação. A palavra `nao` fica de fora da lista de propósito, porque negação muda o sentido.

## 8. Radicalização (stemming)

`aprendiz/linguagem/stemmer.py` implementa uma versão simplificada do **RSLP**
(Orengo & Huyck, 2001). As regras são aplicadas em passos:

1. plural (`farmacias → farmacia`)
2. feminino (`obrigada → obrigado`)
3. grau (`carrinho → carr`)
4. sufixos de substantivo (`atualizacao → atualiz`)
5. sufixos verbais, só se o passo 4 não agiu (`ensinando → ensin`)
6. vogal final (`carro → carr`)

Cada regra tem um **tamanho mínimo de radical**, para não destruir palavras curtas.

O radicalizador não precisa ser linguisticamente perfeito. Ele precisa ser
**consistente**: a mesma palavra sempre gera o mesmo radical, ao ensinar e ao perguntar.

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

## Entidades: regex

`aprendiz/linguagem/entidades.py` reconhece e-mail, valor em reais, data, horário,
telefone e número. Um trecho já reconhecido não é reconhecido de novo por um padrão mais
genérico. As entidades aparecem no painel de explicação e ajudam a exportação a apontar
possíveis dados pessoais.

## Exercícios sugeridos

1. Troque o radicalizador pelo `nltk.stem.RSLPStemmer` e rode o benchmark. O que melhora?
2. Adicione bigramas (pares de palavras) como atributos no Naive Bayes.
3. Faça o corretor considerar a frequência das palavras na base.
4. Crie uma intenção `data` que responda "hoje é …" usando a entidade reconhecida.
