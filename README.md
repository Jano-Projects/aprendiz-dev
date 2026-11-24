<div align="center">

<img src="aprendiz/web/icone.svg" alt="" width="72">

# Aprendiz

**Um laboratório aberto para estudar Inteligência Artificial por dentro, em português.**
Um assistente local e offline, que só sabe o que você ensina e mostra, **ao vivo**, cada
etapa do que pensa: da tokenização à regressão logística.

[![Testes](https://github.com/Jano-Projects/aprendiz-dev/actions/workflows/testes.yml/badge.svg)](https://github.com/Jano-Projects/aprendiz-dev/actions/workflows/testes.yml)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab)
[![Homologação](https://github.com/Jano-Projects/aprendiz-dev/actions/workflows/homologacao.yml/badge.svg)](https://github.com/Jano-Projects/aprendiz-dev/actions/workflows/homologacao.yml)
![Plataformas](https://img.shields.io/badge/plataformas-Debian%20%7C%20Fedora%20%7C%20Ubuntu%20%7C%20Windows-6b7280)
![Offline](https://img.shields.io/badge/funciona-100%25%20offline-16a34a)
[![Licença MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-4f46e5)](LICENSE)

<img src="docs/imagens/tela-principal.png" alt="Tela do Aprendiz 2.4: conversa respondida pela busca Calibrada e, à direita, o Monitor mostrando a conta da regressão logística sinal por sinal" width="820">

</div>

> 🧑‍💻 **Este repositório é para desenvolvedores e estudantes de IA**, do primeiro contato ao
> nível avançado: o código-fonte para estudar, medir, modificar e contribuir.

---

## O que é

O Aprendiz é um chat que roda no seu computador, **sem internet e sem nuvem**. Você ensina
informações do dia a dia (a senha do wi-fi, o horário da farmácia, quando trocar o óleo do
carro) e depois pergunta do jeito que quiser. Ele entende abreviações, sinônimos e erros de
digitação, aprende com as suas avaliações e, quando não sabe, diz que não sabe.

Não há nenhum modelo de IA gigante aqui. A "inteligência" vem de técnicas clássicas de
**PLN**, **recuperação de informação** e **aprendizado de máquina** (BM25, TF-IDF, Naive Bayes,
Levenshtein, TextRank, vetores de palavras, busca em grafo e uma **regressão logística
treinada**), implementadas de forma legível e comentada em português, pequenas o bastante para
rodar em máquinas bem modestas. O **Monitor**, ao lado do chat, mostra cada etapa ao vivo, com
tempo, dados, fórmulas e parâmetros.

Tudo o que ele faz: [Recursos](docs/guias/recursos.md).

## Para quem é

| Você é… | Comece por | Depois |
|---|---|---|
| **Iniciante em IA** | Use o app com o Monitor no nível **Iniciante**: cada etapa explicada em palavras simples, e um glossário com os termos | [docs/estudo/algoritmos.md](docs/estudo/algoritmos.md), seções 1 a 4, com as contas feitas à mão |
| **Dev que quer entender PLN e busca** | A [trilha do código](docs/README.md#trilha-do-código): normalizador, stemmer, Naive Bayes, BM25, TF-IDF | Crie o seu algoritmo de busca ([docs/guias/criar-algoritmo.md](docs/guias/criar-algoritmo.md)) e compare no benchmark |
| **Estudante de aprendizado de máquina** | A busca **Calibrada**: sinais, padronização, regressão logística em duas etapas, limiar tirado do custo ([docs](docs/estudo/algoritmos.md#5-calibrado-buscacalibradopy-pesos-aprendidos-24)) | Treine de novo com `ferramentas/treinar_calibrado.py`, mude os sinais e meça no conjunto de teste e na homologação |
| **Avançado** | O Monitor no nível **Avançado**: nomes técnicos, fórmulas, contribuição de cada peso e o JSON bruto de cada etapa | A API ao vivo (`/api/chat/fluxo`, NDJSON) e a ficha de parâmetros (`/api/modelo`) para os seus próprios experimentos ([docs/estudo/monitor.md](docs/estudo/monitor.md)) |

## Plataformas homologadas

| Sistema | Instalação e testes | Homologação | Manual |
|---|---|---|---|
| **Debian** (estável) | a cada envio | a cada envio | [registro](docs/referencia/homologacao.md#manual-registro) |
| **Fedora** (mais recente) | a cada envio | a cada envio | [registro](docs/referencia/homologacao.md#manual-registro) |
| **Ubuntu** (LTS e mais recente) | a cada envio | a cada envio | [registro](docs/referencia/homologacao.md#manual-registro) |
| **Windows** (com e sem Python) | a cada envio | a cada envio | [registro](docs/referencia/homologacao.md#manual-registro) |

- **Instalação e testes:** o GitHub instala o Aprendiz com os próprios scripts, partindo de um
  sistema **sem Python**, e roda a suíte inteira ([testes.yml](.github/workflows/testes.yml)).
- **Homologação:** com os addons da loja oficial, confere os pisos de acerto das 249 perguntas
  de gente de verdade e da base pessoal de exemplo ([homologacao.yml](.github/workflows/homologacao.yml)).
- **Manual:** um [roteiro de 12 itens](docs/referencia/homologacao.md#manual-roteiro) para
  conferir o que só uma pessoa vê, com o registro de cada versão por sistema.

## Instalar e rodar

**Não é preciso instalar nada antes.** O instalador confere o Python e, se faltar, instala
sozinho, avisando antes que vai precisar de permissão de administrador. A internet é usada só
durante a instalação e quando você pede para atualizar ("verifique e atualize", no chat): aí o
Aprendiz baixa as versões novas dos addons da loja oficial e, se foi instalado pelo código,
atualiza a si mesmo.

| Sistema | Instalar | Abrir |
|---|---|---|
| **Linux** (Ubuntu, Debian, Fedora, openSUSE, Arch…) | `bash instalar.sh` | `bash executar.sh` |
| **Windows** | dois cliques em `instalar.bat` | dois cliques em `executar.bat` |

- **Linux:** se o seu usuário for administrador, o instalador pede a **sua** senha (sudo). Se
  não for, pede a do **root**. Não rode o instalador com `sudo`.
- **Windows:** o Python oficial é baixado do python.org e o Windows pede confirmação (UAC). Se
  você recusar, ele instala só para o seu usuário.
- Na primeira vez, o `executar` também instala tudo, se você pular o `instalar`.

Para conferir a instalação (Python, SQLite, dependências e um chat de ponta a ponta):

```bash
.venv/bin/python ferramentas/verificar.py          # Linux
.venv\Scripts\python ferramentas\verificar.py      # Windows
```

Detalhes, executável e problemas comuns: [docs/guias/empacotamento.md](docs/guias/empacotamento.md).

## Primeiros passos

1. **Ensine:** `pergunta: horário da farmácia resposta: 8h às 20h`
2. **Pergunte do seu jeito:** `que horas a farmácia abre?`
3. **Veja o raciocínio:** abra o **Monitor** (à direita) e acompanhe cada etapa ao vivo
4. **Diga se ajudou:** 👍 ou 👎 embaixo da resposta; com 5 avaliações, a busca começa a se
   ajustar a você
5. **Compare algoritmos:** troque a busca no topo da tela e pergunte de novo
6. **Instale um addon:** *Addons → Importar addon* →
   `exemplos/addons/conversoes-medidas.aprendiz`, e pergunte `quanto vale 1 pol em cm?`
7. **Conheça a loja oficial:** *Addons → Abrir loja oficial* abre no navegador a
   [loja oficial de addons](https://jano-projects.github.io/aprendiz-addons/) da Jano Projects.

## Documentação

| Para | Leia |
|---|---|
| Começar a estudar o código | [Trilha do código](docs/README.md#trilha-do-código) |
| Entender cada algoritmo, com as contas | [Algoritmos](docs/estudo/algoritmos.md) · [Linguagem](docs/estudo/linguagem.md) · [Compreensão](docs/estudo/compreensao.md) · [Monitor](docs/estudo/monitor.md) |
| Criar addons e algoritmos | [Addons](docs/guias/addons.md) · [Criar um algoritmo](docs/guias/criar-algoritmo.md) |
| Desenvolver, testar e empacotar | [Desenvolvimento](docs/guias/desenvolvimento.md) · [Testes](docs/estudo/testes.md) · [Empacotamento](docs/guias/empacotamento.md) |
| Consultar o mapa | [Arquitetura](docs/referencia/arquitetura.md) · [Estrutura](docs/referencia/estrutura.md) · [Versionamento](docs/referencia/versionamento.md) |
| Todos os documentos | [Índice](docs/README.md) · [CHANGELOG](CHANGELOG.md) |

## Contribuindo

Contribuições são bem-vindas, principalmente as que deixam o código mais fácil de entender.
Leia o [CONTRIBUTING.md](.github/CONTRIBUTING.md) (ambiente, padrões, commits e tags) e o
[Código de conduta](.github/CODE_OF_CONDUCT.md). Falhas de segurança: veja o [SECURITY.md](.github/SECURITY.md).
Mudanças por versão: [CHANGELOG.md](CHANGELOG.md).

## Licença

[MIT](LICENSE): use, estude, modifique e distribua à vontade.
