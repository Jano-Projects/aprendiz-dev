# Como contribuir

Obrigado pelo interesse! O Aprendiz é, antes de tudo, um **projeto de estudo**. Contribuições
que deixam o código mais claro valem tanto quanto funcionalidades novas.

## Preparar o ambiente

```bash
git clone https://github.com/SEU-USUARIO/aprendiz.git
cd aprendiz
bash instalar.sh --dev                  # Windows: instalar.bat --dev
.venv/bin/python -m pytest              # todos os testes devem passar
.venv/bin/python -m aprendiz --modo servidor   # http://127.0.0.1:8765
```

## Padrões do código

- **Português** em nomes, comentários e mensagens. O público principal fala português.
- **Todo arquivo começa explicando o que faz.** Em Python, isso é o docstring do módulo; a
  primeira linha dele vai para o `docs/estrutura.md`.
- **Comente o porquê**, não o óbvio. Se um trecho implementa uma fórmula, escreva a fórmula.
- **Sem dependências novas** no núcleo sem conversar antes numa issue. Leveza é um requisito:
  o app precisa rodar em máquinas modestas.
- **Nada carregado da internet** pela interface (nem fontes, nem ícones, nem bibliotecas).
- Python 3.10+, 4 espaços de indentação, linhas até ~100 caracteres (veja `.editorconfig`).

## Antes de abrir um pull request

```bash
.venv/bin/python -m pytest                          # testes
.venv/bin/python benchmarks/comparar.py             # se mexeu em busca ou linguagem
.venv/bin/python ferramentas/gerar_estrutura.py     # se criou, moveu ou apagou arquivos
```

- Mudou um algoritmo? Inclua no PR o resultado do benchmark antes e depois.
- Adicionou um algoritmo? Preencha o campo `explicacao`: ele aparece no app.
- Atualize o `CHANGELOG.md`, na seção **[Não lançado]** no topo (crie-a se não existir).

## Mensagens de commit

Usamos o padrão [Conventional Commits](https://www.conventionalcommits.org/pt-br/), em português:

```
feat(busca): adiciona algoritmo Jaccard
fix(linguagem): corrige radical de palavras terminadas em "ões"
docs(algoritmos): explica a saturação do BM25
test(addons): cobre addon com linguagem vazia
```

Tipos: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`, `ci`.

## Versões e tags

As versões seguem o [Versionamento Semântico](https://semver.org/lang/pt-BR/) (`MAIOR.MENOR.CORREÇÃO`)
e cada uma recebe uma **tag anotada** no Git:

```bash
git tag -a v0.4.0 -m "Aprendiz v0.4.0" -m "Resumo das mudanças (copie do CHANGELOG)"
git push origin v0.4.0
```

Ao enviar uma tag `v*`, o GitHub Actions gera os executáveis de Windows e Linux.

## Ideias de primeiras contribuições

- Um novo algoritmo de busca (Jaccard, BM25 ponderado por IDF): veja `docs/criar-algoritmo.md`.
- Mais frases de exemplo para as intenções (`aprendiz/memoria/sementes.py`).
- Um addon útil: veja `docs/addons.md`.
- Melhorias de acessibilidade na interface.
