# Segurança

## Modelo de segurança do Aprendiz

- **Só escuta em `127.0.0.1`**: nenhum outro computador da rede acessa o app.
- **Nada sai para a internet** durante o uso. A internet só é usada pelos instaladores, para
  baixar o Python e as dependências.
- **Os dados ficam num arquivo SQLite** na pasta do usuário (veja o README). Proteja essa
  pasta como você protegeria qualquer documento pessoal.
- **Addons são tratados como dados não confiáveis**: são só JSON, nada é executado nem
  extraído para o disco, há limites de tamanho e cada campo é validado
  (veja `docs/addons.md`).
- **A interface escapa todo texto** antes de exibir (proteção contra XSS).

## Versões com suporte

Só a versão mais recente recebe correções de segurança.

## Como reportar uma falha

**Não abra uma issue pública** para falhas de segurança. Use o recurso
**"Report a vulnerability"** na aba *Security* do repositório no GitHub (relato privado).

Inclua, se puder:
- a versão do Aprendiz e o sistema operacional;
- os passos para reproduzir;
- o impacto que você imagina.

Você receberá uma resposta assim que possível, e o crédito pela descoberta, se quiser.
