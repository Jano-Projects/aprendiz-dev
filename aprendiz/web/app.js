/*
 * Lógica da interface do Aprendiz (JavaScript puro, sem framework).
 *
 * Organização deste arquivo:
 *   1. Utilidades (DOM, ícones, chamadas à API, avisos)
 *   2. Estado, preferências e tema
 *   3. Seletores de algoritmo
 *   4. Conversas (barra lateral)
 *   5. Mensagens (renderização, envio, efeito de digitação)
 *   6. Envio ao vivo para o Monitor (o painel técnico fica em monitor.js)
 *   7. Diálogos: ensinar, corrigir, base, addons (instalar/exportar),
 *      linguagem, configurações (parâmetros/personalização), reset
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
    config: {},        // chave → item de /api/configuracoes (valor, origem…)
    exportacao: null,  // prévia carregada no diálogo "Exportar como addon"
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

  // =========================================================== 3. SELETORES E CONFIGURAÇÕES
  // Os algoritmos escolhidos ficam no SERVIDOR (Configurações → busca.padrao /
  // resposta.padrao), junto com os demais parâmetros. Assim a escolha vale
  // para qualquer janela e pode ser exportada num addon.
  async function carregarAlgoritmos() {
    estado.algoritmos = await api("/api/algoritmos");
    preencherSeletor($("#sel-busca"), estado.algoritmos.busca, valorConfig("busca.padrao", "bm25"));
    preencherSeletor($("#sel-resposta"), estado.algoritmos.resposta, valorConfig("resposta.padrao", "direta"));
  }

  function valorConfig(chave, padrao) {
    const item = estado.config[chave];
    return item ? item.valor : padrao;
  }

  /** Guarda a lista de /api/configuracoes e aplica a personalização na tela. */
  function guardarConfig(lista) {
    estado.config = {};
    lista.forEach((item) => { estado.config[item.chave] = item; });
    aplicarPersonalizacao();
  }

  async function carregarConfiguracoes() {
    guardarConfig(await api("/api/configuracoes"));
  }

  /** Grava uma configuração do dono (valor null = voltar ao padrão/addon). */
  async function salvarConfig(chave, valor) {
    const caminho = "/api/configuracoes/" + encodeURIComponent(chave);
    const lista = valor === null
      ? await api(caminho, { metodo: "DELETE" })
      : await api(caminho, { metodo: "PUT", corpo: { valor } });
    guardarConfig(lista);
    if (chave.startsWith("limiar.") || chave.endsWith(".padrao")) await carregarAlgoritmos();
  }

  /** Nome, cor e mensagem de boas-vindas (personalização do dono ou de um addon). */
  function aplicarPersonalizacao() {
    const nome = valorConfig("personalizacao.nome", "Aprendiz");
    $("#marca-nome").textContent = nome;
    document.title = nome;
    // A tela de boas-vindas sai do documento durante uma conversa, então a
    // procuramos pela referência guardada na inicialização.
    const inicio = boasVindas || $("#boas-vindas");
    $("#boas-vindas-nome", inicio).textContent = nome;
    $("#boas-vindas-texto", inicio).textContent = valorConfig("personalizacao.boas_vindas", "");

    // A cor padrão tem tons ajustados à mão para cada tema; uma cor
    // personalizada gera os tons derivados com color-mix().
    const cor = estado.config["personalizacao.cor"];
    const raiz = document.documentElement.style;
    const variaveis = ["--primaria", "--primaria-hover", "--primaria-suave", "--fundo-usuario"];
    if (cor && cor.origem !== "padrao") {
      raiz.setProperty("--primaria", cor.valor);
      raiz.setProperty("--fundo-usuario", cor.valor);
      raiz.setProperty("--primaria-hover", `color-mix(in srgb, ${cor.valor} 82%, black)`);
      raiz.setProperty("--primaria-suave", `color-mix(in srgb, ${cor.valor} 14%, var(--fundo))`);
    } else {
      variaveis.forEach((v) => raiz.removeProperty(v));
    }
  }

  function preencherSeletor(select, lista, escolhido) {
    select.innerHTML = lista
      .map((a) => `<option value="${esc(a.nome)}" title="${esc(a.descricao)}">${esc(a.apelido)} · ${esc(a.titulo)}</option>`)
      .join("");
    if (lista.some((a) => a.nome === escolhido)) select.value = escolhido;
    atualizarDica(select, lista);
  }

  function atualizarDica(select, lista) {
    const a = lista.find((x) => x.nome === select.value);
    select.closest(".seletor").title = a ? `${a.apelido} (${a.titulo}): ${a.quando_usar || a.descricao}` : "";
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
    let ultima = null;
    mensagens.forEach((m) => {
      if (m.papel === "usuario") adicionarUsuario(m.texto);
      else { adicionarAssistente(m, false); ultima = m; }
    });
    if (ultima) window.Monitor.mostrar(ultima, false);
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
          <div class="recomendacao" hidden></div>
          <div class="fontes"></div>
          <div class="acoes-msg"></div>
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

    // Recomendação de addon (compreensão): abrir na loja ou ativar o instalado
    const rec = meta.recomendacao;
    if (rec) {
      const caixa = $(".recomendacao", el);
      caixa.hidden = false;
      caixa.innerHTML = `${icone("addon")}<div class="texto"><b></b><span></span></div>`;
      $("b", caixa).textContent = rec.nome;
      $("span", caixa).textContent = rec.acao === "ativar"
        ? "Instalado, mas desativado." : "Disponível na loja oficial.";
      if (rec.acao === "ativar") {
        caixa.appendChild(botaoAcao("check", "Ativar e perguntar de novo", async (b) => {
          b.disabled = true;
          try {
            await api(`/api/addons/${encodeURIComponent(rec.id)}`, { metodo: "PATCH", corpo: { ativo: true } });
            avisar(`Addon "${rec.nome}" ativado.`, "check");
            enviar(meta.pergunta);
          } catch (erro) { b.disabled = false; avisar(erro.message, "alerta"); }
        }, "destaque"));
      } else {
        caixa.appendChild(botaoAcao("link", "Ver na loja oficial", () => abrirLoja(rec.id), "destaque"));
      }
    }

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
    if (meta.tipo === "conhecimento" && msg.id) {
      // 2.6: 👍/👎 viram exemplos para o ajuste pessoal da Calibrada.
      ["util", "nao_util"].forEach((valor) => {
        const b = botaoAcao(valor === "util" ? "util" : "nao-util", valor === "util" ? "Útil" : "Não ajudou",
          async (botao) => {
            try {
              await api("/api/avaliar", { metodo: "POST", corpo: { mensagem_id: msg.id, util: valor === "util" } });
              meta.avaliacao = valor;
              acoes.querySelectorAll(".acao.avaliado").forEach((x) => x.classList.remove("avaliado"));
              botao.classList.add("avaliado");
              avisar(valor === "util" ? "Obrigado! Vou lembrar que essa resposta serviu."
                                      : "Anotado. Vou levar isso em conta na busca Calibrada.");
            } catch (e) { avisar(e.message, "alerta"); }
          });
        if (meta.avaliacao === valor) b.classList.add("avaliado");
        acoes.appendChild(b);
      });
    }
    if (meta.tipo === "conhecimento") {
      acoes.appendChild(botaoAcao(meta.corrigida_por ? "check" : "corrigir",
        meta.corrigida_por ? "Corrigida" : "Corrigir", () => abrirCorrigir(msg.id, meta.pergunta)));
    }
    if (explicacao) {
      // 2.4: o raciocínio fica no Monitor, o painel técnico à direita.
      acoes.appendChild(botaoAcao("monitor", "Ver no monitor", () => window.Monitor.focar(msg)));
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
    return a ? `${a.apelido} · ${a.titulo}` : nome;
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
    const pedido = {
      mensagem: texto,
      conversa_id: estado.conversaId,
      busca: $("#sel-busca").value,
      resposta: $("#sel-resposta").value,
    };
    window.Monitor.comecar(texto);

    try {
      const r = await perguntarAoVivo(pedido);
      await window.Monitor.terminar();   // na câmera lenta, espera as etapas
      digitando.remove();
      const nova = !estado.conversaId;
      estado.conversaId = r.conversa_id;
      adicionarAssistente(r.mensagem, true);
      window.Monitor.mostrar(r.mensagem, true);
      if (nova) $("#titulo-conversa").textContent = texto.slice(0, 48);
      carregarConversas();
      atualizarStatus();
    } catch (erro) {
      digitando.remove();
      window.Monitor.cancelar();
      adicionarAssistente({ texto: erro.message, meta: { tipo: "erro" } }, false);
    } finally {
      estado.enviando = false;
      atualizarBotaoEnviar();
    }
  }

  // =========================================================== 6. ENVIO AO VIVO
  /**
   * Envia pela rota /api/chat/fluxo, que responde em NDJSON: uma linha JSON
   * por etapa do pipeline, assim que ela termina, e no fim a resposta.
   * Cada etapa vai para o Monitor. Se o navegador não ler fluxos, usa a
   * rota comum /api/chat (o Monitor mostra tudo de uma vez no fim).
   */
  async function perguntarAoVivo(pedido) {
    const resposta = await fetch("/api/chat/fluxo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(pedido),
    });
    if (!resposta.ok || !resposta.body || !resposta.body.getReader) {
      return api("/api/chat", { metodo: "POST", corpo: pedido });
    }
    const leitor = resposta.body.getReader();
    const decodificador = new TextDecoder();
    let pendente = "", fim = null;
    const tratar = (linha) => {
      if (!linha.trim()) return;
      const evento = JSON.parse(linha);
      if (evento.evento === "etapa") window.Monitor.etapa(evento);
      else if (evento.evento === "fim") fim = evento.resposta;
      else if (evento.evento === "erro") throw new Error(evento.mensagem);
    };
    for (;;) {
      const { value, done } = await leitor.read();
      if (done) break;
      pendente += decodificador.decode(value, { stream: true });
      const linhas = pendente.split("\n");
      pendente = linhas.pop();          // a última pode estar incompleta
      linhas.forEach(tratar);
    }
    tratar(pendente);
    if (!fim) throw new Error("A resposta foi interrompida.");
    return fim;
  }

  function atualizarBotaoEnviar() {
    $("#btn-enviar").disabled = estado.enviando || !$("#campo-mensagem").value.trim();
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
    const tipos = { pergunta: ["chat", "pergunta"], nota: ["editar", "nota"], trecho: ["arquivo", "trecho de arquivo"],
      verbete: ["linguagem", "verbete"] };
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
        $("strong", item).textContent = `${a.apelido} · ${a.titulo}`;
        $("small", item).textContent = a.descricao;
        $(".corpo", item).innerHTML = `<div class="ficha-algoritmo">
            ${a.quando_usar ? `<p><b>Quando usar:</b> ${esc(a.quando_usar)}</p>` : ""}
            <p><span class="chip custo-${esc(a.custo)}">custo ${esc(a.custo)}</span>
            ${a.limiar != null ? `<span class="chip">limiar de confiança ${esc(String(a.limiar))}</span>` : ""}</p>
          </div>` + window.Markdown.renderizar(a.explicacao || a.descricao);
        if (!usando) {
          const usar = criar(`<button class="botao">${icone("check")} Usar este algoritmo</button>`);
          usar.addEventListener("click", () => {
            const sel = $("#sel-" + tipo);
            sel.value = a.nome;
            sel.dispatchEvent(new Event("change"));
            avisar(`${a.apelido} (${a.titulo}) selecionado.`, "algoritmo");
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

  const CLASSIFICACOES = {
    memoria: "Memória", linguagem: "Linguagem", parametros: "Parâmetros",
    personalizacao: "Personalização", compreensao: "Compreensão", vetores: "Vetores",
    algoritmo: "Algoritmo", aplicacao: "Aplicação",
  };

  /** Selo de origem. "Oficial" é uma declaração do arquivo: os verdadeiros vêm da loja oficial. */
  function seloOrigem(origem) {
    return origem === "oficial"
      ? `<span class="etiqueta oficial" title="Declarado como oficial da Jano Projects pelo próprio arquivo">${icone("selo")}Oficial Jano</span>`
      : `<span class="etiqueta terceiros" title="Feito por outra pessoa: confira a fonte">${icone("pessoas")}Terceiros</span>`;
  }

  function selosClassificacao(lista) {
    return (lista || []).map((t) => `<span class="etiqueta classe">${esc(CLASSIFICACOES[t] || t)}</span>`).join("");
  }

  /** Addons do formato 1 não têm classificação no manifesto: deduz pelo conteúdo. */
  function classificacaoDoAddon(a) {
    const m = a.manifesto || {};
    if (m.classificacao) return m.classificacao;
    return [a.total_conhecimentos && "memoria", a.total_linguagem && "linguagem"].filter(Boolean);
  }

  async function carregarAddons() {
    const lista = $("#lista-addons");
    const [itens, grupos] = await Promise.all([api("/api/addons"), api("/api/addons/grupos")]);
    lista.innerHTML = itens.length ? "" : `
      <div class="vazio">${icone("addon")}
        <div>Nenhum addon instalado ainda.<br>Baixe um arquivo <code>.aprendiz</code> na loja oficial
          e clique em <b>Importar addon</b>.</div></div>`;
    const cartoes = {};  // id → cartão; depois são distribuídos pelos grupos

    itens.forEach((a) => {
      const cartao = criar(`
        <div class="cartao-addon ${a.ativo ? "" : "inativo"}">
          ${icone("addon", "icone-addon")}
          <div class="titulo"><span class="nome"></span><span class="versao"></span>
            ${seloOrigem((a.manifesto || {}).origem)}${selosClassificacao(classificacaoDoAddon(a))}</div>
          <label class="chave" title="Usar este addon nas respostas">
            <span class="estado">${a.ativo ? "Ativo" : "Desativado"}</span>
            <input type="checkbox" ${a.ativo ? "checked" : ""} aria-label="Ativar addon">
          </label>
          <div class="descricao"></div>
          <div class="rodape">
            <span class="autor"></span>
            <span>${[
              a.total_conhecimentos && plural(a.total_conhecimentos, "conhecimento", "conhecimentos"),
              a.total_linguagem && plural(a.total_linguagem, "termo de linguagem", "termos de linguagem"),
              a.total_configuracoes && plural(a.total_configuracoes, "configuração", "configurações"),
              a.total_recursos && "recursos de compreensão",
            ].filter(Boolean).join(" · ")}</span>
            <span class="deps"></span>
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
      const deps = (a.manifesto || {}).dependencias || [];
      if (deps.length) {
        $(".deps", cartao).innerHTML = icone("link");
        $(".deps", cartao).append("depende de " + deps.map((d) => `${d.nome} v${d.versao}`).join(", "));
      }

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

      cartoes[a.id] = cartao;
    });

    // Grupos: addons que recomendam o mesmo padrão de busca e resposta.
    grupos.forEach((g) => lista.appendChild(grupoDeAddons(g, cartoes, grupos)));
  }

  /**
   * Seção de um grupo. "Usar este grupo" ativa os addons dele, aplica o padrão
   * recomendado e (se o dono confirmar) desativa os addons de outros padrões,
   * para todos funcionarem no mesmo ambiente de busca.
   */
  function grupoDeAddons(g, cartoes, grupos) {
    const ativos = g.addons.filter((a) => a.ativo).length;
    const secao = criar(`
      <section class="grupo-addons ${g.em_uso ? "em-uso" : ""}">
        <header>
          <div class="texto">
            <b></b>
            <small></small>
          </div>
          <div class="acoes-grupo"></div>
        </header>
      </section>`);
    $("b", secao).textContent = g.chave ? `Recomendado: ${g.titulo}` : g.titulo;
    $("small", secao).textContent = g.chave
      ? `${plural(g.addons.length, "addon", "addons")}, ${ativos} ativo(s)` + (g.em_uso ? " · padrão em uso" : "")
      : "Addons de personalização ou sem algoritmo recomendado";
    const acoes = $(".acoes-grupo", secao);

    if (g.chave && g.addons.length > 1) {
      const todos = criar(`<button class="acao">${icone(ativos === g.addons.length ? "x" : "check")}<span></span></button>`);
      $("span", todos).textContent = ativos === g.addons.length ? "Desativar grupo" : "Ativar grupo";
      todos.addEventListener("click", async () => {
        await api("/api/addons/grupo", { metodo: "POST", corpo: {
          ids: g.addons.map((a) => a.id), ativo: ativos !== g.addons.length } });
        carregarAddons();
        atualizarStatus();
      });
      acoes.appendChild(todos);
    }
    if (g.chave && !(g.em_uso && ativos === g.addons.length)) {
      const usar = criar(`<button class="botao botao-primario pequeno">${icone("check")} Usar este grupo</button>`);
      usar.addEventListener("click", async () => {
        const outros = grupos.filter((o) => o.chave && o.chave !== g.chave)
          .flatMap((o) => o.addons.filter((a) => a.ativo));
        try {
          await api("/api/addons/grupo", { metodo: "POST", corpo: { ids: g.addons.map((a) => a.id), ativo: true } });
          await api("/api/padrao", { metodo: "PUT", corpo: { busca: g.busca, resposta: g.resposta } });
          if (outros.length && window.confirm(
            `Desativar também ${plural(outros.length, "addon", "addons")} de outros padrões, ` +
            `para todos funcionarem do mesmo jeito?\n\n${outros.map((a) => "• " + a.nome).join("\n")}`)) {
            await api("/api/addons/grupo", { metodo: "POST", corpo: { ids: outros.map((a) => a.id), ativo: false } });
          }
          await carregarConfiguracoes();
          await carregarAlgoritmos();
          avisar(`Padrão ${g.titulo} em uso.`, "check");
        } catch (erro) { avisar(erro.message, "alerta"); }
        carregarAddons();
        atualizarStatus();
      });
      acoes.appendChild(usar);
    }
    g.addons.forEach((a) => { if (cartoes[a.id]) secao.appendChild(cartoes[a.id]); });
    return secao;
  }

  const SITUACAO_DEPENDENCIA = {
    instalado: ["check", "instalado"],
    desativado: ["alerta", "instalado, mas desativado"],
    desatualizado: ["alerta", "instalado em versão mais antiga"],
    ausente: ["alerta", "não instalado"],
  };

  /**
   * Mostra o que o addon traz e espera a decisão do dono.
   * Resolve true se ele clicar em Instalar.
   */
  /** Pacote da loja (2.2): uma confirmação só, com a lista; depois instala todos, na ordem. */
  async function instalarPacote(corpo) {
    const info = await api("/api/addons/pacote/inspecionar", { metodo: "POST", corpo });
    $("#instalar-titulo").textContent = `Instalar pacote com ${plural(info.addons.length, "addon", "addons")}`;
    const resumo = $("#instalar-resumo");
    resumo.innerHTML = "";
    $("#instalar-opcoes").innerHTML = "";
    const bloco = criar(`<div class="bloco-resumo"><h4>${icone("addon")} Addons do pacote, na ordem de instalação</h4></div>`);
    info.addons.forEach((a) => {
      const linha = criar(`<div class="linha-resumo">${icone("addon")}<span></span><small></small></div>`);
      $("span", linha).textContent = `${a.nome} v${a.versao}`;
      $("small", linha).textContent = !a.versao_anterior ? "novo"
        : a.versao_anterior === a.versao ? "já instalado (reinstala)" : `atualiza a v${a.versao_anterior}`;
      bloco.appendChild(linha);
    });
    resumo.appendChild(bloco);
    if (info.addons.some((a) => a.origem !== "oficial")) {
      resumo.appendChild(criar(`<div class="aviso-backup alerta">${icone("pessoas")}<span>O pacote tem addons de terceiros.
        Só instale se confiar em quem o enviou. Addons contêm apenas dados: nada é executado.</span></div>`));
    }
    const dlg = $("#dlg-instalar");
    const ok = await new Promise((resolver) => {
      dlg.returnValue = "";
      dlg.addEventListener("close", () => resolver(dlg.returnValue === "instalar"), { once: true });
      dlg.showModal();
    });
    if (!ok) return;
    avisar(`Instalando ${plural(info.addons.length, "addon", "addons")}…`, "importar");
    const r = await api("/api/addons/pacote", { metodo: "POST", corpo });
    const falhas = r.resultado.filter((x) => !x.ok);
    avisar(`${plural(r.resultado.length - falhas.length, "addon instalado", "addons instalados")}`
      + (falhas.length ? `; ${falhas.length} com problema: ${falhas.map((x) => `${x.arquivo} (${x.erro})`).join("; ")}` : "."),
      falhas.length ? "alerta" : "addon");
  }

  function confirmarInstalacao(info) {
    const m = info.manifesto;
    const t = info.totais;
    $("#instalar-titulo").textContent = info.versao_anterior
      ? `Atualizar ${m.nome} (v${info.versao_anterior} → v${m.versao})` : `Instalar ${m.nome}`;

    const resumo = $("#instalar-resumo");
    resumo.innerHTML = `
      <div class="selos">${seloOrigem(m.origem)}<span class="versao">v${esc(m.versao)}</span>${selosClassificacao(m.classificacao)}</div>
      <p class="descricao"></p>
      <dl class="dados">
        <dt>Autor</dt><dd class="autor"></dd>
        <dt>Traz</dt><dd>${[
          t.conhecimentos && plural(t.conhecimentos, "conhecimento", "conhecimentos"),
          t.linguagem && plural(t.linguagem, "termo de linguagem", "termos de linguagem"),
          t.parametros && plural(t.parametros, "parâmetro", "parâmetros"),
          t.ajuste !== null && t.ajuste !== undefined && `ajuste da busca Calibrada${t.ajuste ? ` (${t.ajuste} avaliações)` : ""}`,
          t.personalizacao && plural(t.personalizacao, "personalização", "personalizações"),
          t.compreensao && plural(t.compreensao, "regra de compreensão", "regras de compreensão"),
          t.lemas && `${t.lemas.toLocaleString("pt-BR")} palavras no léxico`,
          t.vetores && `vetores de ${t.vetores.toLocaleString("pt-BR")} palavras`,
        ].filter(Boolean).join(" · ")}</dd>
        <dt>Feito com</dt><dd>${m.app.criado_com ? "Aprendiz " + esc(m.app.criado_com) : "versão não informada"}${m.app.versao_minima ? ` (exige ${esc(m.app.versao_minima)} ou mais novo)` : ""}</dd>
        <dt>SHA-256</dt><dd><code title="${esc(info.hash)}">${esc(info.hash.slice(0, 16))}…</code></dd>
      </dl>`;
    $(".descricao", resumo).textContent = m.descricao || "";
    $(".autor", resumo).textContent = [m.autor, m.licenca].filter(Boolean).join(" · ") || "não informado";

    if (m.origem !== "oficial") {
      resumo.appendChild(criar(`<div class="aviso-backup alerta">${icone("pessoas")}<span>Addon de terceiros.
        Só instale se confiar em quem o enviou. Ele contém apenas dados: nada é executado.</span></div>`));
    } else {
      resumo.appendChild(criar(`<div class="aviso-backup">${icone("selo")}<span>Addons oficiais são distribuídos
        só pela loja oficial da Jano Projects. Se este arquivo veio de outro lugar, confira o SHA-256 com o da loja.
        <button type="button" class="acao destaque" data-abrir-loja>${icone("link")}<span>Abrir loja oficial</span></button></span></div>`));
    }
    // Recomendação de algoritmos e grupo: opções que valem na hora de instalar.
    $("#instalar-opcoes").innerHTML = "";
    const rec = info.recomendado;
    if (rec) {
      const acerto = rec.acerto != null ? ` (acertou ${Math.round(rec.acerto * 100)}% no teste do autor)` : "";
      const bloco = criar(`<div class="bloco-resumo"><h4>${icone("algoritmo")} Recomendado para este addon</h4>
        <div class="linha-resumo">${icone("busca")}<span></span></div></div>`);
      $(".linha-resumo span", bloco).textContent = `Busca ${rec.titulo_busca} · resposta ${rec.titulo_resposta}${acerto}`;
      resumo.appendChild(bloco);
      if (!rec.disponivel) {
        bloco.appendChild(criar(`<small class="ajuda">Algum desses algoritmos não existe nesta versão do Aprendiz; o padrão atual continua valendo.</small>`));
      } else if (!rec.ja_em_uso) {
        const marcar = !rec.outros_padroes_ativos.length;
        const opcao = criar(`<label class="opcao-instalar"><input type="checkbox" id="opt-recomendacao" ${marcar ? "checked" : ""}>
          <span><b></b><small></small></span></label>`);
        $("b", opcao).textContent = `Usar ${rec.titulo_busca} · ${rec.titulo_resposta} como padrão`;
        $("small", opcao).textContent = rec.outros_padroes_ativos.length
          ? `Outros addons ativos recomendam outro padrão (${rec.outros_padroes_ativos.join("; ")}).`
          : "Troca os algoritmos do topo da tela. Dá para mudar de novo quando quiser.";
        $("#instalar-opcoes").appendChild(opcao);
      }
    }
    if (info.grupo && info.grupo.inativos.length) {
      const opcao = criar(`<label class="opcao-instalar"><input type="checkbox" id="opt-grupo" checked>
        <span><b></b><small></small></span></label>`);
      $("b", opcao).textContent = `Ativar também ${plural(info.grupo.inativos.length, "addon desativado", "addons desativados")} do mesmo grupo`;
      $("small", opcao).textContent = info.grupo.inativos.map((a) => a.nome).join(", ");
      $("#instalar-opcoes").appendChild(opcao);
    }

    if (info.dependencias.length) {
      const bloco = criar(`<div class="bloco-resumo"><h4>${icone("link")} Complementa estes addons</h4></div>`);
      info.dependencias.forEach((d) => {
        const [nomeIcone, texto] = SITUACAO_DEPENDENCIA[d.situacao];
        const linha = criar(`<div class="linha-resumo ${d.situacao}">${icone(nomeIcone)}<span></span><small></small></div>`);
        $("span", linha).textContent = `${d.nome} v${d.versao}`;
        $("small", linha).textContent = texto + (d.versao_instalada && d.situacao !== "instalado" ? ` (v${d.versao_instalada})` : "");
        bloco.appendChild(linha);
      });
      if (info.dependencias.some((d) => d.situacao !== "instalado")) {
        bloco.appendChild(criar(`<small class="ajuda">Ele funciona sozinho, mas as respostas ficam mais completas com as dependências instaladas e ativas.</small>`));
      }
      resumo.appendChild(bloco);
    }
    if (info.configuracoes.length) {
      const bloco = criar(`<div class="bloco-resumo"><h4>${icone("config")} Ajusta</h4></div>`);
      info.configuracoes.forEach((c) => {
        const linha = criar(`<div class="linha-resumo">${icone("seta")}<span></span><small></small></div>`);
        $("span", linha).textContent = `${c.titulo}: ${c.valor}`;
        $("small", linha).textContent = c.dono_ja_definiu ? "você já definiu este valor; o seu continua valendo" : "";
        bloco.appendChild(linha);
      });
      resumo.appendChild(bloco);
    }
    if (info.amostra.length) {
      const bloco = criar(`<div class="bloco-resumo"><h4>${icone("olho")} Amostra</h4></div>`);
      info.amostra.forEach((texto) => {
        const linha = criar(`<div class="linha-resumo">${icone("base")}<span></span></div>`);
        $("span", linha).textContent = texto;
        bloco.appendChild(linha);
      });
      resumo.appendChild(bloco);
    }

    const dlg = $("#dlg-instalar");
    return new Promise((resolver) => {
      dlg.returnValue = "";
      dlg.addEventListener("close", () => resolver(dlg.returnValue === "instalar"), { once: true });
      dlg.showModal();
    });
  }

  $("#addon-arquivo").addEventListener("change", async (ev) => {
    for (const arquivo of ev.target.files) {
      try {
        const corpo = { nome_arquivo: arquivo.name, conteudo_base64: await lerComoBase64(arquivo) };
        if (arquivo.name.toLowerCase().endsWith(".aprendiz-pacote")) {
          await instalarPacote(corpo);
          continue;
        }
        const info = await api("/api/addons/inspecionar", { metodo: "POST", corpo });
        if (!(await confirmarInstalacao(info))) continue;
        avisar(`Instalando ${arquivo.name}…`, "importar");
        corpo.usar_recomendacao = !!($("#opt-recomendacao") && $("#opt-recomendacao").checked);
        corpo.ativar_grupo = !!($("#opt-grupo") && $("#opt-grupo").checked);
        const r = await api("/api/addons", { metodo: "POST", corpo });
        const a = r.addon;
        let mensagem = a.total_conhecimentos || !a.total_recursos
          ? `${a.nome} instalado com ${plural(a.total_conhecimentos, "conhecimento", "conhecimentos")}.`
          : `${a.nome} instalado.`;
        if (r.versao_anterior === a.versao) mensagem = `${a.nome} v${a.versao} reinstalado.`;
        else if (r.versao_anterior) mensagem = `${a.nome} atualizado: v${r.versao_anterior} → v${a.versao}.`;
        avisar(mensagem, "addon");
      } catch (erro) { avisar(`${arquivo.name}: ${erro.message}`, "alerta"); }
    }
    ev.target.value = "";
    carregarAddons();
    atualizarStatus();
    await carregarConfiguracoes();   // o addon pode ter trazido parâmetros/personalização
    await carregarAlgoritmos();
  });

  // ---- Exportar o conhecimento do dono como addon
  async function abrirExportar() {
    let dados;
    try { dados = await api("/api/exportar"); }
    catch (erro) { avisar(erro.message, "alerta"); return; }
    estado.exportacao = dados;
    const lista = $("#exp-itens");
    lista.innerHTML = "";

    /** Um grupo de caixas de seleção com "marcar todos". */
    function grupo(titulo, nomeIcone, itens, ajuda) {
      if (!itens.length) return;
      const bloco = criar(`
        <details class="grupo-exportar" open>
          <summary>${icone(nomeIcone)}<strong></strong><span class="contador"></span>
            <label class="marcar-todos"><input type="checkbox"> todos</label></summary>
          ${ajuda ? `<p class="ajuda"></p>` : ""}
          <div class="itens"></div>
        </details>`);
      $("strong", bloco).textContent = titulo;
      if (ajuda) $(".ajuda", bloco).textContent = ajuda;
      itens.forEach((item) => {
        const linha = criar(`<label class="item-exportar">
            <input type="checkbox" data-grupo="${esc(item.grupo)}" data-valor="${esc(item.valor)}" ${item.marcado ? "checked" : ""}>
            <span class="texto"><b></b><small></small></span></label>`);
        $("b", linha).textContent = item.titulo;
        $("small", linha).textContent = item.detalhe || "";
        (item.avisos || []).forEach((motivo) => {
          const etiqueta = criar(`<span class="etiqueta perigo" title="Pode ser um dado pessoal">${icone("alerta")}<span></span></span>`);
          $("span", etiqueta).textContent = motivo;
          $(".texto", linha).appendChild(etiqueta);
        });
        $(".itens", bloco).appendChild(linha);
      });
      const todos = $(".marcar-todos input", bloco);
      todos.addEventListener("click", (ev) => ev.stopPropagation());
      todos.addEventListener("change", () => {
        $$(".itens input", bloco).forEach((c) => { c.checked = todos.checked; });
        contarExportacao();
      });
      $$(".itens input", bloco).forEach((c) => c.addEventListener("change", contarExportacao));
      lista.appendChild(bloco);
    }

    const corta = (t, n) => (t.length > n ? t.slice(0, n - 1) + "…" : t);
    grupo("Conhecimentos", "base", dados.conhecimentos.map((k) => ({
      grupo: "conhecimentos", valor: k.id, marcado: k.marcado, avisos: k.avisos,
      titulo: corta(k.pergunta || k.conteudo, 90), detalhe: k.pergunta ? corta(k.conteudo, 140) : "",
    })));
    ["sinonimos", "abreviacoes"].forEach((tipo) => grupo(
      tipo === "sinonimos" ? "Sinônimos" : "Abreviações", "linguagem",
      dados.linguagem[tipo].map((l) => ({ grupo: tipo, valor: l.termo, marcado: true,
        titulo: `${l.termo} → ${l.valor}` }))));
    grupo("Parâmetros", "config", dados.parametros.map((c) => ({
      grupo: "parametros", valor: c.chave, marcado: c.marcado, titulo: `${c.titulo}: ${c.valor}` })));
    grupo("Personalização", "editar", dados.personalizacao.map((c) => ({
      grupo: "personalizacao", valor: c.chave, marcado: c.marcado, titulo: `${c.titulo}: ${c.valor}` })));
    grupo("Ajuste pessoal da busca", "algoritmo", (dados.ajuste || []).map((a) => ({
      grupo: "ajuste", valor: a.id, marcado: a.marcado,
      titulo: `Pesos da Calibrada aprendidos com ${a.avaliacoes} avaliações`,
      detalhe: a.data ? `treinados em ${a.data}` : "",
    })), "Só números (o peso de cada sinal). Nenhuma pergunta ou resposta vai junto.");
    grupo("Dependências (addons instalados)", "link", dados.dependencias.map((d) => ({
      grupo: "dependencias", valor: d.id, marcado: d.marcado,
      titulo: `${d.nome} v${d.versao}`,
      detalhe: (d.origem === "oficial" ? "oficial Jano" : "de terceiros") + (d.ativo ? "" : " · desativado"),
    })), "Só o nome e a versão vão no arquivo, para quem receber saber o que instalar junto.");

    if (!lista.children.length) {
      lista.innerHTML = `<div class="vazio">${icone("base")}<div>Ainda não há nada seu para exportar.<br>Ensine algo ao assistente primeiro.</div></div>`;
    }
    preencherRecomendacao(dados.recomendacao);
    contarExportacao();
    $("#dlg-exportar").showModal();
    $("#exp-nome").focus();
  }

  /** Mostra o resultado do teste de algoritmos e pré-seleciona a recomendação. */
  function preencherRecomendacao(rec) {
    const busca = $("#exp-busca");
    const resposta = $("#exp-resposta");
    const opcoes = (select, lista) => {
      select.innerHTML = "";
      lista.forEach((a) => {
        const o = criar(`<option></option>`);
        o.value = a.nome;
        o.textContent = a.titulo.replace(" (padrão)", "");
        select.appendChild(o);
      });
    };
    opcoes(busca, estado.algoritmos.busca);
    opcoes(resposta, estado.algoritmos.resposta);
    if (rec) {
      busca.value = rec.busca;
      resposta.value = rec.resposta;
      const acertos = Object.entries(rec.acertos)
        .map(([nome, valor]) => `${nome} ${Math.round(valor * 100)}%`).join(" · ");
      $("#exp-teste").textContent = `Teste com ${rec.perguntas} perguntas feitas a partir dos itens marcados (acerto@1): ${acertos}.`;
    } else {
      $("#exp-teste").textContent = "Marque conhecimentos para testar os algoritmos.";
    }
  }

  $("#btn-recalcular").addEventListener("click", async () => {
    const corpo = { conhecimentos: [], abreviacoes: [], sinonimos: [] };
    $$("#exp-itens input[data-grupo]:checked").forEach((c) => {
      if (corpo[c.dataset.grupo]) corpo[c.dataset.grupo].push(c.dataset.valor);
    });
    $("#exp-teste").textContent = "Testando…";
    try { preencherRecomendacao(await api("/api/exportar/recomendar", { metodo: "POST", corpo })); }
    catch (erro) { avisar(erro.message, "alerta"); }
  });

  function contarExportacao() {
    $$("#exp-itens .grupo-exportar").forEach((bloco) => {
      const caixas = $$(".itens input", bloco);
      const marcadas = caixas.filter((c) => c.checked).length;
      $(".contador", bloco).textContent = `${marcadas} de ${caixas.length}`;
      $(".marcar-todos input", bloco).checked = marcadas === caixas.length;
    });
    const conteudo = $$("#exp-itens input[data-grupo]:checked").filter((c) => c.dataset.grupo !== "dependencias").length;
    $("#exp-resumo").textContent = conteudo ? plural(conteudo, "item marcado", "itens marcados") : "nada marcado";
    $("#btn-gerar-addon").disabled = !conteudo;
  }

  $("#form-exportar").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const corpo = {
      manifesto: {
        nome: $("#exp-nome").value.trim(), versao: $("#exp-versao").value.trim(),
        autor: $("#exp-autor").value.trim() || null, licenca: $("#exp-licenca").value.trim() || null,
        descricao: $("#exp-descricao").value.trim() || null,
      },
      conhecimentos: [], abreviacoes: [], sinonimos: [], parametros: [], personalizacao: [], ajuste: [], dependencias: [],
      recomendado: { busca: $("#exp-busca").value, resposta: $("#exp-resposta").value },
    };
    $$("#exp-itens input[data-grupo]:checked").forEach((c) => corpo[c.dataset.grupo].push(c.dataset.valor));

    const botao = $("#btn-gerar-addon");
    botao.disabled = true;
    try {
      // Aqui não usamos api(): a resposta é um arquivo (bytes), não JSON.
      const resposta = await fetch("/api/exportar", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
      if (!resposta.ok) {
        const erro = await resposta.json().catch(() => ({}));
        throw new Error(typeof erro.detail === "string" ? erro.detail : "Erro " + resposta.status);
      }
      const disposicao = resposta.headers.get("Content-Disposition") || "";
      const nome = (disposicao.match(/filename="([^"]+)"/) || [])[1] || "meu-addon.aprendiz";
      const url = URL.createObjectURL(await resposta.blob());
      const link = criar(`<a hidden></a>`);
      link.href = url;
      link.download = nome;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
      $("#dlg-exportar").close();
      avisar(`${nome} gerado. Procure na sua pasta de downloads.`, "exportar");
    } catch (erro) {
      avisar(erro.message, "alerta");
    } finally {
      contarExportacao();
    }
  });

  $("#btn-exportar").addEventListener("click", abrirExportar);

  // ---- Loja oficial
  /**
   * Abre a loja oficial no navegador padrão do sistema. A interface não manda
   * endereço nenhum: o servidor abre o que está fixo em config.URL_LOJA_OFICIAL.
   * Funciona para qualquer botão com [data-abrir-loja], inclusive os criados depois.
   */
  async function abrirLoja(addonId) {
    try {
      // Com um addon (recomendação), a loja já abre filtrada nele.
      const r = await api("/api/loja-oficial", { metodo: "POST", corpo: addonId ? { addon: addonId } : undefined });
      if (r.aberto) avisar("Loja oficial aberta no navegador.", "link");
      else avisar("Não consegui abrir o navegador. Acesse: " + r.url, "alerta");
    } catch (erro) { avisar(erro.message, "alerta"); }
  }
  document.addEventListener("click", (ev) => {
    if (ev.target.closest("[data-abrir-loja]")) { ev.preventDefault(); abrirLoja(); }
    // Atualização sob pedido (2.2): o pedido vai pelo chat, e a resposta fica na conversa.
    if (ev.target.closest("[data-atualizar]")) {
      ev.preventDefault();
      ev.target.closest("dialog")?.close();
      enviar("verifique e atualize");
    }
  });

  // ---- Banco de linguagem
  const AJUDA_LINGUAGEM = {
    abreviacoes: ["Abreviação (ex.: vc)", "Significado (ex.: você)",
      "Abreviações são expandidas antes de tudo. Ao alterar, a base é reindexada."],
    sinonimos: ["Termo (ex.: automóvel)", "Trocar por (ex.: carro)",
      "Cada sinônimo é trocado pela forma principal (também no plural e nas flexões), então ensinar sobre 'carro' também responde 'automóveis'. Cadeias são seguidas: automóvel → carro → veículo."],
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
    mostrarConflitos(dados, aba);
    mostrarDeAddons(dados, aba);
  }

  // Termos que addons diferentes explicam de jeitos diferentes: ficam sem troca
  // até o dono escolher. Um clique na opção cadastra a escolha como dele.
  function mostrarConflitos(dados, aba) {
    const caixa = $("#conflitos-linguagem");
    const conflitos = (dados.conflitos || {})[aba] || [];
    caixa.hidden = !conflitos.length;
    caixa.innerHTML = "";
    if (!conflitos.length) return;
    caixa.appendChild(criar(`<p>${icone("alerta")} <strong>${conflitos.length} ${conflitos.length === 1 ? "termo tem" : "termos têm"} significados diferentes nos addons.</strong> Enquanto você não escolhe, a palavra fica como foi escrita (melhor não trocar do que trocar pelo sentido errado).</p>`));
    conflitos.forEach((c) => {
      const linha = criar(`<div class="linha-conflito"><span class="termo"></span><span class="seta">→</span><span class="opcoes"></span></div>`);
      $(".termo", linha).textContent = c.termo;
      c.opcoes.forEach((o) => {
        const b = criar(`<button class="chip" type="button"></button>`);
        b.textContent = o.valor;
        b.title = "Vem de: " + o.addons.join(", ") + ". Clique para usar esta.";
        b.addEventListener("click", async () => {
          await api("/api/linguagem/" + aba, { metodo: "POST", corpo: { termo: c.termo, valor: o.valor } });
          avisar(`"${c.termo}" agora significa "${o.valor}".`, "check");
          carregarLinguagem();
        });
        $(".opcoes", linha).appendChild(b);
      });
      caixa.appendChild(linha);
    });
  }

  function mostrarDeAddons(dados, aba) {
    const bloco = $("#ling-addons");
    const itens = (dados.de_addons || {})[aba] || [];
    bloco.hidden = !itens.length;
    if (!itens.length) return;
    const LIMITE = 300;
    $("summary", bloco).textContent = `Vindos dos addons ativos (${itens.length})`;
    const lista = $(".lista-base", bloco);
    lista.innerHTML = "";
    itens.slice(0, LIMITE).forEach((l) => {
      const linha = criar(`<div class="linha-ling"><span class="termo"></span><span class="seta">→</span><span class="valor"></span><span class="origem"></span></div>`);
      $(".termo", linha).textContent = l.termo;
      $(".valor", linha).textContent = l.valor;
      $(".origem", linha).textContent = l.addon;
      lista.appendChild(linha);
    });
    if (itens.length > LIMITE) lista.appendChild(criar(`<p class="ajuda">Mostrando ${LIMITE} de ${itens.length}.</p>`));
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

  /** Monta a lista de configurações de um tipo (parametros | personalizacao). */
  function renderConfig(tipo) {
    const lista = $("#config-" + tipo);
    lista.innerHTML = "";
    Object.values(estado.config).filter((c) => c.tipo === tipo).forEach((c) => {
      const linha = criar(`
        <div class="linha-config">
          <div class="texto"><b></b><small></small></div>
          <div class="controle"></div>
          <div class="origem-config"><span class="etiqueta"></span>
            <button class="acao restaurar" title="Voltar ao valor do addon ou ao padrão">${icone("reset")}<span>Padrão</span></button></div>
        </div>`);
      $("b", linha).textContent = c.titulo;
      $("small", linha).textContent = c.descricao;
      const etiqueta = $(".etiqueta", linha);
      etiqueta.textContent = c.origem === "dono" ? "definido por você"
        : c.origem === "addon" ? "do addon " + (c.addon_nome || c.addon_id) : "padrão";
      etiqueta.classList.toggle("pergunta", c.origem === "dono");
      etiqueta.classList.toggle("addon", c.origem === "addon");
      $(".restaurar", linha).hidden = c.origem !== "dono";

      const controle = $(".controle", linha);
      let campo;
      if (c.opcoes) {
        campo = criar(`<select></select>`);
        (estado.algoritmos[c.opcoes] || []).forEach((a) => {
          const opcao = criar(`<option></option>`);
          opcao.value = a.nome;
          opcao.textContent = a.titulo;
          campo.appendChild(opcao);
        });
      } else if (c.cor) {
        campo = criar(`<input type="color">`);
      } else if (typeof c.padrao === "number") {
        campo = criar(`<input type="range">`);
        campo.min = c.minimo; campo.max = c.maximo; campo.step = c.passo;
        const saida = criar(`<output></output>`);
        saida.textContent = Number(c.valor).toFixed(2);
        campo.addEventListener("input", () => { saida.textContent = Number(campo.value).toFixed(2); });
        controle.appendChild(saida);
      } else {
        campo = criar(`<input type="text">`);
        campo.maxLength = c.chave.endsWith("nome") ? 30 : 200;
      }
      campo.value = c.valor;
      campo.setAttribute("aria-label", c.titulo);
      controle.prepend(campo);

      campo.addEventListener("change", async () => {
        const valor = typeof c.padrao === "number" ? Number(campo.value) : campo.value;
        try { await salvarConfig(c.chave, valor); avisar(`${c.titulo} atualizado.`, "config"); }
        catch (erro) { avisar(erro.message, "alerta"); }
        renderTodasConfig();
      });
      $(".restaurar", linha).addEventListener("click", async () => {
        try { await salvarConfig(c.chave, null); } catch (erro) { avisar(erro.message, "alerta"); }
        renderTodasConfig();
      });
      lista.appendChild(linha);
    });
  }

  function renderTodasConfig() {
    renderConfig("personalizacao");
    renderConfig("parametros");
  }

  async function abrirConfig() {
    await atualizarStatus();
    await carregarConfiguracoes();
    renderTodasConfig();
    const s = estado.status || {};
    const separador = pastaDoBanco().includes("\\") ? "\\" : "/";
    $("#dados-instalacao").innerHTML = `
      <dt>Versão</dt><dd>${esc(String(s.versao || "?"))}</dd>
      <dt>Conhecimentos</dt><dd>${esc(String(s.conhecimentos ?? "?"))}</dd>
      <dt>Conversas</dt><dd>${esc(String(s.conversas ?? "?"))}</dd>
      <dt>Addons</dt><dd>${esc(String(s.addons ?? 0))} (${esc(String(s.conhecimentos_addons ?? 0))} conhecimentos)</dd>
      <dt>Loja oficial</dt><dd><code>${esc(s.loja_oficial || "")}</code>
        <button class="acao destaque" data-abrir-loja>${icone("link")}<span>Abrir</span></button></dd>
      <dt>Memória</dt><dd><code>${esc(s.banco || "")}</code></dd>
      <dt>Cópias de segurança</dt><dd><code>${esc(pastaDoBanco() + separador + "backups")}</code></dd>`;
    aplicarTema(preferencias.ler("tema", "sistema"));
    await mostrarAjuste();
    $("#dlg-config").showModal();
  }

  // ---- Ajuste pessoal da Calibrada (2.6)
  function mostrarAjuste(dados) {
    const preencher = (a) => {
      const r = a.resumo;
      const pct = (x) => `${Math.round((x || 0) * 100)}%`;
      $("#dados-ajuste").innerHTML = `
        <dt>Avaliações</dt><dd>${a.avaliacoes.total} (${a.avaliacoes.certos} certas, ${a.avaliacoes.errados} erradas)</dd>
        <dt>Situação</dt><dd>${a.ativo ? (a.origem === "dono" ? "em uso (o seu)" : `em uso (do addon ${esc(a.origem)})`) : (a.avaliacoes.total < a.minimo
          ? `faltam ${a.minimo - a.avaliacoes.total} avaliações para o primeiro treino` : "pesos oficiais")}</dd>
        ${r ? `<dt>Último treino</dt><dd>${esc(new Date(r.data).toLocaleString())} · ${r.exemplos} exemplos</dd>
        <dt>Nas suas avaliações</dt><dd>certo em 1º lugar: ${pct(r.acerto_antes)} com os pesos oficiais → ${pct(r.acerto_depois)} com o ajuste</dd>
        <dt>Distância do oficial</dt><dd>${esc(String(r.distancia_do_oficial))}</dd>` : ""}
        <dt>Busca em uso</dt><dd>${esc(a.busca_em_uso)}${a.busca_em_uso === "calibrado" ? "" : " (o ajuste só vale na Calibrada)"}</dd>`;
      $("#btn-ajuste-oficial").disabled = a.origem !== "dono";
    };
    if (dados) { preencher(dados); return Promise.resolve(); }
    return api("/api/ajuste").then(preencher).catch(() => {});
  }
  $("#btn-ajuste-treinar").addEventListener("click", async () => {
    try {
      const a = await api("/api/ajuste/treinar", { metodo: "POST" });
      mostrarAjuste(a);
      avisar(a.ativo ? "Ajuste pessoal treinado." : "Ainda não há avaliações suficientes.", a.ativo ? "check" : "info");
    } catch (e) { avisar(e.message, "alerta"); }
  });
  $("#btn-ajuste-oficial").addEventListener("click", async () => {
    try { mostrarAjuste(await api("/api/ajuste", { metodo: "DELETE" })); avisar("De volta aos pesos oficiais."); }
    catch (e) { avisar(e.message, "alerta"); }
  });

  $$("#seg-tema button").forEach((b) => b.addEventListener("click", () => aplicarTema(b.dataset.tema)));

  // ---- Reset da memória
  const PARTES_RESET = ["conhecimentos", "linguagem", "conversas", "addons", "configuracoes"];

  function abrirReset() {
    const s = estado.status || {};
    const separador = pastaDoBanco().includes("\\") ? "\\" : "/";
    $("#reset-info-conhecimentos").textContent = `${s.conhecimentos ?? 0} conhecimento(s) ensinado(s)`;
    $("#reset-info-conversas").textContent = `${s.conversas ?? 0} conversa(s)`;
    $("#reset-info-addons").textContent = `${s.addons ?? 0} addon(s) instalado(s)`;
    $("#reset-pasta-backup").textContent = pastaDoBanco() + separador + "backups";
    $("#reset-confirmacao").value = "";
    PARTES_RESET.forEach((p) => { $("#reset-" + p).checked = true; });
    validarReset();
    $("#dlg-reset").showModal();
    $("#reset-confirmacao").focus();
  }

  function validarReset() {
    const algumaParte = PARTES_RESET.some((p) => $("#reset-" + p).checked);
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
        configuracoes: $("#reset-configuracoes").checked,
        confirmacao: "RESETAR",
      } });
      $("#dlg-reset").close();
      $("#dlg-config").close();
      novaConversa();
      await carregarConversas();
      await atualizarStatus();
      await carregarConfiguracoes();
      await carregarAlgoritmos();
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
      window.Monitor.invalidarModelo();   // addons ou configurações podem ter mudado
      // O endereço da loja vem do servidor (aplicativo/config.py), para existir num lugar só.
      $$(".endereco-loja").forEach((el) => { el.textContent = (s.loja_oficial || "").replace(/^https:\/\//, ""); });
    } catch (e) { $("#status").textContent = "servidor indisponível"; }
  }

  function fecharMenuMobile() { $("#lateral").classList.remove("aberta"); }

  /**
   * "Sinal de vida": avisa o servidor que a interface continua aberta.
   * Quando a janela/aba é fechada, os sinais param e o app de desktop
   * encerra sozinho (veja aprendiz/aplicativo/desktop.py).
   */
  function enviarSinal() {
    fetch("/api/sinal", { method: "POST" }).catch(() => { /* servidor fora do ar */ });
  }

  // =========================================================== REVISÃO DE TEXTO (0.8+)
  let ultimaRevisao = null;

  async function abrirRevisar() {
    const normas = await api("/api/normas");
    const sel = $("#revisar-norma");
    sel.innerHTML = "";
    const auto = criar(`<option value="">Automática (pelas Configurações ou pelo texto)</option>`);
    sel.appendChild(auto);
    normas.forEach((n) => {
      const o = criar(`<option></option>`);
      o.value = n.id;
      o.textContent = `${n.nome} · ${n.ortografia === "1990" ? "Acordo de 1990" : n.ortografia === "1945" ? "ortografia anterior ao Acordo" : "as duas ortografias"}`;
      sel.appendChild(o);
    });
    $("#revisar-ajuda").textContent = normas.length
      ? "Ortografia, gramática e palavras de outras variantes, pela norma do país escolhido."
      : "Nenhum addon de norma está ativo. Instale um dos addons de português da loja oficial (Brasil, Portugal, Angola…).";
    $("#dlg-revisar").showModal();
  }

  /** Mostra o texto com os trechos apontados sublinhados (tudo escapado). */
  function renderRevisao(r) {
    ultimaRevisao = r;
    $("#revisar-resultado").hidden = false;
    const n = r.apontamentos.length;
    $("#revisar-resumo").textContent = `Norma: ${r.norma.nome}. ` +
      (n ? `${n} ${n === 1 ? "ponto" : "pontos"} a revisar.` : "Nada a apontar.");
    let html = "", cursor = 0;
    r.apontamentos.forEach((a, i) => {
      html += esc(r.texto.slice(cursor, a.inicio));
      html += `<mark class="nivel-${esc(a.nivel)}" title="${esc(a.nivel_titulo)}">${esc(r.texto.slice(a.inicio, a.fim))}<sup>${i + 1}</sup></mark>`;
      cursor = a.fim;
    });
    html += esc(r.texto.slice(cursor));
    $("#revisar-marcado").innerHTML = html.replace(/\n/g, "<br>");
    const lista = $("#revisar-lista");
    lista.innerHTML = "";
    r.apontamentos.forEach((a) => {
      const li = criar(`<li><span class="selo nivel-${esc(a.nivel)}"></span> <s></s> <b></b><div class="explicacao-revisao"></div></li>`);
      $(".selo", li).textContent = a.nivel_titulo;
      $("s", li).textContent = a.trecho;
      $("b", li).textContent = a.sugestoes.length ? "→ " + a.sugestoes.join(" ou ") : "";
      $(".explicacao-revisao", li).textContent = a.mensagem;
      lista.appendChild(li);
    });
    $("#btn-copiar-revisado").hidden = r.texto_revisado === r.texto;
  }

  $("#form-revisar").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const r = await api("/api/revisar", { metodo: "POST",
        corpo: { texto: $("#revisar-texto").value, norma: $("#revisar-norma").value || null } });
      renderRevisao(r);
    } catch (erro) { avisar(erro.message, "alerta"); }
  });
  $("#btn-copiar-revisado").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(ultimaRevisao.texto_revisado); avisar("Texto revisado copiado."); }
    catch (e) { avisar("Não foi possível copiar.", "alerta"); }
  });

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
      sel.addEventListener("change", async () => {
        atualizarDica(sel, estado.algoritmos[tipo]);
        try { await salvarConfig(tipo + ".padrao", sel.value); }
        catch (erro) { avisar(erro.message, "alerta"); }
      });
    });

    $("#filtro-conversas").addEventListener("input", renderConversas);
    $("#btn-nova").addEventListener("click", novaConversa);
    $("#btn-ensinar").addEventListener("click", () => { fecharMenuMobile(); abrirEnsinar(); });
    $("#btn-base").addEventListener("click", () => { fecharMenuMobile(); $("#dlg-base").showModal(); carregarBase(); });
    $("#btn-como-funciona").addEventListener("click", abrirComoFunciona);
    $("#btn-addons").addEventListener("click", () => { fecharMenuMobile(); $("#dlg-addons").showModal(); carregarAddons(); });
    $("#btn-linguagem").addEventListener("click", () => { fecharMenuMobile(); $("#dlg-linguagem").showModal(); carregarLinguagem(); });
    $("#btn-revisar").addEventListener("click", () => { fecharMenuMobile(); abrirRevisar(); });
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
    window.Monitor.iniciar({ $, $$, esc, icone, api, criar, preferencias, nomeAlgoritmo });
    ligarEventos();
    atualizarBotaoEnviar();
    try {
      await carregarConfiguracoes();
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
