/*
 * Lógica da interface do Aprendiz (JavaScript puro, sem framework).
 *
 * Organização deste arquivo:
 *   1. Utilidades (DOM, ícones, chamadas à API, avisos)
 *   2. Estado, preferências e tema
 *   3. Seletores de algoritmo
 *   4. Conversas (barra lateral)
 *   5. Mensagens (renderização, envio, efeito de digitação)
 *   6. Painel "Por que respondi isso?"
 *   7. Diálogos: ensinar, corrigir, base, addons, linguagem, configurações, reset
 *   8. Inicialização
 *
 * Toda comunicação com o "cérebro" é feita pela API local (/api/...),
 * documentada em aprendiz/api/servidor.py.
 */
(function () {
  "use strict";

  // =========================================================== 1. UTILIDADES
  const $ = (seletor, raiz) => (raiz || document).querySelector(seletor);
  const $$ = (seletor, raiz) => Array.from((raiz || document).querySelectorAll(seletor));
  const esc = window.Markdown.escapar;

  /** HTML de um ícone do conjunto definido no index.html (<symbol id="i-...">). */
  const icone = (nome, classe) => `<svg class="ic ${classe || ""}" aria-hidden="true"><use href="#i-${nome}"/></svg>`;

  /** Chama a API local e devolve o JSON (lança erro com a mensagem do servidor). */
  async function api(caminho, opcoes) {
    opcoes = opcoes || {};
    const resposta = await fetch(caminho, {
      method: opcoes.metodo || "GET",
      headers: opcoes.corpo ? { "Content-Type": "application/json" } : {},
      body: opcoes.corpo ? JSON.stringify(opcoes.corpo) : undefined,
    });
    const dados = await resposta.json().catch(() => ({}));
    if (!resposta.ok) {
      const detalhe = typeof dados.detail === "string" ? dados.detail : "Erro " + resposta.status;
      throw new Error(detalhe);
    }
    return dados;
  }

  /** Aviso rápido no rodapé da tela. */
  function avisar(texto, nomeIcone) {
    $$(".aviso-flutuante").forEach((el) => el.remove());
    const el = criar(`<div class="aviso-flutuante" role="status">${icone(nomeIcone || "check")}<span></span></div>`);
    $("span", el).textContent = texto;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3200);
  }

  /** Cria um elemento a partir de uma string HTML. */
  function criar(html) {
    const t = document.createElement("template");
    t.innerHTML = html.trim();
    return t.content.firstElementChild;
  }

  // localStorage pode falhar (modo privado, permissões): sempre com try/catch.
  const preferencias = {
    ler(chave, padrao) {
      try { return localStorage.getItem("aprendiz." + chave) || padrao; } catch (e) { return padrao; }
    },
    gravar(chave, valor) {
      try { localStorage.setItem("aprendiz." + chave, valor); } catch (e) { /* ignora */ }
    },
  };

  // =========================================================== 2. ESTADO E TEMA
  const estado = {
    conversaId: null,
    conversas: [],
    enviando: false,
    algoritmos: { busca: [], resposta: [] },
    abaLinguagem: "abreviacoes",
    status: null,
  };

  const midiaEscura = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

  /** preferência: "claro" | "escuro" | "sistema" */
  function aplicarTema(preferencia) {
    preferencias.gravar("tema", preferencia);
    const efetivo = preferencia === "sistema" ? (midiaEscura && midiaEscura.matches ? "escuro" : "claro") : preferencia;
    document.documentElement.dataset.tema = efetivo;
    // O botão do topo mostra o tema para o qual vai mudar.
    $("#btn-tema").innerHTML = icone(efetivo === "escuro" ? "sol" : "lua");
    $$("#seg-tema button").forEach((b) => b.classList.toggle("ativo", b.dataset.tema === preferencia));
  }
  if (midiaEscura) {
    midiaEscura.addEventListener("change", () => {
      if (preferencias.ler("tema", "sistema") === "sistema") aplicarTema("sistema");
    });
  }

  // =========================================================== 3. SELETORES
  async function carregarAlgoritmos() {
    estado.algoritmos = await api("/api/algoritmos");
    preencherSeletor($("#sel-busca"), estado.algoritmos.busca, preferencias.ler("busca", "bm25"));
    preencherSeletor($("#sel-resposta"), estado.algoritmos.resposta, preferencias.ler("resposta", "direta"));
  }

  function preencherSeletor(select, lista, escolhido) {
    select.innerHTML = lista
      .map((a) => `<option value="${esc(a.nome)}" title="${esc(a.descricao)}">${esc(a.titulo)}</option>`)
      .join("");
    if (lista.some((a) => a.nome === escolhido)) select.value = escolhido;
    atualizarDica(select, lista);
  }

  function atualizarDica(select, lista) {
    const a = lista.find((x) => x.nome === select.value);
    select.closest(".seletor").title = a ? `${a.titulo}: ${a.descricao}` : "";
  }

  // =========================================================== 4. CONVERSAS
  async function carregarConversas() {
    estado.conversas = await api("/api/conversas");
    renderConversas();
  }

  function renderConversas() {
    const filtro = $("#filtro-conversas").value.trim().toLowerCase();
    const lista = $("#lista-conversas");
    const visiveis = estado.conversas.filter((c) => c.titulo.toLowerCase().includes(filtro));
    lista.innerHTML = "";

    if (!visiveis.length) {
      lista.innerHTML = `<div class="lista-vazia">${filtro ? "Nenhuma conversa encontrada." : "Suas conversas aparecem aqui."}</div>`;
      return;
    }

    lista.appendChild(criar(`<div class="rotulo-lista">Conversas</div>`));
    visiveis.forEach((c) => {
      const item = criar(`
        <div class="conversa ${c.id === estado.conversaId ? "ativa" : ""}" title="${esc(c.titulo)}" tabindex="0">
          ${icone("chat")}
          <span class="nome">${esc(c.titulo)}</span>
          <span class="acoes">
            <button class="renomear" title="Renomear" aria-label="Renomear">${icone("editar")}</button>
            <button class="apagar" title="Apagar" aria-label="Apagar">${icone("lixeira")}</button>
          </span>
        </div>`);
      item.addEventListener("click", () => abrirConversa(c.id, c.titulo));
      item.addEventListener("keydown", (ev) => { if (ev.key === "Enter") abrirConversa(c.id, c.titulo); });
      $(".renomear", item).addEventListener("click", (ev) => { ev.stopPropagation(); renomearConversa(c); });
      $(".apagar", item).addEventListener("click", async (ev) => {
        ev.stopPropagation();
        if (!window.confirm("Apagar esta conversa? O conhecimento ensinado continua guardado.")) return;
        await api("/api/conversas/" + c.id, { metodo: "DELETE" });
        if (c.id === estado.conversaId) novaConversa();
        carregarConversas();
        atualizarStatus();
      });
      lista.appendChild(item);
    });
  }

  async function renomearConversa(c) {
    const titulo = window.prompt("Novo nome da conversa:", c.titulo);
    if (!titulo || !titulo.trim()) return;
    await api("/api/conversas/" + c.id, { metodo: "PATCH", corpo: { titulo: titulo.trim() } });
    if (c.id === estado.conversaId) $("#titulo-conversa").textContent = titulo.trim();
    carregarConversas();
  }

  function novaConversa() {
    estado.conversaId = null;
    $("#titulo-conversa").textContent = "Nova conversa";
    $("#mensagens").innerHTML = "";
    $("#mensagens").appendChild(boasVindas);
    renderConversas();
    $("#campo-mensagem").focus();
    fecharMenuMobile();
  }

  async function abrirConversa(id, titulo) {
    estado.conversaId = id;
    $("#titulo-conversa").textContent = titulo;
    renderConversas();
    const mensagens = await api(`/api/conversas/${id}/mensagens`);
    const area = $("#mensagens");
    area.innerHTML = "";
    mensagens.forEach((m) => {
      if (m.papel === "usuario") adicionarUsuario(m.texto);
      else adicionarAssistente(m, false);
    });
    rolarParaFim();
    fecharMenuMobile();
  }

  // =========================================================== 5. MENSAGENS
  let boasVindas; // guardado na inicialização para reaparecer em "Nova conversa"

  function rolarParaFim() {
    const area = $("#mensagens");
    area.scrollTop = area.scrollHeight;
  }

  function adicionarUsuario(texto) {
    const el = criar(`<div class="msg usuario"><div class="balao"></div></div>`);
    $(".balao", el).textContent = texto; // textContent: nunca interpreta HTML
    $("#mensagens").appendChild(el);
    rolarParaFim();
  }

  function adicionarDigitando() {
    const el = criar(`<div class="msg assistente">
      <img class="avatar" src="/static/icone.svg" alt="">
      <div class="balao digitando" aria-label="Pensando"><span></span><span></span><span></span></div></div>`);
    $("#mensagens").appendChild(el);
    rolarParaFim();
    return el;
  }

  /** Mostra uma resposta do assistente. animar=true faz o efeito de digitação. */
  function adicionarAssistente(msg, animar) {
    const meta = msg.meta || {};
    const explicacao = meta.explicacao || null;
    const classeBalao = meta.tipo === "desconhecido" ? "desconhecido" : meta.tipo === "erro" ? "erro" : "";
    const el = criar(`
      <div class="msg assistente">
        <img class="avatar" src="/static/icone.svg" alt="">
        <div class="bloco">
          <div class="balao ${classeBalao}"></div>
          <div class="fontes"></div>
          <div class="acoes-msg"></div>
          <div class="explicacao" hidden></div>
        </div>
      </div>`);
    const balao = $(".balao", el);
    $("#mensagens").appendChild(el);

    // Fontes (de onde veio a resposta)
    (meta.fontes || []).forEach((f) => {
      const nomeIcone = f.addon ? "addon" : f.tipo === "trecho" ? "arquivo" : "base";
      const dica = f.addon ? `Do addon "${f.addon}"` : "Ensinado por você";
      const ficha = criar(`<span class="fonte ${f.addon ? "addon" : ""}" title="${esc(dica)}">${icone(nomeIcone)}<span></span></span>`);
      $("span", ficha).textContent = f.addon ? `${f.addon} · ${f.titulo}` : f.titulo;
      $(".fontes", el).appendChild(ficha);
    });

    // Botões de ação
    const acoes = $(".acoes-msg", el);
    if (meta.tipo !== "erro") {
      acoes.appendChild(botaoAcao("copiar", "Copiar", async (b) => {
        try { await navigator.clipboard.writeText(msg.texto); avisar("Resposta copiada."); }
        catch (e) { avisar("Não foi possível copiar.", "alerta"); }
      }));
    }
    if (meta.tipo === "desconhecido") {
      acoes.appendChild(botaoAcao("ensinar", "Ensinar isso", () => abrirEnsinar({ pergunta: meta.pergunta }), "destaque"));
    }
    if (meta.tipo === "conhecimento") {
      acoes.appendChild(botaoAcao(meta.corrigida_por ? "check" : "corrigir",
        meta.corrigida_por ? "Corrigida" : "Corrigir", () => abrirCorrigir(msg.id, meta.pergunta)));
    }
    if (explicacao) {
      const painel = $(".explicacao", el);
      acoes.appendChild(botaoAcao("lampada", "Por que respondi isso?", (b) => {
        if (!painel.dataset.pronto) { painel.innerHTML = renderExplicacao(explicacao); painel.dataset.pronto = "1"; }
        painel.hidden = !painel.hidden;
        b.classList.toggle("ativa", !painel.hidden);
      }));
      const selo = criar(`<span class="selo">${icone("algoritmo")}<span></span></span>`);
      $("span", selo).textContent = `${nomeAlgoritmo("busca", explicacao.algoritmo_busca)} · ${explicacao.total_ms} ms`;
      acoes.appendChild(selo);
    }

    if (animar) digitar(balao, msg.texto);
    else balao.innerHTML = window.Markdown.renderizar(msg.texto);
  }

  function botaoAcao(nomeIcone, texto, aoClicar, classe) {
    const b = criar(`<button class="acao ${classe || ""}">${icone(nomeIcone)}<span></span></button>`);
    $("span", b).textContent = texto;
    b.addEventListener("click", () => aoClicar(b));
    return b;
  }

  function nomeAlgoritmo(tipo, nome) {
    const a = (estado.algoritmos[tipo] || []).find((x) => x.nome === nome);
    return a ? a.titulo : nome;
  }

  /**
   * Efeito de "digitação": revela o texto aos poucos.
   * A resposta já chegou inteira (a busca leva milissegundos); o efeito é só
   * visual, para a leitura ficar mais natural.
   */
  function digitar(elemento, texto) {
    const palavras = texto.split(/(\s+)/);
    let i = 0;
    const passo = Math.max(1, Math.ceil(palavras.length / 60)); // ~1 s no máximo
    const timer = setInterval(() => {
      i += passo;
      elemento.innerHTML = window.Markdown.renderizar(palavras.slice(0, i).join(""));
      rolarParaFim();
      if (i >= palavras.length) {
        clearInterval(timer);
        elemento.innerHTML = window.Markdown.renderizar(texto);
      }
    }, 16);
  }

  async function enviar(texto) {
    texto = (texto || "").trim();
    if (!texto || estado.enviando) return;
    estado.enviando = true;
    $("#btn-enviar").disabled = true;

    if (boasVindas.isConnected) boasVindas.remove();
    adicionarUsuario(texto);
    const digitando = adicionarDigitando();

    try {
      const r = await api("/api/chat", {
        metodo: "POST",
        corpo: {
          mensagem: texto,
          conversa_id: estado.conversaId,
          busca: $("#sel-busca").value,
          resposta: $("#sel-resposta").value,
        },
      });
      digitando.remove();
      const nova = !estado.conversaId;
      estado.conversaId = r.conversa_id;
      adicionarAssistente(r.mensagem, true);
      if (nova) $("#titulo-conversa").textContent = texto.slice(0, 48);
      carregarConversas();
      atualizarStatus();
    } catch (erro) {
      digitando.remove();
      adicionarAssistente({ texto: erro.message, meta: { tipo: "erro" } }, false);
    } finally {
      estado.enviando = false;
      atualizarBotaoEnviar();
    }
  }

  function atualizarBotaoEnviar() {
    $("#btn-enviar").disabled = estado.enviando || !$("#campo-mensagem").value.trim();
  }

  // =========================================================== 6. EXPLICAÇÃO
  function fichas(lista) {
    if (!lista || !lista.length) return `<span class="rotulo">—</span>`;
    return `<span class="fichas">${lista.map((t) => `<span class="ficha">${esc(String(t))}</span>`).join("")}</span>`;
  }

  function mapaFichas(mapa) {
    return fichas(Object.entries(mapa || {}).map(([de, para]) => `${de} → ${para}`));
  }

  function barra(valor, limiar, aceito) {
    const pct = Math.max(0, Math.min(1, valor)) * 100;
    const marca = limiar != null ? `<span class="limiar" style="left:${Math.min(100, limiar * 100)}%" title="limiar"></span>` : "";
    return `<div class="barra ${aceito ? "aceito" : ""}"><i style="width:${pct}%"></i>${marca}</div>`;
  }

  /** Monta o HTML do painel a partir da lista de etapas do pipeline. */
  function renderExplicacao(exp) {
    const partes = exp.etapas.map((etapa, indice) => {
      const d = etapa.dados || {};
      let corpo = "";

      if (etapa.nome === "Normalização") {
        corpo = `
          <div class="linha-dado"><span class="rotulo">Normalizado:</span><code>${esc(d.normalizado || "")}</code></div>
          <div class="linha-dado"><span class="rotulo">Abreviações:</span>${mapaFichas(d.expansoes)}</div>
          <div class="linha-dado"><span class="rotulo">Correções:</span>${mapaFichas(d.correcoes)}</div>
          <div class="linha-dado"><span class="rotulo">Sinônimos:</span>${mapaFichas(d.sinonimos)}</div>
          <div class="linha-dado"><span class="rotulo">Palavras-chave:</span>${fichas(d.conteudo)}</div>
          <div class="linha-dado"><span class="rotulo">Radicais:</span>${fichas(d.radicais)}</div>`;
      } else if (etapa.nome === "Interpretação") {
        const linhas = (d.intencoes || []).map((i) => `
          <tr><td>${esc(i.intencao)}${i.exata ? " (frase exata)" : ""}</td>
          <td style="width:45%">${barra(i.probabilidade)}</td>
          <td class="num">${(i.probabilidade * 100).toFixed(1)}%</td></tr>`).join("");
        corpo = `<table class="tabela"><tr><th>Intenção</th><th></th><th>Prob.</th></tr>${linhas}</table>
          <div class="linha-dado"><span class="rotulo">Entidades:</span>${fichas((d.entidades || []).map((e) => `${e.tipo}: ${e.valor}`))}</div>`;
      } else if (etapa.nome.startsWith("Busca")) {
        const linhas = (d.candidatos || []).map((c) => `
          <tr><td>${c.aceito ? icone("check", "ok") : icone("x", "nao")} ${esc(c.titulo)}</td>
          <td style="width:30%">${barra(c.confianca, d.limiar, c.aceito)}</td>
          <td class="num">${c.confianca.toFixed(2)}</td>
          <td class="num" title="Pontuação bruta do algoritmo">${c.pontuacao}</td></tr>`).join("");
        corpo = `<div class="linha-dado"><span class="rotulo">Limiar de confiança:</span>${d.limiar}
            <span class="rotulo">(marca laranja na barra)</span></div>` +
          (linhas
            ? `<table class="tabela"><tr><th>Candidato</th><th>Confiança</th><th></th><th>Pontos</th></tr>${linhas}</table>`
            : `<div class="rotulo">Nenhum candidato encontrado.</div>`);
      } else if (etapa.nome.startsWith("Resposta ·") && d.frases) {
        const linhas = d.frases.map((f) => `
          <tr><td>${esc(f.texto)}</td><td class="num">${f.relevancia}</td>
          <td class="num">${f.centralidade}</td><td class="num"><b>${f.nota}</b></td></tr>`).join("");
        corpo = `<table class="tabela"><tr><th>Frase</th><th>Relev.</th><th>Central.</th><th>Nota</th></tr>${linhas}</table>`;
      } else {
        corpo = Object.entries(d).map(([k, v]) =>
          `<div class="linha-dado"><span class="rotulo">${esc(k)}:</span>${esc(typeof v === "object" ? JSON.stringify(v) : String(v))}</div>`).join("");
      }

      return `<div class="etapa"><div class="etapa-titulo"><span><span class="num">${indice + 1}</span>${esc(etapa.nome)}</span>
        <span class="ms">${etapa.ms} ms</span></div>${corpo}</div>`;
    });

    return partes.join("") + `<div class="etapa"><div class="etapa-titulo"><span>Tempo total</span>
      <span class="ms">${exp.total_ms} ms</span></div></div>`;
  }

  // =========================================================== 7. DIÁLOGOS
  // Qualquer botão com [data-fechar] fecha o diálogo em que está.
  $$("[data-fechar]").forEach((b) => b.addEventListener("click", () => b.closest("dialog").close()));
  // Clicar fora (no fundo escuro) também fecha.
  $$("dialog").forEach((d) => d.addEventListener("click", (ev) => { if (ev.target === d) d.close(); }));

  // ---- Ensinar / editar
  function abrirEnsinar(dados) {
    dados = dados || {};
    $("#titulo-ensinar").textContent = dados.id ? "Editar conhecimento" : "Ensinar algo novo";
    $("#ensinar-id").value = dados.id || "";
    $("#ensinar-pergunta").value = dados.pergunta || "";
    $("#ensinar-conteudo").value = dados.conteudo || "";
    $("#dlg-ensinar").showModal();
    (dados.pergunta ? $("#ensinar-conteudo") : $("#ensinar-pergunta")).focus();
  }

  $("#form-ensinar").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const id = $("#ensinar-id").value;
    const corpo = { pergunta: $("#ensinar-pergunta").value.trim() || null, conteudo: $("#ensinar-conteudo").value.trim() };
    if (!corpo.conteudo) return;
    try {
      await api(id ? "/api/conhecimentos/" + id : "/api/conhecimentos", { metodo: id ? "PUT" : "POST", corpo });
      $("#dlg-ensinar").close();
      avisar(id ? "Conhecimento atualizado." : "Aprendi!");
      atualizarStatus();
      if ($("#dlg-base").open) carregarBase();
    } catch (erro) { avisar(erro.message, "alerta"); }
  });

  // ---- Corrigir
  function abrirCorrigir(mensagemId, pergunta) {
    $("#corrigir-id").value = mensagemId;
    $("#corrigir-pergunta").value = pergunta || "";
    $("#corrigir-texto").value = "";
    $("#dlg-corrigir").showModal();
    $("#corrigir-texto").focus();
  }

  $("#form-corrigir").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      await api("/api/corrigir", { metodo: "POST", corpo: {
        mensagem_id: $("#corrigir-id").value, resposta_correta: $("#corrigir-texto").value.trim() } });
      $("#dlg-corrigir").close();
      avisar("Correção aprendida!");
      atualizarStatus();
    } catch (erro) { avisar(erro.message, "alerta"); }
  });

  // ---- Base de conhecimento
  let filtroTimer;
  async function carregarBase() {
    const filtro = $("#base-filtro").value;
    const dados = await api("/api/conhecimentos?filtro=" + encodeURIComponent(filtro));
    $("#base-total").textContent = `(${dados.total})`;
    const lista = $("#lista-base");
    lista.innerHTML = dados.itens.length ? "" : `
      <div class="vazio">${icone("base")}
        <div>${filtro ? "Nada encontrado com esse filtro." : "A base está vazia. Ensine algo pelo chat ou clique em Novo."}</div></div>`;
    const tipos = { pergunta: ["chat", "pergunta"], nota: ["editar", "nota"], trecho: ["arquivo", "trecho de arquivo"] };
    dados.itens.forEach((c) => {
      const [ic, nome] = tipos[c.tipo] || ["base", c.tipo];
      const item = criar(`
        <div class="item-base">
          <div class="cab">
            <span class="etiqueta ${c.tipo}">${icone(ic)} ${esc(nome)}</span>
            <span class="pergunta">${esc(c.pergunta || "")}</span>
            <button class="botao-icone editar" title="Editar" aria-label="Editar">${icone("editar")}</button>
            <button class="botao-icone apagar" title="Apagar" aria-label="Apagar">${icone("lixeira")}</button>
          </div>
          <div class="conteudo">${esc(c.conteudo)}</div>
          <div class="origem">${icone("info")} ${esc(c.origem)} · ${new Date(c.atualizado_em).toLocaleString("pt-BR")}</div>
        </div>`);
      $(".editar", item).addEventListener("click", () => abrirEnsinar(c));
      $(".apagar", item).addEventListener("click", async () => {
        if (!window.confirm("Apagar este conhecimento?")) return;
        await api("/api/conhecimentos/" + c.id, { metodo: "DELETE" });
        carregarBase();
        atualizarStatus();
      });
      lista.appendChild(item);
    });
  }

  $("#base-filtro").addEventListener("input", () => {
    clearTimeout(filtroTimer);
    filtroTimer = setTimeout(carregarBase, 250); // espera parar de digitar
  });
  $("#btn-base-novo").addEventListener("click", () => abrirEnsinar());

  $("#base-arquivo").addEventListener("change", async (ev) => {
    for (const arquivo of ev.target.files) {
      try {
        const texto = await arquivo.text();
        const r = await api("/api/importar", { metodo: "POST", corpo: { nome: arquivo.name, texto } });
        avisar(`${arquivo.name}: ${r.trechos} trechos aprendidos.`, "importar");
      } catch (erro) { avisar(`${arquivo.name}: ${erro.message}`, "alerta"); }
    }
    ev.target.value = "";
    carregarBase();
    atualizarStatus();
  });

  // ---- Como funcionam os algoritmos
  function abrirComoFunciona() {
    const lista = $("#lista-algoritmos");
    lista.innerHTML = "";
    [["busca", "1. Busca: encontrar os conhecimentos"], ["resposta", "2. Resposta: montar o texto"]].forEach(([tipo, titulo]) => {
      lista.appendChild(criar(`<div class="grupo-algoritmos">${esc(titulo)}</div>`));
      const emUso = $("#sel-" + tipo).value;
      estado.algoritmos[tipo].forEach((a) => {
        const usando = a.nome === emUso;
        const item = criar(`
          <details class="algoritmo" ${usando ? "open" : ""}>
            <summary>
              <span><strong></strong><small></small></span>
              ${usando ? `<span class="em-uso">em uso</span>` : ""}
              ${icone("seta", "seta")}
            </summary>
            <div class="corpo"></div>
          </details>`);
        $("strong", item).textContent = a.titulo;
        $("small", item).textContent = a.descricao + (a.limiar != null ? ` · limiar de confiança: ${a.limiar}` : "");
        $(".corpo", item).innerHTML = window.Markdown.renderizar(a.explicacao || a.descricao);
        if (!usando) {
          const usar = criar(`<button class="botao">${icone("check")} Usar este algoritmo</button>`);
          usar.addEventListener("click", () => {
            const sel = $("#sel-" + tipo);
            sel.value = a.nome;
            sel.dispatchEvent(new Event("change"));
            avisar(`${a.titulo} selecionado.`, "algoritmo");
            abrirComoFunciona();
          });
          $(".corpo", item).appendChild(usar);
        }
        lista.appendChild(item);
      });
    });
    if (!$("#dlg-algoritmos").open) $("#dlg-algoritmos").showModal();
  }

  // ---- Addons
  /** Lê um arquivo escolhido pelo usuário como base64 (sem o prefixo "data:"). */
  function lerComoBase64(arquivo) {
    return new Promise((resolver, rejeitar) => {
      const leitor = new FileReader();
      leitor.onload = () => resolver(String(leitor.result).split(",")[1] || "");
      leitor.onerror = () => rejeitar(new Error("Não consegui ler o arquivo."));
      leitor.readAsDataURL(arquivo);
    });
  }

  function plural(n, singular, pluralTexto) { return `${n} ${n === 1 ? singular : pluralTexto}`; }

  async function carregarAddons() {
    const lista = $("#lista-addons");
    const itens = await api("/api/addons");
    lista.innerHTML = itens.length ? "" : `
      <div class="vazio">${icone("addon")}
        <div>Nenhum addon instalado ainda.<br>Baixe um arquivo <code>.aprendiz</code> e clique em <b>Importar addon</b>.</div></div>`;

    itens.forEach((a) => {
      const cartao = criar(`
        <div class="cartao-addon ${a.ativo ? "" : "inativo"}">
          ${icone("addon", "icone-addon")}
          <div class="titulo"><span class="nome"></span><span class="versao"></span></div>
          <label class="chave" title="Usar este addon nas respostas">
            <span class="estado">${a.ativo ? "Ativo" : "Desativado"}</span>
            <input type="checkbox" ${a.ativo ? "checked" : ""} aria-label="Ativar addon">
          </label>
          <div class="descricao"></div>
          <div class="rodape">
            <span class="autor"></span>
            <span>${plural(a.total_conhecimentos, "conhecimento", "conhecimentos")}${a.total_linguagem ? " · " + plural(a.total_linguagem, "termo de linguagem", "termos de linguagem") : ""}</span>
            <span class="acoes-addon">
              <button class="acao ver">${icone("olho")}<span>Ver conteúdo</span></button>
              ${a.site ? `<a class="acao" href="${esc(a.site)}" target="_blank" rel="noopener noreferrer">${icone("info")}<span>Site</span></a>` : ""}
              <button class="acao remover">${icone("lixeira")}<span>Remover</span></button>
            </span>
          </div>
        </div>`);
      $(".nome", cartao).textContent = a.nome;
      $(".versao", cartao).textContent = "v" + a.versao;
      $(".descricao", cartao).textContent = a.descricao || "";
      $(".autor", cartao).textContent = [a.autor && "por " + a.autor, a.licenca].filter(Boolean).join(" · ");

      $(".chave input", cartao).addEventListener("change", async (ev) => {
        const ativo = ev.target.checked;
        try {
          await api("/api/addons/" + encodeURIComponent(a.id), { metodo: "PATCH", corpo: { ativo } });
          avisar(`${a.nome} ${ativo ? "ativado" : "desativado"}.`, "addon");
          carregarAddons();
          atualizarStatus();
        } catch (erro) { ev.target.checked = !ativo; avisar(erro.message, "alerta"); }
      });

      $(".ver", cartao).addEventListener("click", async (ev) => {
        const existente = $(".amostra", cartao);
        if (existente) { existente.remove(); return; }
        const dados = await api(`/api/conhecimentos?limite=8&addon=${encodeURIComponent(a.id)}`);
        const amostra = criar(`<div class="amostra"></div>`);
        dados.itens.forEach((k) => {
          const linha = criar(`<div><b></b><span></span></div>`);
          $("b", linha).textContent = k.pergunta || "";
          $("span", linha).textContent = k.conteudo.length > 220 ? k.conteudo.slice(0, 217) + "…" : k.conteudo;
          amostra.appendChild(linha);
        });
        if (a.total_conhecimentos > dados.itens.length) {
          amostra.appendChild(criar(`<span class="rotulo">… e mais ${a.total_conhecimentos - dados.itens.length}.</span>`));
        }
        cartao.appendChild(amostra);
      });

      $(".remover", cartao).addEventListener("click", async () => {
        if (!window.confirm(`Remover o addon "${a.nome}"? O que você ensinou não é afetado.`)) return;
        await api("/api/addons/" + encodeURIComponent(a.id), { metodo: "DELETE" });
        avisar(`${a.nome} removido.`, "lixeira");
        carregarAddons();
        atualizarStatus();
      });

      lista.appendChild(cartao);
    });
  }

  $("#addon-arquivo").addEventListener("change", async (ev) => {
    for (const arquivo of ev.target.files) {
      try {
        avisar(`Importando ${arquivo.name}…`, "importar");
        const r = await api("/api/addons", { metodo: "POST", corpo: {
          nome_arquivo: arquivo.name, conteudo_base64: await lerComoBase64(arquivo) } });
        const a = r.addon;
        let mensagem = `${a.nome} instalado com ${plural(a.total_conhecimentos, "conhecimento", "conhecimentos")}.`;
        if (r.versao_anterior === a.versao) mensagem = `${a.nome} v${a.versao} reinstalado.`;
        else if (r.versao_anterior) mensagem = `${a.nome} atualizado: v${r.versao_anterior} → v${a.versao}.`;
        avisar(mensagem, "addon");
      } catch (erro) { avisar(`${arquivo.name}: ${erro.message}`, "alerta"); }
    }
    ev.target.value = "";
    carregarAddons();
    atualizarStatus();
  });

  // ---- Banco de linguagem
  const AJUDA_LINGUAGEM = {
    abreviacoes: ["Abreviação (ex.: vc)", "Significado (ex.: você)",
      "Abreviações são expandidas antes de tudo. Ao alterar, a base é reindexada."],
    sinonimos: ["Termo (ex.: automóvel)", "Trocar por (ex.: carro)",
      "Cada sinônimo é trocado pela forma principal, então ensinar sobre 'carro' também responde 'automóvel'."],
    intencoes: ["Intenção (ex.: saudacao)", "Frase de exemplo (ex.: fala aí)",
      "Exemplos treinam o classificador Naive Bayes. Intenções sociais: saudacao, despedida, agradecimento, ajuda."],
  };

  async function carregarLinguagem() {
    const dados = await api("/api/linguagem");
    const aba = estado.abaLinguagem;
    const [ph1, ph2, ajuda] = AJUDA_LINGUAGEM[aba];
    $("#ling-termo").placeholder = ph1;
    $("#ling-valor").placeholder = ph2;
    $("#ajuda-linguagem").textContent = ajuda;
    $$(".aba").forEach((b) => b.classList.toggle("ativa", b.dataset.aba === aba));

    const lista = $("#lista-linguagem");
    lista.innerHTML = "";
    dados[aba].forEach((l) => {
      const linha = criar(`
        <div class="linha-ling">
          <span class="termo">${esc(l.termo)}</span><span class="seta">→</span>
          <span class="valor">${esc(l.valor)}</span>
          <button class="botao-icone" title="Remover" aria-label="Remover">${icone("lixeira")}</button>
        </div>`);
      $("button", linha).addEventListener("click", async () => {
        const chave = aba === "intencoes" ? l.id : l.termo;
        await api(`/api/linguagem/${aba}/${encodeURIComponent(chave)}`, { metodo: "DELETE" });
        carregarLinguagem();
      });
      lista.appendChild(linha);
    });
  }

  $$(".aba").forEach((b) => b.addEventListener("click", () => {
    estado.abaLinguagem = b.dataset.aba;
    carregarLinguagem();
  }));

  $("#form-linguagem").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      await api("/api/linguagem/" + estado.abaLinguagem, { metodo: "POST",
        corpo: { termo: $("#ling-termo").value, valor: $("#ling-valor").value } });
      $("#ling-termo").value = "";
      $("#ling-valor").value = "";
      $("#ling-termo").focus();
      carregarLinguagem();
    } catch (erro) { avisar(erro.message, "alerta"); }
  });

  // ---- Configurações
  function pastaDoBanco() {
    const caminho = (estado.status && estado.status.banco) || "";
    const corte = Math.max(caminho.lastIndexOf("/"), caminho.lastIndexOf("\\"));
    return corte > 0 ? caminho.slice(0, corte) : caminho;
  }

  async function abrirConfig() {
    await atualizarStatus();
    const s = estado.status || {};
    const separador = pastaDoBanco().includes("\\") ? "\\" : "/";
    $("#dados-instalacao").innerHTML = `
      <dt>Versão</dt><dd>${esc(String(s.versao || "?"))}</dd>
      <dt>Conhecimentos</dt><dd>${esc(String(s.conhecimentos ?? "?"))}</dd>
      <dt>Conversas</dt><dd>${esc(String(s.conversas ?? "?"))}</dd>
      <dt>Addons</dt><dd>${esc(String(s.addons ?? 0))} (${esc(String(s.conhecimentos_addons ?? 0))} conhecimentos)</dd>
      <dt>Memória</dt><dd><code>${esc(s.banco || "")}</code></dd>
      <dt>Cópias de segurança</dt><dd><code>${esc(pastaDoBanco() + separador + "backups")}</code></dd>`;
    aplicarTema(preferencias.ler("tema", "sistema"));
    $("#dlg-config").showModal();
  }

  $$("#seg-tema button").forEach((b) => b.addEventListener("click", () => aplicarTema(b.dataset.tema)));

  // ---- Reset da memória
  function abrirReset() {
    const s = estado.status || {};
    const separador = pastaDoBanco().includes("\\") ? "\\" : "/";
    $("#reset-info-conhecimentos").textContent = `${s.conhecimentos ?? 0} conhecimento(s) ensinado(s)`;
    $("#reset-info-conversas").textContent = `${s.conversas ?? 0} conversa(s)`;
    $("#reset-info-addons").textContent = `${s.addons ?? 0} addon(s) instalado(s)`;
    $("#reset-pasta-backup").textContent = pastaDoBanco() + separador + "backups";
    $("#reset-confirmacao").value = "";
    ["conhecimentos", "linguagem", "conversas", "addons"].forEach((p) => { $("#reset-" + p).checked = true; });
    validarReset();
    $("#dlg-reset").showModal();
    $("#reset-confirmacao").focus();
  }

  function validarReset() {
    const algumaParte = ["conhecimentos", "linguagem", "conversas", "addons"].some((p) => $("#reset-" + p).checked);
    $("#btn-confirmar-reset").disabled = !(algumaParte && $("#reset-confirmacao").value.trim().toUpperCase() === "RESETAR");
  }

  $("#reset-confirmacao").addEventListener("input", validarReset);
  $$("#dlg-reset input[type=checkbox]").forEach((c) => c.addEventListener("change", validarReset));
  $("#btn-abrir-reset").addEventListener("click", abrirReset);

  $("#form-reset").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const botao = $("#btn-confirmar-reset");
    botao.disabled = true;
    try {
      const r = await api("/api/resetar", { metodo: "POST", corpo: {
        conhecimentos: $("#reset-conhecimentos").checked,
        linguagem: $("#reset-linguagem").checked,
        conversas: $("#reset-conversas").checked,
        addons: $("#reset-addons").checked,
        confirmacao: "RESETAR",
      } });
      $("#dlg-reset").close();
      $("#dlg-config").close();
      novaConversa();
      await carregarConversas();
      await atualizarStatus();
      avisar("Memória resetada. Cópia de segurança salva em " + r.backup, "escudo");
    } catch (erro) {
      avisar(erro.message, "alerta");
      validarReset();
    }
  });

  // =========================================================== 8. INICIALIZAÇÃO
  async function atualizarStatus() {
    try {
      estado.status = await api("/api/status");
      const s = estado.status;
      $("#status").textContent = `v${s.versao} · ${plural(s.conhecimentos, "conhecimento", "conhecimentos")}`;
      $("#contador-addons").textContent = s.addons ? String(s.addons) : "";
    } catch (e) { $("#status").textContent = "servidor indisponível"; }
  }

  function fecharMenuMobile() { $("#lateral").classList.remove("aberta"); }

  /**
   * "Sinal de vida": avisa o servidor que a interface continua aberta.
   * Quando a janela/aba é fechada, os sinais param e o app de desktop
   * encerra sozinho (veja aprendiz/desktop.py).
   */
  function enviarSinal() {
    fetch("/api/sinal", { method: "POST" }).catch(() => { /* servidor fora do ar */ });
  }

  function ligarEventos() {
    const campo = $("#campo-mensagem");

    $("#form-mensagem").addEventListener("submit", (ev) => {
      ev.preventDefault();
      const texto = campo.value;
      campo.value = "";
      campo.style.height = "auto";
      enviar(texto);
    });

    // Enter envia; Shift+Enter quebra linha.
    campo.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing) {
        ev.preventDefault();
        $("#form-mensagem").requestSubmit();
      }
    });

    // O campo cresce conforme o texto; o botão só acende com texto.
    campo.addEventListener("input", () => {
      campo.style.height = "auto";
      campo.style.height = Math.min(campo.scrollHeight, 200) + "px";
      atualizarBotaoEnviar();
    });

    $$(".cartao").forEach((b) => b.addEventListener("click", () => enviar(b.dataset.texto)));

    ["busca", "resposta"].forEach((tipo) => {
      const sel = $("#sel-" + tipo);
      sel.addEventListener("change", () => {
        preferencias.gravar(tipo, sel.value);
        atualizarDica(sel, estado.algoritmos[tipo]);
      });
    });

    $("#filtro-conversas").addEventListener("input", renderConversas);
    $("#btn-nova").addEventListener("click", novaConversa);
    $("#btn-ensinar").addEventListener("click", () => { fecharMenuMobile(); abrirEnsinar(); });
    $("#btn-base").addEventListener("click", () => { fecharMenuMobile(); $("#dlg-base").showModal(); carregarBase(); });
    $("#btn-como-funciona").addEventListener("click", abrirComoFunciona);
    $("#btn-addons").addEventListener("click", () => { fecharMenuMobile(); $("#dlg-addons").showModal(); carregarAddons(); });
    $("#btn-linguagem").addEventListener("click", () => { fecharMenuMobile(); $("#dlg-linguagem").showModal(); carregarLinguagem(); });
    $("#btn-config").addEventListener("click", () => { fecharMenuMobile(); abrirConfig(); });
    $("#btn-tema").addEventListener("click", () =>
      aplicarTema(document.documentElement.dataset.tema === "escuro" ? "claro" : "escuro"));
    $("#btn-menu").addEventListener("click", () => $("#lateral").classList.add("aberta"));
    $("#btn-fechar-menu").addEventListener("click", fecharMenuMobile);
    $("#cortina").addEventListener("click", fecharMenuMobile);

    // Atalho: Ctrl+Shift+O (ou Cmd+Shift+O) abre uma nova conversa.
    document.addEventListener("keydown", (ev) => {
      if ((ev.ctrlKey || ev.metaKey) && ev.shiftKey && ev.key.toLowerCase() === "o") {
        ev.preventDefault();
        novaConversa();
      }
    });
  }

  async function iniciar() {
    enviarSinal();
    setInterval(enviarSinal, 10000);
    aplicarTema(preferencias.ler("tema", "sistema"));
    boasVindas = $("#boas-vindas");
    ligarEventos();
    atualizarBotaoEnviar();
    try {
      await carregarAlgoritmos();
      await carregarConversas();
      await atualizarStatus();
    } catch (erro) {
      avisar("Não consegui falar com o servidor local: " + erro.message, "alerta");
    }
    $("#campo-mensagem").focus();
  }

  iniciar();
})();
