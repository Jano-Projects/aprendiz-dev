# Histórico de versões

Todas as mudanças relevantes do projeto ficam registradas aqui.
O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/), e as versões
seguem o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

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

[0.3.0]: https://github.com/Jano-Projects/aprendiz-dev/releases/tag/v0.3.0
