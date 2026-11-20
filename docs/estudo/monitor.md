# Monitor

O Monitor é o painel à direita do chat. Ele mostra o que acontece por dentro de cada resposta,
**enquanto** o Aprendiz pensa: as etapas do pipeline, a conta da busca, os parâmetros do modelo e
os tempos. Abre e fecha pelo botão de tela no topo; em telas estreitas, vira uma gaveta.

## Dois níveis de leitura

| Nível | Para quem | O que muda |
|---|---|---|
| **Iniciante** | Quem está começando em IA | Cada etapa diz o que faz em palavras simples; a aba Busca explica a nota de cada candidato em frases; o glossário traz só a definição simples |
| **Avançado** | Quem já programa e quer o detalhe | O nome técnico de cada etapa (com links para o glossário), as fórmulas com os números da resposta, o valor bruto de cada sinal e um bloco **Dados brutos (JSON)** em cada etapa |

A escolha fica guardada no navegador.

## As abas

**Pipeline.** Uma linha por etapa, na ordem em que aconteceram, com o tempo de cada uma. A barra
fina embaixo do nome é um **gráfico de Gantt**: começa onde a etapa começou e tem a largura do
tempo que ela levou, em relação ao total. Clicar abre os dados da etapa (radicais, intenções,
candidatos, frases…).

As etapas chegam **ao vivo**: cada uma aparece assim que termina no servidor. Como uma resposta
leva cerca de 20 ms, tudo aparece quase de uma vez; a **câmera lenta** espaça as etapas
(450 ms entre elas) e segura a resposta no chat até a última, para dar tempo de acompanhar.

**Busca.** Os candidatos da busca que decidiu a resposta, com a confiança, o limiar (a marca
laranja) e se foram aceitos. "Aceito" quer dizer que passou de verdade: limiar, folgas do
assunto e regra do assunto, e não só "confiança ≥ limiar". Clicar num candidato mostra de onde
veio a nota dele:

- **Calibrado:** a conta inteira da regressão logística. Cada sinal vira uma barra (verde
  empurra para cima, vermelho para baixo), com `z = viés + Σ peso · (x − média) / desvio` e
  `p = σ(z)`. No 1º lugar, também a 2ª etapa: a nota dele, a distância para o 2º e a chance de
  estar certo, comparada com o limiar.
- **Híbrido:** a posição em cada algoritmo, a parcela `1 / (60 + posição)` do RRF e o motivo do
  consenso.
- **BM25, TF-IDF, Fuzzy:** os números que cada um calcula (nota BM25 e cobertura, cosseno,
  WRatio).

**Modelo.** A ficha técnica, lida de `GET /api/modelo` (veja abaixo): o total de parâmetros, a
divisão por tipo, cada componente (clique para ver os detalhes e, na Calibrada, os pesos), o
resultado do treino da Calibrada no conjunto de teste e o ambiente (versões, processadores,
memória).

**Desempenho.** As respostas desta sessão: tempo médio, p90 (a partir de 5 respostas), memória
do processo e o tempo médio de cada etapa, da mais cara para a mais barata. É o lugar para ver
onde vale otimizar.

**Glossário.** De *token* a *validação cruzada*, com a definição simples e, no nível Avançado, a
técnica (fórmulas, complexidade). Os termos que aparecem nas outras abas levam até aqui.

## O que conta como parâmetro

A ficha separa os números em quatro tipos:

| Tipo | O que é | Exemplos no Aprendiz |
|---|---|---|
| **Aprendido** | Ajustado por um treino a partir de exemplos rotulados | Pesos e viés da busca Calibrada (as duas etapas); P(palavra \| intenção) do Naive Bayes |
| **Estatística** | Calculado da base, sem rótulos | IDF de cada termo e pesos TF-IDF; média e desvio de cada sinal da Calibrada |
| **Pré-treinado** | Veio pronto num addon | Vetores de palavras (100 dimensões, 1 byte cada); tabela de lemas |
| **Hiperparâmetro** | Escolhido por uma pessoa | k1 e b do BM25, k do RRF, limiares, profundidade da teia, pesos da Extrativa |

Com os 34 addons da homologação, a conta fica assim:

| Componente | Tipo | Parâmetros |
|---|---|---|
| Busca Calibrada · 1ª etapa | aprendido | 18 (17 sinais + viés) |
| Busca Calibrada · 2ª etapa | aprendido | 3 |
| Busca Calibrada · padronização | estatística | 34 |
| Intenções (Naive Bayes) | aprendido | 858 (6 classes × 143) |
| TF-IDF | estatística | 42.983 (4.829 IDF + 38.154 pesos não nulos) |
| BM25 · Fuzzy · teia · limiares · Extrativa | hiperparâmetro | 14 |
| Vetores de palavras | pré-treinado | 1.409.800 (14.098 palavras × 100) |
| Lemas | pré-treinado | 317.331 |
| **Total** | | **1.771.041** |

Um modelo de linguagem pequeno tem centenas de milhões de parâmetros, todos aprendidos. Aqui,
quase tudo é pré-treinado, e a parte que aprende com rótulos tem menos de mil números. É por isso
que o Aprendiz roda em qualquer máquina.

## Para usar fora da interface

### `POST /api/chat/fluxo`: o pipeline ao vivo

Recebe o mesmo corpo de `/api/chat` e responde em **NDJSON** (`application/x-ndjson`): um
objeto JSON por linha, enviado assim que fica pronto.

```bash
curl -N -X POST http://127.0.0.1:8765/api/chat/fluxo \
     -H "Content-Type: application/json" \
     -d '{"mensagem": "como juntar duas tabelas em sql?", "busca": "calibrado"}'
```

```
{"evento": "etapa", "indice": 0, "nome": "Normalização", "ms": 0.72, "inicio_ms": 0.0, "dados": {...}}
{"evento": "etapa", "indice": 1, "nome": "Diálogo", "ms": 4.34, "inicio_ms": 0.72, "dados": {...}}
...
{"evento": "fim", "resposta": {"conversa_id": "...", "mensagem_usuario": {...}, "mensagem": {...}}}
```

Se algo falhar, a última linha é `{"evento": "erro", "mensagem": "..."}`.

Por dentro, é o padrão **produtor-consumidor**: o `Assistente` roda numa thread e avisa cada
etapa por um *ouvinte* (`Etapas.ouvinte`, em `core/assistente.py`), que coloca o evento numa
`queue.Queue`; o gerador da rota lê a fila e envia cada linha. Na interface, `app.js` lê o
corpo com `ReadableStream` e entrega cada etapa ao `monitor.js`. Se o navegador não ler fluxos,
cai na rota comum `/api/chat`.

Em Python, sem servidor:

```python
from aprendiz.core import Assistente
from aprendiz.memoria import Banco

assistente = Assistente(Banco("teste.db"))
assistente.responder("qual a senha do wifi?", busca="calibrado",
                     ouvinte=lambda etapa: print(etapa["nome"], etapa["ms"], "ms"))
```

### `GET /api/modelo`: a ficha técnica

```json
{
  "total_parametros": 1771041,
  "por_tipo": {"aprendido": 879, "estatística": 43017, "pré-treinado": 1727131, "hiperparâmetro": 14},
  "componentes": [{"nome": "...", "tipo": "...", "tecnica": "...", "parametros": 18,
                   "descricao": "...", "detalhes": {...}}],
  "treino_calibrado": {"data": "...", "perguntas_treino": 532, "teste": {...}},
  "base": {...},
  "ambiente": {"aprendiz": "2.4.0", "python": "...", "sqlite": "...", "memoria_mb": 128.6}
}
```

Quem calcula é `aprendiz/core/monitor.py` (`ficha_do_modelo`). A memória vem de `/proc` no
Linux e da API do Windows; em outros sistemas, fica `null`.

## Para quem cria algoritmos

- O que o seu algoritmo puser em `Candidato.detalhes` aparece na aba Busca (e no JSON bruto).
  A Calibrada é o exemplo completo: `sinais`, `contribuicoes`, `vies`, `z`, `chance` e, no 1º
  lugar, `decisao` e `chance_de_estar_certo`.
- Uma etapa nova do pipeline (`etapas.marcar("Nome", dados)`) aparece sozinha no Pipeline. Para
  ela ter a explicação nos dois níveis, acrescente uma linha na lista `ETAPAS` de
  `web/monitor.js`; termos novos vão na lista `GLOSSARIO`.

## Exercícios

1. Ligue a câmera lenta e pergunte algo com erro de digitação ("oq é nul"). Em qual etapa a
   palavra é corrigida? Quanto tempo ela leva?
2. Faça a mesma pergunta com BM25 e com Calibrado e compare, na aba Desempenho, o tempo da
   etapa Busca. Por que a Calibrada custa mais?
3. Na aba Busca, com a Calibrada, ache uma pergunta em que o 1º lugar tem chance média
   (0,3 a 0,6) na 1ª etapa, mas passa no limiar por estar longe do 2º. Por que a 2ª etapa existe?
4. Desative o addon de vetores e veja a aba Modelo: quantos parâmetros sobram? O que muda nas
   respostas com "automóvel" quando a base fala de "carro"?
5. Consuma o `/api/chat/fluxo` num script seu e grave o tempo de cada etapa de 50 perguntas.
   Qual etapa tem a maior variação?
