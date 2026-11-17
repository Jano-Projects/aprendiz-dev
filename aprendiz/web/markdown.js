/*
 * Mini renderizador de Markdown (sem bibliotecas externas).
 *
 * Suporta o suficiente para um chat:
 *   **negrito**, *itálico*, `código`, blocos ```código```,
 *   listas com "- " ou "1. " (com uma sublista recuada por 2+ espaços),
 *   parágrafos e quebras de linha.
 *
 * SEGURANÇA: todo texto é "escapado" ANTES de virar HTML. Assim, se alguém
 * ensinar "<script>…</script>" ao assistente, isso aparece como texto e
 * nunca é executado (proteção contra XSS).
 */
(function () {
  "use strict";

  function escapar(texto) {
    return texto
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // Formatação dentro de uma linha (o texto já chega escapado).
  function emLinha(texto) {
    return texto
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
  }

  function renderizar(markdown) {
    const partes = String(markdown || "").split(/```/);
    let html = "";

    partes.forEach(function (parte, i) {
      // Partes ímpares estão DENTRO de um bloco de código.
      if (i % 2 === 1) {
        html += "<pre><code>" + escapar(parte.replace(/^\w*\n/, "")) + "</code></pre>";
        return;
      }

      const linhas = escapar(parte).split("\n");
      let lista = null;        // "ul" | "ol" | null — lista principal aberta
      let subLista = false;    // há uma sublista (itens recuados) aberta?
      let itemAberto = false;  // o <li> atual continua aberto para receber sublista
      let paragrafo = [];

      function fecharParagrafo() {
        if (paragrafo.length) {
          html += "<p>" + paragrafo.map(emLinha).join("<br>") + "</p>";
          paragrafo = [];
        }
      }
      function fecharItem() {
        if (subLista) { html += "</ul>"; subLista = false; }
        if (itemAberto) { html += "</li>"; itemAberto = false; }
      }
      function fecharLista() {
        fecharItem();
        if (lista) { html += "</" + lista + ">"; lista = null; }
      }

      linhas.forEach(function (linha) {
        const recuado = linha.match(/^\s{2,}[-*]\s+(.*)$/);
        const item = linha.match(/^[-*]\s+(.*)$/);
        const numerado = linha.match(/^\s*\d+[.)]\s+(.*)$/);

        if (recuado && lista) {
          // Item recuado dentro de uma lista: vira sublista do item atual.
          if (!subLista) { html += "<ul>"; subLista = true; }
          html += "<li>" + emLinha(recuado[1]) + "</li>";
        } else if (item || numerado || recuado) {
          fecharParagrafo();
          const tipo = numerado ? "ol" : "ul";
          if (lista !== tipo) { fecharLista(); html += "<" + tipo + ">"; lista = tipo; }
          fecharItem();
          html += "<li>" + emLinha((numerado || item || recuado)[1]);
          itemAberto = true;
        } else if (linha.trim() === "") {
          fecharParagrafo();
          fecharLista();
        } else {
          fecharLista();
          paragrafo.push(linha);
        }
      });
      fecharParagrafo();
      fecharLista();
    });

    return html;
  }

  window.Markdown = { renderizar: renderizar, escapar: escapar };
})();
