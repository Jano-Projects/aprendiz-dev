# Versionamento

O Aprendiz e os addons da loja seguem o [Versionamento Semântico](https://semver.org/lang/pt-BR/):
**MAIOR.MENOR.CORREÇÃO**. Cada número só sobe por um motivo, e uma etapa de trabalho, sozinha,
não muda número nenhum.

## O que faz cada número subir

| Número | Sobe quando… | Exemplo |
|---|---|---|
| **MAIOR** (`3.0.0`) | algo **deixa de ser compatível**: um addon publicado para de funcionar, o formato `.aprendiz` muda de um jeito que versões anteriores não leem, ou o banco do usuário precisa de uma migração sem volta | trocar a estrutura do `manifesto.json` |
| **MENOR** (`2.6.0`) | um **pacote de melhorias** fica pronto e é publicado | busca nova, tipo de pergunta novo, seção nova no `compreensao.json` |
| **CORREÇÃO** (`2.6.1`) | só **conserto** do que já foi publicado, sem recurso novo | uma resposta errada, um erro no instalador |

O MENOR não "vira" MAIOR ao passar de 9: `2.10`, `2.15` e `2.30` são versões normais. O MAIOR
diz se algo quebrou, não o tamanho do projeto.

## Compatibilidade sem subir o MAIOR

Recurso novo que as versões anteriores **recusam com aviso** continua sendo MENOR. Um addon que
usa uma seção nova declara `"app": {"versao_minima": "2.6.0"}` no manifesto, e o Aprendiz 2.5
diz "este addon precisa do Aprendiz 2.6.0 ou mais novo" em vez de quebrar. Nada do que já
estava instalado deixa de funcionar.

## Como uma versão nasce

1. O trabalho acontece num branch com o nome da versão (`aprendiz-2.6` no app, `addons-2.6`
   na loja), em etapas. Cada etapa vira um ou mais commits, **sem tag**.
2. Os números em `pyproject.toml` e `aprendiz/__init__.py` já mostram a versão em preparação,
   e o [CHANGELOG](../../CHANGELOG.md) junta as mudanças em **[Não lançado]**.
3. Para alguém testar antes, publica-se uma pré-versão: tag `v2.6.0-beta.1`, `beta.2`…,
   marcada como *pre-release* no GitHub. Pré-versões não gastam número.
4. Com tudo testado (suíte, homologação com a loja), o branch entra na `main`, o CHANGELOG
   ganha a data e sai a tag `v2.6.0`, com a release.
5. Depois disso, só correções: `2.6.1`, `2.6.2`…

## Addons

A mesma regra vale para cada addon, contada separadamente da versão do app:

| Mudança no addon | Versão |
|---|---|
| Usa algo novo do app, ou muda o formato dos dados | MENOR, e `versao_minima` do app sobe junto |
| Conteúdo novo (frases, verbetes, porquês) | MENOR |
| Erro de digitação, resposta errada, gatilho que atrapalhava | CORREÇÃO |
| Precisa de um app novo **e** deixa de servir às versões anteriores dele de um jeito que o aviso não cobre | MAIOR |

O addon sobe de versão uma vez por publicação, por mais ajustes que tenha recebido no branch.
