# Addons

Addons são **pacotes de conhecimento prontos**. Alguém prepara um assunto (conversões de
medidas, atalhos do Linux, regras de um jogo…), gera um arquivo `.aprendiz` e publica. Quem
baixa importa pelo app, em **Addons → Importar addon**.

- Cada addon pode ser **ativado ou desativado** a qualquer momento. Desativar só esconde o
  addon das respostas; nada é apagado.
- **O que o dono ensina tem prioridade.** Se você e um addon souberem a mesma coisa, vale a
  sua resposta. O mesmo vale para sinônimos e abreviações.
- Importar de novo um addon com o mesmo `id` **atualiza** o addon: o conteúdo é substituído e a
  escolha de ativo/desativado é mantida.
- Cada resposta mostra de qual addon veio a informação.
- O reset da memória tem uma opção separada para os addons.

## Criar um addon

Crie uma pasta com os arquivos abaixo. Veja o exemplo completo em
`exemplos/addons/conversoes-medidas/`.

```
meu-addon/
├── manifesto.json     (obrigatório)
├── perguntas.txt      pares de pergunta e resposta: o jeito mais fácil
├── linguagem.json     (opcional) sinônimos e abreviações
└── *.md / *.txt       (opcional) textos livres, divididos em trechos
```

**manifesto.json**

```json
{
  "id": "conversoes-medidas",
  "nome": "Conversões de medidas",
  "versao": "1.0.0",
  "autor": "Seu nome",
  "descricao": "Uma frase sobre o addon.",
  "licenca": "CC0-1.0",
  "site": "https://exemplo.org"
}
```

- `id`: de 2 a 63 caracteres, só letras minúsculas, números e hífen. É o que identifica o addon
  nas atualizações, então **não mude o id entre versões**.
- `nome` e `versao` são obrigatórios. Os outros campos são opcionais.

**perguntas.txt**

```
# Comentários começam com #
P: quantos ml tem uma xícara de chá
R: Uma xícara de chá tem cerca de 240 ml.

P: quanto vale uma polegada
R: 1 polegada = 2,54 cm.
```

**linguagem.json**

```json
{
  "sinonimos":   { "chicara": "xicara" },
  "abreviacoes": { "pol": "polegada", "lb": "libra" }
}
```

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

## O formato `.aprendiz`

É um **ZIP comum** com até três arquivos JSON (UTF-8):

| Arquivo | Obrigatório | Conteúdo |
|---|---|---|
| `manifesto.json` | sim | o objeto acima, mais `"formato": 1` |
| `conhecimentos.json` | sim | lista de `{"pergunta"?, "conteudo", "tipo"?}`; `tipo` é `pergunta`, `nota` ou `trecho` |
| `linguagem.json` | não | `{"sinonimos": {...}, "abreviacoes": {...}}` |

Quem gera addons por programa pode criar o ZIP diretamente ou usar
`aprendiz.addons.criar_pacote()`.

## Segurança

Addons vêm da internet, então o Aprendiz os trata como **dados não confiáveis**
(`aprendiz/addons.py`):

- **Só dados, nunca código.** Não existe forma de um addon executar algo.
- **Nada é extraído para o disco.** Só os três nomes conhecidos são lidos de dentro do ZIP;
  qualquer outro arquivo, inclusive com caminhos como `../../`, é ignorado.
- **Limites:** 50 MB de arquivo, 200 MB descompactados (proteção contra *zip bombs*), 100 mil
  conhecimentos e 20 mil caracteres por conhecimento.
- **Validação de cada campo**, com remoção de caracteres de controle. O `site` precisa começar
  com `https://`.
- **Instalação atômica:** ou o addon entra inteiro, ou nada muda.
- Na interface, todo texto de addon é exibido **escapado**, sem risco de HTML ou script.

O que a validação **não** garante é que o conteúdo esteja **correto**. Instale addons de fontes
em que você confia, e use "Ver conteúdo" para conferir antes de ativar.

## Ideia para a loja de addons

Uma loja simples não precisa de servidor:

1. Um repositório no GitHub com os arquivos `.aprendiz` e um `catalogo.json` listando nome,
   descrição, versão, link de download e o **SHA-256** de cada arquivo.
2. Uma página estática (GitHub Pages) que lê o catálogo e mostra os addons.
3. No futuro, o app pode ler o catálogo e conferir o SHA-256 antes de instalar. O comando
   `criar_addon.py --conferir` já mostra esse hash.
