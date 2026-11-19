# Segurança

## Modelo de segurança do Aprendiz

- **Só escuta em `127.0.0.1`**: nenhum outro computador da rede acessa o app.
- **Nada sai para a internet** durante o uso. O botão **Loja oficial** só abre no navegador do
  sistema o endereço fixo da loja (`aprendiz/aplicativo/config.py`), e só quando você clica. A internet só é usada pelos instaladores, para
  baixar o Python e as dependências, e pela **atualização sob pedido** (2.2): só quando você
  pede ("verifique e atualize" no chat, ou o botão na janela de addons), o app lê o catálogo da
  loja oficial e a última release do GitHub, baixa os addons com versão nova e confere cada um
  pelo SHA-256 do catálogo antes de instalar. Nenhum endereço vem de fora do código, e nada é
  enviado: só se baixa.
- **Os dados ficam num arquivo SQLite** na pasta do usuário (veja o README). Proteja essa
  pasta como você protegeria qualquer documento pessoal.
- **Addons são tratados como dados não confiáveis**: são só dados (JSON, listas de palavras e
  um binário de vetores com tamanho conferido byte a byte), nada é executado nem extraído para
  o disco, há limites de tamanho e cada campo é validado. Addons de compreensão não trazem
  expressões regulares, e as respostas que o app calcula vêm de uma lista fechada
  (veja `docs/guias/addons.md` e `docs/estudo/compreensao.md`). Addons de norma também não: as regras de
  gramática usam só tipos, classes e transformações de listas fechadas do app
  (veja `docs/estudo/revisao.md`).
- **Recomendação de addon** não baixa nada: o botão só abre a loja oficial (endereço fixo)
  filtrada pelo id do addon, que precisa ter só letras minúsculas, números e hífen.
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
