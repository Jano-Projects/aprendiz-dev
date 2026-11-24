# Como o Aprendiz é testado

Um modelo de linguagem raramente "quebra" com um erro na tela. Ele erra em silêncio: responde
outra coisa, com confiança. Por isso a suíte de testes do Aprendiz tem, além dos testes comuns
("esta pergunta dá esta resposta"), quatro tipos de teste que procuram erros que ninguém pensou
em escrever. Todos rodam com:

```bash
.venv/bin/python -m pytest                              # ~820 testes, ~15 s
.venv/bin/python -m pytest --loja ../aprendiz-addons    # + homologação com os addons reais (~1 min)
```

Os testes **não rodam quando o app abre**: rodam quando alguém mexe no código, antes de publicar.
O GitHub também os roda a cada envio.

## 1. Testes metamórficos — `tests/test_metamorficos.py`

O problema: para muitas perguntas não dá para escrever "a resposta certa" à mão. A saída: em vez
de conferir a resposta, conferir uma **relação** entre respostas. Se "qual a senha do wifi?" acha
a senha, então estas também precisam achar:

| Transformação | Exemplo |
|---|---|
| maiúsculas | `QUAL A SENHA DO WIFI?` |
| sem acento | `que horas a farmacia abre?` |
| cortesia | `por favor, qual a senha do wifi?` · `… obrigado` |
| pedido | `me explica como deletar um arquivo no linux` |
| letras trocadas | `qual a snhea do wifi` |
| singular/plural | `quais os animal da fazenda` |
| espaços e pontuação | `   qual  a  senha   ?!?!` |

Cada transformação roda nos cinco algoritmos de busca. A segunda parte do arquivo usa uma base
com **armadilhas**: um conhecimento sobre "favor" (para pegar quem confunde "por favor" com o
assunto), "milhas" e "linhas" (uma letra trocada leva à outra), palavras de três letras ("pão",
"gás") e plurais que mudam a terminação ("pães", "países", "homens").

Foi assim que os defeitos da 2.5.1 apareceram: com os addons da loja, 10 de 204 perguntas
mudavam de resposta só por começar com "por favor".

## 2. Fuzz — `tests/test_robustez.py`

Joga no assistente o que ninguém digitaria de propósito: emoji, só pontuação, `'; DROP TABLE`,
HTML, números de 400 dígitos, 5 mil palavras, texto aleatório gerado com semente fixa. Não confere
o conteúdo da resposta, só que ela **sai inteira**: com tipo, texto e confiança entre 0 e 1, em
todas as combinações de busca × resposta, e em menos de 20 s mesmo com texto enorme (o Aprendiz
precisa rodar em máquina fraca).

## 3. Invariantes — `tests/test_invariantes.py`

Coisas que valem sempre, qualquer que seja o algoritmo:

- **Determinismo:** a mesma pergunta dá a mesma resposta (15 combinações de algoritmos).
- **Ordem não importa:** a mesma base ensinada na ordem inversa responde igual.
- **Memória viva:** ensinou, a busca acha na hora; esqueceu, some na hora (o cache do índice
  precisa ser invalidado).
- **Addons limpos:** instalar e remover um addon deixa as respostas exatamente como antes;
  desativar equivale a não ter; reinstalar não duplica.
- **Exportação fiel:** exportar e importar em outro Aprendiz dá as mesmas respostas.
- **Concorrência:** seis threads perguntando ao mesmo tempo não cruzam respostas (o servidor
  atende o navegador em threads).

## 4. Propriedades dos modelos — `tests/test_modelos.py`

Testes da matemática, sem depender de pergunta nenhuma, com dados gerados por semente:

| Modelo | O que tem de valer |
|---|---|
| Naive Bayes (intenções) | probabilidades somam 1 e vêm em ordem; a ordem das palavras não muda nada; 5 mil palavras não dão *underflow* (a conta é em log) |
| Calibrado (regressão logística) | a sigmoide é estável em ±1000, monótona e simétrica; aumentar um sinal move a chance no sentido do peso dele; viés + contribuições = logito (o que o Monitor mostra fecha a conta) |
| TF-IDF | vetor normalizado tem norma 1; o cosseno fica entre 0 e 1; vetor vazio não divide por zero |
| RRF (Híbrido) | `1/(60 + posição)`: consenso entre algoritmos vence um 1º lugar isolado |
| TextRank (Extrativa) | notas entre 0 e 1 com máximo 1; a frase central ganha; a ordem das frases não muda as notas |

## 5. Regressão — `tests/test_correcoes_251.py`

Cada defeito corrigido vira um teste, com a entrada que falhava. Se o teste quebrar, o defeito
voltou. Inclui uma tabela de 32 pares singular/plural e uma lista de **limitações conhecidas**
marcadas como `xfail` ("fácil"/"fáceis", "herói"/"heróis"): sem o acento, que o normalizador
remove, não dá para saber se "faceis" vem de "fácil" ou de "fiel". Quem melhorar o stemmer vê
esses testes passarem.

## 6. Homologação com a loja — `tests/test_loja_homologacao.py`

Opcional (`--loja` ou a variável `APRENDIZ_LOJA`). Instala os addons publicados e faz as 249
perguntas de [`ferramentas/homologar.py`](../../ferramentas/homologar.py). Cada busca tem um
**piso** de acertos; cair abaixo dele é regressão:

| Busca | Piso (2.7) |
|---|---|
| Híbrido | 231 |
| BM25 | 227 |
| Calibrado | 236 |
| TF-IDF | 211 |
| Fuzzy | 162 |

### Base pessoal — `homologar.py --pessoal` (2.7)

As 249 perguntas acima medem o conteúdo dos addons. O uso principal do Aprendiz é outro:
responder sobre o que o **dono** ensinou. Com `--pessoal`, a homologação ensina os 16 fatos
inventados de [`ferramentas/dados/base_pessoal.json`](../../ferramentas/dados/base_pessoal.json)
(senha do wifi, aniversários, carro, contas…) por cima dos mesmos addons e faz 44 perguntas,
escritas como gente escreve:

| Grupo | O que mede |
|---|---|
| direto, variação, escrita, pedido | achar o fato com outras palavras, abreviação, erro e pedido |
| sem resposta | perguntas parecidas com o que foi ensinado, mas sobre outra coisa ("senha do **banco**", "telefone do **eletricista**"): o certo é dizer que não sabe |

No fim, além do total, sai a linha `sem resposta: recusou X/12, inventou Y`. É a medida de
quanto o Aprendiz inventa quando não sabe.

```bash
python ferramentas/homologar.py ../aprendiz-addons --pessoal --busca calibrado
```


O mesmo arquivo repete os testes metamórficos sobre as 204 perguntas que o Híbrido acerta, com
pisos por transformação (100% para maiúsculas, cortesia e pontuação; 97% para letras trocadas).

## Para estudar

- **Por que semente fixa?** Teste aleatório que falha "às vezes" não ajuda ninguém. Com
  `random.Random(42)` o "aleatório" é o mesmo em toda máquina, e uma falha se reproduz.
- **Por que piso e não valor exato?** Uma melhoria não pode quebrar o teste. Se o número subir,
  atualize o piso: ele só anda para cima.
- **Exercício:** escreva uma transformação nova em `TRANSFORMACOES` (por exemplo, trocar "você"
  por "vc") e veja quais algoritmos aguentam.
