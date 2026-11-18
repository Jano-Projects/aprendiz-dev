# Histórico de versões

Todas as mudanças relevantes do projeto ficam registradas aqui.
O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/), e as versões
seguem o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

## [0.4.1] - 2026-11-17

### Adicionado
- **Verbetes** (tipo de conhecimento para dicionários): respondem só à palavra sozinha ou a
  "o que significa…"; numa frase com outras palavras, são ignorados. Se vários dicionários
  tiverem a mesma palavra, a resposta mostra todos.
- `linguagem.json` dos addons aceita `stopwords` e `intencoes` (frases de treino do
  classificador), válidos só com o addon ativo.
- `criar_addon.py`: blocos `V:` (verbete) e o arquivo `verbetes.txt`.

### Mudado
- Banco: `versao_esquema` 5 (tabelas `conhecimentos` e `addon_linguagem` aceitam os tipos
  novos; bancos antigos são convertidos ao abrir, sem perder dados).

## [0.4.0] - 2026-11-17

### Adicionado
- **Formato de addon 2**: o manifesto registra `origem` (`oficial` da Jano Projects ou
  `terceiros`), `classificacao` (memória, linguagem, parâmetros, personalização; algoritmo e
  aplicação ficam reservados e são recusados), `app` (versão que gerou e versão mínima) e
  `dependencias` (addons que ele complementa). Addons do formato 1 continuam sendo lidos.
- **Exportar meu conhecimento** (Addons): gera um `.aprendiz` com os itens escolhidos.
  Itens com cara de dado pessoal vêm desmarcados; addons instalados entram só como
  dependências (id, versão e nome), sem copiar o conteúdo.
- **Confirmação antes de instalar**: origem, classificação, totais, versão do app,
  dependências (instalada, desativada, desatualizada ou ausente), parâmetros e amostra.
- **Configurações de parâmetros e personalização**: algoritmos padrão, limiares de cada
  busca, margem de prioridade do dono, nome, cor e mensagem de boas-vindas. Valem na ordem
  dono > addon ativo > padrão, e a interface mostra de onde vem cada valor.
- Addons podem trazer `parametros.json` e `personalizacao.json` (lista fechada de chaves).
- Rotas `POST /api/addons/inspecionar`, `GET/POST /api/exportar` e `/api/configuracoes`.
- Opção "Configurações" no reset da memória.
- Addon de exemplo `modo-exigente` (só parâmetros).

### Mudado
- A escolha de algoritmo nos seletores agora fica no servidor (Configurações), e não mais no
  navegador.
- `/api/algoritmos` mostra o limiar em vigor (e o padrão em `limiar_padrao`).
- O addon de exemplo `conversoes-medidas` passou para a versão 1.1.0, marcado como oficial.
- Banco: `versao_esquema` 4 (coluna `addons.manifesto` e tabela `configuracoes`).

### Corrigido
- Instalador do Windows: depois de instalar o Python, localiza o `python.exe` pelo Registro
  do Windows (PEP 514) e pelo lançador `py`, em vez de supor a pasta. Antes, falhava quando
  já havia outro Python da mesma série instalado em outra pasta. Em caso de erro, mostra o
  final do log do instalador oficial.
- Links do README, CONTRIBUTING e CHANGELOG apontando para `Jano-Projects/aprendiz-dev`, e
  `git clone` do CONTRIBUTING criando a pasta `aprendiz`.
- Nome do job de executáveis no GitHub Actions quando ele é pulado.

## [0.3.0] - 2026-11-17

Primeira versão pública.

### Adicionado
- Explicação de cada algoritmo dentro do app (botão **?** ao lado dos seletores).
- `docs/algoritmos.md` reescrito com um exemplo completo, com números calculados pelo código.
- `docs/estrutura.md`: mapa indentado de pastas e arquivos, gerado a partir dos docstrings
  (`ferramentas/gerar_estrutura.py`). Um teste garante que nenhum arquivo fique sem descrição.
- Sublistas no renderizador de Markdown da interface.
- Arquivos de comunidade: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, modelos
  de issue e de pull request, `.editorconfig`.

### Melhorado
- Sinônimo padrão "hora/horas → horário": "que horas abre?" agora encontra "horário de…".
  O BM25 passou de 89% para 100% de acerto no benchmark, e o Fuzzy de 72% para 83%.
- "wi-fi" e "e-mail" viram "wifi" e "email" na normalização (prefixos de até 2 letras).
- Bancos de versões anteriores recebem os sinônimos novos e são reindexados ao abrir.

## 0.2.0 - 2026-11-17 (desenvolvimento, sem tag)

### Adicionado
- **Addons**: pacotes de conhecimento `.aprendiz` com importação, ativar/desativar,
  atualização por versão, remoção e indicação da origem em cada resposta.
- Prioridade do dono: o que ele ensina vence o conteúdo de addons.
- `ferramentas/criar_addon.py` para criar e conferir addons, e um addon de exemplo
  ("Conversões de medidas").
- Migração automática de bancos da versão 0.1.

## 0.1.0 - 2026-11-17 (desenvolvimento, sem tag)

### Adicionado
- Assistente local e offline: normalização, radicais (RSLP simplificado), intenções
  (Naive Bayes), entidades (regex).
- Seletor de algoritmos: BM25, TF-IDF, Fuzzy e Híbrido (RRF); respostas Direta e Extrativa
  (TextRank).
- Interface de chat com painel "Por que respondi isso?", temas claro e escuro, ícones,
  configurações e reset da memória com cópia de segurança.
- Instaladores para Linux e Windows que instalam o Python se faltar, verificador de
  instalação, executável via PyInstaller e CI em Windows, Ubuntu, Fedora e Debian.

[Não lançado]: https://github.com/Jano-Projects/aprendiz-dev/compare/v0.4.1...HEAD
[0.4.1]: https://github.com/Jano-Projects/aprendiz-dev/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/Jano-Projects/aprendiz-dev/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/Jano-Projects/aprendiz-dev/releases/tag/v0.3.0
