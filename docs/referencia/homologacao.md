# Homologação por plataforma

O Aprendiz é homologado em **Debian**, **Fedora**, **Ubuntu** e **Windows** de dois jeitos que se
completam: o automático confere os números a cada envio, e o manual confere o que só uma pessoa
vê (a instalação pedindo permissão, a janela abrindo, os botões funcionando).

## Automática (GitHub Actions)

A cada envio para a `main` e em cada pull request, o workflow
[Homologação](../../.github/workflows/homologacao.yml) roda em cada plataforma, partindo de um
sistema **sem Python**:

1. instala o Aprendiz com o próprio `instalar.sh` ou `instalar.bat`;
2. baixa os addons da [loja oficial](https://github.com/Jano-Projects/aprendiz-addons);
3. roda [`tests/test_loja_homologacao.py`](../../tests/test_loja_homologacao.py): as 249 perguntas
   dos addons em cada busca e a [base pessoal](../estudo/testes.md#base-pessoal--homologarpy---pessoal-27),
   cada uma com o seu piso.

| Plataforma | Imagem |
|---|---|
| Debian (estável) | `debian:stable` |
| Fedora (mais recente) | `fedora:latest` |
| Ubuntu (LTS) | `ubuntu:latest` |
| Ubuntu (mais recente) | `ubuntu:rolling` |
| Windows | `windows-latest` |

O resumo de cada execução, na aba **Actions** do GitHub, traz uma linha por plataforma com a
versão, o sistema, o Python e os acertos.

## Manual: roteiro

Para cada versão publicada, em cada sistema disponível (máquina real ou virtual). Marque cada
item que funcionou e anote o que não funcionou.

| # | O que fazer | O que deve acontecer |
|---|---|---|
| 1 | Instalar com `bash instalar.sh` (Linux) ou dois cliques em `instalar.bat` (Windows) | Avisa antes de pedir permissão de administrador; termina sem erro |
| 2 | Rodar `ferramentas/verificar.py` | Tudo "OK", inclusive o chat de ponta a ponta |
| 3 | Abrir com `executar` | A janela (ou o navegador) abre no chat |
| 4 | Ensinar `pergunta: horário da farmácia resposta: 8h às 20h` e perguntar `que horas a farmácia abre?` | Responde 8h às 20h |
| 5 | Ensinar `a partir de agora o horário da farmácia é 9h às 21h` e perguntar de novo | "Atualizei!"; depois responde 9h às 21h |
| 6 | Perguntar `qual a senha do banco?` | "Não tenho nada sobre **banco**", sem inventar |
| 7 | Dar 👍 ou 👎 em 5 respostas e abrir **Configurações → Ajuste pessoal da busca** | Mostra as avaliações e o ajuste "em uso" |
| 8 | **Addons → Abrir loja oficial**, baixar um addon e importar | Pede confirmação e instala; ativar e desativar funciona |
| 9 | **Exportar** o que foi ensinado e importar o arquivo numa instalação limpa | Os conhecimentos voltam |
| 10 | Abrir o **Monitor** e fazer uma pergunta | As etapas aparecem ao vivo |
| 11 | **Resetar memória** | Pede confirmação e cria a cópia de segurança em `backups/` |
| 12 | Rodar as homologações com `--registro` (abaixo) | Os números batem com os pisos |

## Manual: registro

As linhas saem prontas da própria ferramenta, com a data, a versão, o sistema e o Python:

```bash
.venv/bin/python ferramentas/homologar.py ../aprendiz-addons --busca calibrado --registro | tail -1
.venv/bin/python ferramentas/homologar.py ../aprendiz-addons --busca calibrado --pessoal --registro | tail -1
```

No Windows, troque `.venv/bin/python` por `.venv\Scripts\python`. Cole as linhas na tabela e
escreva na última coluna os itens do roteiro que falharam ("roteiro ok" se nenhum).

| Data | Versão | Sistema | Python | Busca · conjunto | Resultado | Roteiro |
|---|---|---|---|---|---|---|
