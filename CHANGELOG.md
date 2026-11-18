# Histórico de versões

Todas as mudanças relevantes do projeto ficam registradas aqui.
O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/), e as versões
seguem o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

## [0.6.0] - 2026-11-18

### Adicionado
- **Dicionário nos dois sentidos** (`aprendiz/core/dicionario.py`): além de "o que significa
  kota?", o app entende "como se diz dinheiro em Angola?", "como se fala aldeia em kriol",
  "qual a gíria pra dinheiro em Moçambique?", "como os angolanos chamam o dinheiro?", "traduza
  aldeia para kriol", "kota em Angola" e "como se diz kota em português?". Sem região, lista o
  termo de cada dicionário instalado.
- Verbetes com **traduções** (`traducoes`, linha `T:`) e **outras grafias** (linhas `V:` a mais).
- Manifesto com **região** do dicionário (`regiao`: nome, artigo e termos).
- **Variações de pergunta** em qualquer addon (`variacoes`, várias linhas `P:` no mesmo bloco):
  jeitos diferentes de perguntar que levam à mesma resposta, nos quatro algoritmos de busca.
- O teste de recomendação de algoritmos usa as variações.
- Botão **Abrir loja oficial** (em Addons, em Configurações e na confirmação de um addon
  oficial): abre no navegador padrão do sistema o endereço fixo da loja
  (`config.URL_LOJA_OFICIAL`), pela rota `POST /api/loja-oficial`, que não aceita outro
  endereço.

### Mudado
- Banco: `versao_esquema` 6 (colunas `variacoes` e `traducoes` em `conhecimentos`).
- Textos do app e da documentação: addons oficiais são distribuídos só pela loja oficial da
  Jano Projects; addons de terceiros são compartilhados diretamente, como arquivo. A tela de
  instalação de um addon "oficial" lembra de conferir o SHA-256 com o da loja.

## [0.5.0] - 2026-11-17

### Adicionado
- **Algoritmo recomendado** no manifesto dos addons (`recomendado`: busca, resposta e acerto).
  `criar_addon.py` e a exportação calculam a recomendação testando os quatro algoritmos de
  busca com o próprio conteúdo (`aprendiz/core/recomendacao.py`).
- Na instalação: a recomendação aparece na confirmação, com as opções **Usar como padrão** e
  **Ativar também os addons do mesmo grupo**.
- **Grupos de addons** na tela de Addons, pela recomendação: ativar ou desativar o grupo
  inteiro e **Usar este grupo** (ativa, aplica o padrão e oferece desativar os de outros
  padrões).
- Na exportação: resultado do teste, escolha da busca e da resposta recomendadas e o botão
  **Testar de novo**.
- Rotas `GET /api/addons/grupos`, `POST /api/addons/grupo`, `PUT /api/padrao` e
  `POST /api/exportar/recomendar`.

### Mudado
- A etapa de busca do pipeline virou o método `Assistente.buscar()`, reaproveitado pelo teste
  de recomendação.
- README e documentação descrevem só o que o projeto faz hoje (sem roteiro de planos).

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

[Não lançado]: https://github.com/Jano-Projects/aprendiz-dev/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/Jano-Projects/aprendiz-dev/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/Jano-Projects/aprendiz-dev/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/Jano-Projects/aprendiz-dev/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/Jano-Projects/aprendiz-dev/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/Jano-Projects/aprendiz-dev/releases/tag/v0.3.0
