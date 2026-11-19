# Como criar um algoritmo

O seletor é montado automaticamente a partir dos algoritmos registrados. Para adicionar
o seu, são quatro passos.

## Exemplo: busca por Jaccard

A similaridade de Jaccard é o tamanho da interseção dividido pelo tamanho da união de dois
conjuntos de termos.

**1. Crie** `aprendiz/algoritmos/busca/jaccard.py`:

```python
"""Busca por similaridade de Jaccard: |A ∩ B| / |A ∪ B|."""

from aprendiz.algoritmos.base import AlgoritmoBusca, Candidato, ContextoBusca, registrar
from aprendiz.linguagem import TextoProcessado


@registrar                                   # 3. registra no seletor
class BuscaJaccard(AlgoritmoBusca):          # 2. herda o contrato
    nome = "jaccard"                         # id usado pela API
    titulo = "Jaccard"                       # nome na interface
    descricao = "Termos em comum ÷ termos no total."
    explicacao = """
**Ideia:** dividir o número de termos em comum pelo total de termos diferentes.
Aparece no botão "Como funciona?" do app.
"""
    limiar = 0.3

    def buscar(self, consulta: TextoProcessado, ctx: ContextoBusca, limite: int = 5):
        q = set(consulta.radicais)
        if not q:
            return []
        resultados = []
        for doc in ctx.banco.todos_conhecimentos():
            d = set(doc["texto_busca"].split())
            j = len(q & d) / len(q | d) if d else 0.0
            if j > 0:
                resultados.append(Candidato(doc, pontuacao=j, confianca=j,
                                            detalhes={"jaccard": round(j, 3)}))
        resultados.sort(key=lambda c: c.pontuacao, reverse=True)
        return resultados[:limite]
```

**4. Importe** em `aprendiz/algoritmos/busca/__init__.py`:

```python
from aprendiz.algoritmos.busca import bm25, tfidf, fuzzy, hibrido, jaccard
```

Pronto: reinicie o app e o "Jaccard" aparece no seletor. Rode o benchmark para comparar:

```bash
python benchmarks/comparar.py
```

## O contrato

### Busca

```python
def buscar(self, consulta: TextoProcessado, ctx: ContextoBusca, limite: int) -> list[Candidato]
```

- `consulta.radicais`: termos da pergunta para a busca
- `consulta.conteudo`: palavras sem stopwords, não radicalizadas
- `ctx.banco`: acesso ao SQLite (`todos_conhecimentos()`, `buscar_fts()`…)
- `ctx.cache`: dicionário para guardar índices entre buscas. Compare
  `ctx.banco.versao_conhecimento` para saber quando reconstruir (veja `tfidf.py`).
- Devolva no máximo `limite` candidatos, do melhor para o pior.
- `confianca` deve ir de 0 a 1 e ser comparável com o seu `limiar`.

### Resposta

```python
def responder(self, consulta, candidatos: list[Candidato], ctx) -> RespostaGerada
```

Recebe só os candidatos **aceitos** (acima do limiar), já ordenados. Sempre há pelo menos um.
Devolva o texto, os ids usados (`fontes`) e, se quiser, `detalhes`, que aparecem no painel
de explicação.

### Um exemplo maior: a resposta Trabalhada (2.0)

`algoritmos/resposta/trabalhada.py` mostra um montador que usa mais do que os candidatos:

- `ctx.caminho` traz o caminho de porquês que a teia (`core/teia.py`) montou a partir do melhor
  candidato, ou `None` se ele não tem teia;
- `ctx.expressao` traz as frases dos addons de linguagem (`expressao.dizer("porque", texto)`).

Com isso ela conta o fato e cada porquê seguido dos porquês do fragmento ligado. Sem teia, cai
na resposta Direta: um montador novo deve sempre ter um caminho simples para quando faltar dado.

## Dicas

- O que você colocar em `detalhes` aparece na interface. Use isso para explicar seu algoritmo.
- Escreva um teste em `tests/test_algoritmos.py`: os testes parametrizados já rodam para
  todos os algoritmos registrados.
