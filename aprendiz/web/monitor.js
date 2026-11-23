/*
 * Monitor do Aprendiz (2.4): o painel técnico à direita do chat.
 *
 * Mostra o que acontece "por dentro" de cada resposta, para quem estuda IA:
 *
 *   Pipeline     cada etapa AO VIVO (rota /api/chat/fluxo), com tempo e início,
 *                como um gráfico de Gantt; "câmera lenta" espaça as etapas
 *   Busca        candidatos, confiança × limiar e, na busca Calibrada, a conta
 *                inteira: z = viés + Σ peso·sinal, p = σ(z) e a 2ª etapa
 *   Modelo       ficha técnica (/api/modelo): componentes e parâmetros por tipo
 *   Desempenho   tempos e memória das respostas desta sessão
 *   Glossário    os termos técnicos, explicados em dois níveis
 *
 * Dois níveis de leitura: Iniciante (o que cada etapa faz, em palavras
 * simples) e Avançado (nome técnico, fórmulas e os dados brutos em JSON).
 *
 * O app.js chama Monitor.iniciar({...}) com as utilidades dele e depois:
 *   Monitor.comecar(pergunta)      uma pergunta foi enviada
 *   Monitor.etapa(etapa)           chegou uma etapa ao vivo (devolve Promise)
 *   Monitor.mostrar(mensagem)      mostra uma resposta (nova ou do histórico)
 */
(function () {
  "use strict";

  let $, $$, esc, icone, api, criar, preferencias, nomeAlgoritmo;

  const estado = {
    aberto: true,
    nivel: "iniciante",   // "iniciante" | "avancado"
    lento: false,         // câmera lenta: espaça as etapas ao vivo
    aba: "pipeline",
    mensagem: null,       // a mensagem do assistente que está no monitor
    aoVivo: null,         // {pergunta, etapas: [], inicio} enquanto pensa
    candidato: 0,         // candidato escolhido na aba Busca
    sessao: [],           // desempenho desta sessão (últimas respostas)
    modelo: null,         // cache de /api/modelo
    filtroGlossario: "",
  };
  const ATRASO_LENTO = 450; // ms entre etapas na câmera lenta
  let filaLenta = Promise.resolve();

  // ================================================================ CATÁLOGOS
  /** O que cada etapa faz: em palavras simples e com o nome técnico. */
  const ETAPAS = [
    ["Normalização", "Prepara o texto: minúsculas, sem acento, corrige a digitação, troca sinônimos, tira as palavras vazias e reduz cada palavra à raiz.",
      "Pré-processamento: tokenização, correção por Levenshtein, stopwords e stemming (RSLP)", ["token", "stopword", "radical", "levenshtein"]],
    ["Atualização", "Reconheceu um pedido para procurar atualizações.", "Comando por expressão regular", ["regex"]],
    ["Ensino", "Reconheceu um pedido para aprender algo novo.", "Ensino explícito por expressões regulares", ["regex"]],
    ["Revisão", "Revisou o texto pela norma do português escolhida.", "Verificação ortográfica (busca binária no vocabulário) e regras de gramática", ["busca-binaria"]],
    ["Dicionário", "Procurou a palavra nos dicionários dos addons.", "Consulta a verbetes por igualdade de radicais", ["radical"]],
    ["Interpretação", "Descobre a intenção da frase: cumprimento, agradecimento, pergunta…", "Classificação de intenção: Naive Bayes multinomial com suavização de Laplace e softmax", ["naive-bayes", "laplace", "softmax"]],
    ["Resposta social", "Respondeu a um cumprimento ou agradecimento com uma frase pronta.", "Resposta por intenção (classe vencedora com margem)", ["naive-bayes"]],
    ["Compreensão", "Entende o tipo de pergunta (definição, comparação, pedido…) e qual é o assunto.", "Análise de tipo de pergunta por padrões e léxico", ["lema"]],
    ["Assunto conhecido", "Confere se a frase fala de algo que a base conhece.", "Checagem de vocabulário da base", []],
    ["Diálogo", "Lê a conversa: \"não entendi\", \"e em Portugal?\", desabafos, pedidos de opinião.", "Atos de fala e resolução de contexto", ["ato-de-fala"]],
    ["Padrão de frase", "Reconhece estruturas como \"quantos * cada *\" e procura pelo conceito.", "Casamento de moldes com lacunas (templates)", ["template"]],
    ["Busca por sentido", "Sem as palavras exatas, tentou palavras de sentido parecido.", "Expansão de consulta por embeddings (similaridade do cosseno)", ["embedding", "cosseno"]],
    ["Busca", "Procura na base os conhecimentos que respondem e dá uma nota a cada um.", "Recuperação de informação (ranking) com limiar de confiança", ["bm25", "tfidf", "levenshtein", "rrf", "regressao-logistica", "limiar"]],
    ["Panorama", "Juntou tudo o que sabe sobre o assunto numa lista.", "Recuperação de vários documentos por assunto", []],
    ["Pedido composto", "Dividiu a frase em várias perguntas e respondeu cada uma.", "Segmentação da consulta", []],
    ["Fora de alcance", "Percebeu um pedido que um assistente offline não atende.", "Classificação de escopo por léxico", []],
    ["Recomendação de addon", "Procurou na loja um addon que trate do assunto.", "Cobertura ponderada entre a pergunta e o catálogo (com vetores)", ["embedding"]],
    ["Modo estrito", "Nada passou do limiar: diz que não sabe, em vez de inventar.", "Rejeição abaixo do limiar (precisão × revocação)", ["limiar", "precisao-revocacao"]],
    ["Teia de porquês", "Seguiu os porquês do conhecimento achado até a base dos conceitos.", "Busca em largura (BFS) num grafo dirigido, com profundidade máxima", ["bfs", "grafo"]],
    ["Resposta", "Monta o texto final a partir do que foi aceito.", "Geração de resposta: direta, extrativa (TextRank) ou trabalhada (teia)", ["textrank"]],
  ];

  function infoEtapa(nome) {
    const achado = ETAPAS.find(([prefixo]) => nome === prefixo || nome.startsWith(prefixo + " ·") || nome.startsWith(prefixo));
    return achado ? { simples: achado[1], tecnica: achado[2], termos: achado[3] } : { simples: "", tecnica: "", termos: [] };
  }

  /** Os sinais da busca Calibrada, em palavras simples. */
  const SINAIS = {
    bm25_conf: "palavras da pergunta presentes (BM25)",
    bm25_rank: "posição na lista do BM25",
    tfidf_conf: "semelhança dos vetores TF-IDF (cosseno)",
    tfidf_rank: "posição na lista do TF-IDF",
    fuzzy_conf: "letras parecidas (Fuzzy)",
    fuzzy_rank: "posição na lista do Fuzzy",
    cobertura_idf: "palavras raras da pergunta presentes",
    pares: "pares de palavras vizinhas da pergunta também vizinhos no texto",
    termos: "tamanho da pergunta",
    assunto: "quanto bate no assunto declarado",
    palavras_assunto: "quantas palavras batem no assunto",
    palavra_forte: "bate numa palavra rara do assunto",
    melhor_assunto: "é o que mais bate no assunto",
    cobre_assunto: "fala do assunto da pergunta",
    pergunta_exata: "pergunta igual a uma variação",
    define: "é a definição pedida (\"o que é X?\")",
    consenso_hibrido: "o Híbrido aceitaria",
    regras_bm25: "as regras do BM25 aceitariam",
  };

  /** Glossário: [id, termo, nível iniciante, detalhe técnico]. */
  const GLOSSARIO = [
    ["token", "Token", "Cada pedaço do texto depois de cortado nas palavras.", "Tokenização: dividir a string em unidades (aqui, palavras e números), depois de normalizar caixa e acentos."],
    ["stopword", "Stopword (palavra vazia)", "Palavras muito comuns, como \"o\", \"de\", \"que\", que quase não dizem o assunto.", "Removidas antes da busca para reduzir ruído; a lista vem do banco de linguagem e dos addons."],
    ["radical", "Radical (stemming)", "A raiz da palavra: \"ensinar\", \"ensinei\" e \"ensinando\" viram \"ensin\".", "Stemming por regras de sufixo (RSLP simplificado). Não é linguística perfeita: o importante é ser consistente entre o que se ensina e o que se pergunta."],
    ["lema", "Lema", "A forma de dicionário: \"fui\" e \"era\" viram \"ser\".", "Lematização por tabela (addon de compreensão); resolve formas irregulares que o stemming não junta."],
    ["levenshtein", "Distância de Levenshtein", "Quantas letras é preciso trocar, tirar ou pôr para um texto virar o outro.", "Distância de edição; a RapidFuzz a converte em semelhança 0–100. WRatio combina várias estratégias (ordem, tamanhos)."],
    ["regex", "Expressão regular", "Um molde de texto que reconhece frases como \"aprenda que…\".", "Linguagem de padrões (módulo re do Python)."],
    ["busca-binaria", "Busca binária", "Procurar numa lista ordenada partindo sempre do meio, como num dicionário de papel.", "O(log n): o vocabulário das normas fica num bloco de bytes ordenado."],
    ["naive-bayes", "Naive Bayes", "Calcula qual intenção tem mais chance de ter \"gerado\" as palavras da frase.", "P(c|w) ∝ P(c)·Π P(w|c), supondo palavras independentes; somam-se logaritmos para evitar underflow."],
    ["laplace", "Suavização de Laplace", "Soma 1 a cada contagem, para uma palavra nova não zerar a probabilidade.", "P(w|c) = (n(w,c) + 1) / (N(c) + |V|)."],
    ["softmax", "Softmax", "Transforma notas em porcentagens que somam 100%.", "softmax(x)_i = e^(x_i − max) / Σ e^(x_j − max)."],
    ["ato-de-fala", "Ato de fala", "O que a frase FAZ: perguntar, agradecer, pedir, reclamar.", "Classificação pragmática do enunciado, além do conteúdo."],
    ["template", "Molde (template)", "Frases com lacunas, como \"quantos * cada *\", que dizem o conceito.", "Casamento de padrões com curingas; as lacunas viram exemplo e saem da busca."],
    ["embedding", "Vetor de palavra (embedding)", "Uma lista de números que representa o sentido da palavra; sentidos parecidos, números parecidos.", "Embeddings densos de 100 dimensões, quantizados em int8; vizinhança pelo cosseno."],
    ["cosseno", "Similaridade do cosseno", "Compara a DIREÇÃO de dois vetores: 1 = mesmo sentido, 0 = nada a ver.", "cos(a,b) = a·b / (|a|·|b|); com vetores normalizados, é só o produto escalar."],
    ["bm25", "BM25", "Nota de relevância dos buscadores: palavras da pergunta no texto, valendo mais as raras.", "Σ IDF(q)·f·(k1+1) / (f + k1·(1 − b + b·|D|/avgdl)), com k1 = 1,2 e b = 0,75, calculada pelo FTS5 do SQLite."],
    ["tfidf", "TF-IDF", "Peso de cada palavra num texto: frequente nele e rara nos outros.", "w = tf·idf, idf = log((N+1)/(df+1)) + 1; vetores normalizados (L2) comparados pelo cosseno."],
    ["idf", "IDF", "Quanto uma palavra é rara na base; raras valem mais.", "Inverse document frequency: log((N+1)/(df+1)) + 1."],
    ["rrf", "Reciprocal Rank Fusion", "Junta listas de algoritmos diferentes olhando só a posição de cada item.", "RRF(d) = Σ 1/(k + posição_i(d)), k = 60."],
    ["regressao-logistica", "Regressão logística", "Soma sinais com pesos e transforma o total numa chance de 0 a 1.", "p = σ(w·x + b), treinada por máxima verossimilhança com regularização L2 (scikit-learn)."],
    ["sigmoide", "Sigmoide", "A curva em S que leva qualquer número para entre 0 e 1.", "σ(z) = 1 / (1 + e^(−z)); σ(0) = 0,5."],
    ["logito", "Logito", "A chance escrita na escala da soma: 0 vira 0,5; positivo, mais que 0,5.", "logit(p) = log(p / (1 − p)), o inverso da sigmoide."],
    ["padronizacao", "Padronização (z-score)", "Põe sinais de escalas diferentes na mesma régua.", "z = (x − média) / desvio, com média e desvio do treino."],
    ["regularizacao", "Regularização", "Um freio para o modelo não decorar o treino.", "Penalidade L2 sobre os pesos; C é o inverso da força, escolhido por validação cruzada."],
    ["validacao-cruzada", "Validação cruzada", "Treinar em partes e testar na parte que ficou de fora, várias vezes.", "GroupKFold (5 dobras), agrupando pela pergunta para não vazar candidatos."],
    ["colinearidade", "Colinearidade", "Quando dois sinais medem quase a mesma coisa, o modelo divide o peso entre eles.", "Pesos individuais deixam de ser interpretáveis; a soma continua estável."],
    ["calibracao", "Calibração", "Uma chance de 70% deve acertar cerca de 70% das vezes.", "A 2ª etapa da Calibrada recalibra a nota do 1º lugar usando a distância para o 2º."],
    ["limiar", "Limiar", "A nota mínima para aceitar uma resposta.", "Corte de decisão; na Calibrada, 0,25 sai do custo: responder vale 2p − 1, recusar −0,5."],
    ["precisao-revocacao", "Precisão × revocação", "Inventar menos ou recusar menos: subir o limiar ajuda um e piora o outro.", "Precisão = acertos / respondidas; revocação = acertos / respondíveis."],
    ["textrank", "TextRank", "Escolhe as frases que mais se parecem com as outras: as centrais do texto.", "PageRank sobre o grafo de frases: nota(i) = (1 − d) + d·Σ sim(i,j)/Σ_k sim(j,k)·nota(j), d = 0,85."],
    ["bfs", "Busca em largura (BFS)", "Visita primeiro os vizinhos mais próximos, depois os vizinhos deles.", "Travessia nível a nível com fila, limitada em profundidade e passos."],
    ["grafo", "Grafo", "Pontos (conceitos) ligados por setas (porquês).", "G = (V, E) dirigido; os nós são fragmentos, as arestas são relações (porque, regra, definição…)."],
    ["parametro", "Parâmetro", "Um número que o modelo usa para decidir.", "Aprendido (treino com rótulos), estatística (da base), pré-treinado (veio pronto) ou hiperparâmetro (escolhido por uma pessoa)."],
    ["hiperparametro", "Hiperparâmetro", "Um ajuste escolhido por uma pessoa, não aprendido.", "Ex.: k1 e b do BM25, k do RRF, limiares, profundidade da teia."],
    ["ndjson", "NDJSON (fluxo)", "Um JSON por linha, enviado assim que fica pronto: é assim que o Monitor vê o pipeline ao vivo.", "application/x-ndjson via StreamingResponse; produtor-consumidor com queue.Queue."],
  ];

  // ================================================================ UTILIDADES
  const avancado = () => estado.nivel === "avancado";
  const num = (x, casas) => (typeof x === "number" ? x.toLocaleString("pt-BR", { maximumFractionDigits: casas == null ? 3 : casas }) : esc(String(x)));
  const termo = (id, texto) => `<button type="button" class="termo-mon" data-termo="${esc(id)}">${esc(texto)}</button>`;
  const json = (dados) => `<details class="bruto"><summary>Dados brutos (JSON)</summary><pre>${esc(JSON.stringify(dados, null, 2))}</pre></details>`;
  const espera = (ms) => new Promise((ok) => setTimeout(ok, ms));

  function fichas(lista) {
    if (!lista || !lista.length) return `<span class="rotulo">—</span>`;
    return `<span class="fichas">${lista.map((t) => `<span class="ficha">${esc(String(t))}</span>`).join("")}</span>`;
  }
  const mapaFichas = (mapa) => fichas(Object.entries(mapa || {}).map(([de, para]) => `${de} → ${para}`));

  function barra(valor, limiar, aceito) {
    const pct = Math.max(0, Math.min(1, valor)) * 100;
    const marca = limiar != null ? `<span class="limiar" style="left:${Math.min(100, limiar * 100)}%" title="limiar"></span>` : "";
    return `<div class="barra ${aceito ? "aceito" : ""}"><i style="width:${pct}%"></i>${marca}</div>`;
  }

  // ================================================================ ETAPAS
  /** O corpo de uma etapa: os dados de cada uma, mostrados do jeito que fazem sentido. */
  function corpoEtapa(etapa) {
    const d = etapa.dados || {};
    if (etapa.nome === "Normalização") {
      return `
        <div class="linha-dado"><span class="rotulo">Normalizado:</span><code>${esc(d.normalizado || "")}</code></div>
        <div class="linha-dado"><span class="rotulo">Abreviações:</span>${mapaFichas(d.expansoes)}</div>
        <div class="linha-dado"><span class="rotulo">Correções:</span>${mapaFichas(d.correcoes)}</div>
        <div class="linha-dado"><span class="rotulo">Sinônimos:</span>${mapaFichas(d.sinonimos)}</div>
        ${d.expressoes && Object.keys(d.expressoes).length ? `<div class="linha-dado"><span class="rotulo">Expressões:</span>${mapaFichas(d.expressoes)}</div>` : ""}
        ${d.lemas && Object.keys(d.lemas).length ? `<div class="linha-dado"><span class="rotulo">Lemas:</span>${mapaFichas(d.lemas)}</div>` : ""}
        <div class="linha-dado"><span class="rotulo">${avancado() ? "Tokens de conteúdo" : "Palavras-chave"}:</span>${fichas(d.conteudo)}</div>
        <div class="linha-dado"><span class="rotulo">Radicais:</span>${fichas(d.radicais)}</div>`;
    }
    if (etapa.nome === "Interpretação") {
      const linhas = (d.intencoes || []).map((i) => `
        <tr><td>${esc(i.intencao)}${i.exata ? " (frase exata)" : ""}</td>
        <td style="width:40%">${barra(i.probabilidade)}</td>
        <td class="num">${(i.probabilidade * 100).toFixed(1)}%</td></tr>`).join("");
      return `<table class="tabela"><tr><th>Intenção</th><th></th><th>${avancado() ? "P(c|w)" : "Chance"}</th></tr>${linhas}</table>
        <div class="linha-dado"><span class="rotulo">Entidades:</span>${fichas((d.entidades || []).map((e) => `${e.tipo}: ${e.valor}`))}</div>`;
    }
    if (d.candidatos) {
      const linhas = d.candidatos.slice(0, 5).map((c) => `
        <tr><td>${c.aceito ? icone("check", "ok") : icone("x", "nao")} ${esc(c.titulo)}</td>
        <td style="width:30%">${barra(c.confianca, d.limiar, c.aceito)}</td>
        <td class="num">${num(c.confianca, 3)}</td></tr>`).join("");
      return `<div class="linha-dado"><span class="rotulo">Limiar:</span>${num(d.limiar)}
          <span class="rotulo">· detalhes na aba Busca</span></div>` +
        (linhas ? `<table class="tabela"><tr><th>Candidato</th><th>Confiança</th><th></th></tr>${linhas}</table>`
          : `<div class="rotulo">Nenhum candidato encontrado.</div>`);
    }
    if (d.frases) {
      const linhas = d.frases.map((f) => `
        <tr><td>${esc(f.texto)}</td><td class="num">${f.relevancia}</td>
        <td class="num">${f.centralidade}</td><td class="num"><b>${f.nota}</b></td></tr>`).join("");
      return `<table class="tabela"><tr><th>Frase</th><th>Relev.</th><th>${avancado() ? "TextRank" : "Central."}</th><th>Nota</th></tr>${linhas}</table>`;
    }
    return Object.entries(d).map(([k, v]) =>
      `<div class="linha-dado"><span class="rotulo">${esc(k)}:</span>${Array.isArray(v) ? fichas(v)
        : esc(typeof v === "object" && v !== null ? JSON.stringify(v) : String(v))}</div>`).join("") || `<span class="rotulo">Sem dados.</span>`;
  }

  /** Uma linha da linha do tempo (Pipeline), com a barra de Gantt. */
  function linhaEtapa(etapa, indice, total) {
    const info = infoEtapa(etapa.nome);
    const t = Math.max(total || 0, 0.01);
    const inicio = Math.min(100, ((etapa.inicio_ms || 0) / t) * 100);
    const largura = Math.max(0.8, Math.min(100 - inicio, (etapa.ms / t) * 100));
    const subtitulo = avancado()
      ? `<div class="etapa-tecnica">${esc(info.tecnica)} ${info.termos.map((id) => termo(id, nomeTermo(id))).join(" ")}</div>`
      : (info.simples ? `<div class="etapa-simples">${esc(info.simples)}</div>` : "");
    return `<details class="etapa-mon" data-indice="${indice}">
      <summary>
        <span class="num">${indice + 1}</span>
        <span class="etapa-nome">${esc(etapa.nome)}</span>
        <span class="ms">${num(etapa.ms, 2)} ms</span>
        <span class="gantt"><i style="left:${inicio}%;width:${largura}%"></i></span>
      </summary>
      ${subtitulo}
      <div class="etapa-corpo">${corpoEtapa(etapa)}${avancado() ? json(etapa.dados) : ""}</div>
    </details>`;
  }

  function nomeTermo(id) {
    const t = GLOSSARIO.find((g) => g[0] === id);
    return t ? t[1] : id;
  }

  // ================================================================ ABAS
  function abaPipeline() {
    const vivo = estado.aoVivo;
    if (vivo) {
      const ultimo = vivo.etapas[vivo.etapas.length - 1];
      const total = ultimo ? (ultimo.inicio_ms || 0) + ultimo.ms : 1;
      return `<div class="mon-cabeca"><div class="mon-pergunta">${esc(vivo.pergunta)}</div>
          <div class="mon-meta"><span class="pulso"></span> pensando… ${vivo.etapas.length} ${vivo.etapas.length === 1 ? "etapa" : "etapas"}</div></div>
        <div class="linha-tempo">${vivo.etapas.map((e, i) => linhaEtapa(e, i, total)).join("")}</div>`;
    }
    const msg = estado.mensagem;
    const exp = msg && msg.meta && msg.meta.explicacao;
    if (!exp) return vazio("Envie uma pergunta para ver o pipeline ao vivo.", "Cada etapa aparece assim que termina, com o tempo que levou.");
    const etapas = exp.etapas || [];
    const total = exp.total_ms || etapas.reduce((s, e) => s + e.ms, 0);
    const pergunta = (msg.meta && msg.meta.pergunta) || "";
    const memoria = exp.memoria_mb != null ? ` · ${num(exp.memoria_mb, 1)} MB` : "";
    const resumo = avancado()
      ? `${etapas.length} etapas · ${num(total, 2)} ms${memoria} · busca <code>${esc(exp.algoritmo_busca)}</code> · resposta <code>${esc(exp.algoritmo_resposta)}</code>`
      : `${etapas.length} etapas em ${num(total, 1)} milissegundos · ${esc(nomeAlgoritmo("busca", exp.algoritmo_busca))}`;
    return `<div class="mon-cabeca"><div class="mon-pergunta">${esc(pergunta)}</div><div class="mon-meta">${resumo}</div></div>
      ${avancado() ? "" : `<p class="mon-dica">Clique numa etapa para ver os dados. A barra mostra quando ela começou e quanto durou.</p>`}
      <div class="linha-tempo">${etapas.map((e, i) => linhaEtapa(e, i, total)).join("")}</div>
      ${avancado() ? json(exp) : ""}`;
  }

  function etapasDeBusca() {
    const exp = estado.mensagem && estado.mensagem.meta && estado.mensagem.meta.explicacao;
    return exp ? (exp.etapas || []).filter((e) => e.dados && e.dados.candidatos) : [];
  }

  function abaBusca() {
    const buscas = etapasDeBusca();
    if (!buscas.length) return vazio("Esta resposta não passou pela busca.", "Cumprimentos, ensino e dicionário são resolvidos antes dela.");
    const etapa = buscas[buscas.length - 1];   // a busca que decidiu a resposta
    const d = etapa.dados;
    const exp = estado.mensagem.meta.explicacao;
    const cands = d.candidatos || [];
    const i = Math.min(estado.candidato, Math.max(0, cands.length - 1));
    const linhas = cands.map((c, k) => `
      <tr class="clicavel ${k === i ? "escolhido" : ""}" data-candidato="${k}">
        <td>${c.aceito ? icone("check", "ok") : icone("x", "nao")} ${esc(c.titulo)}</td>
        <td style="width:28%">${barra(c.confianca, d.limiar, c.aceito)}</td>
        <td class="num">${num(c.confianca, 3)}</td>
        ${avancado() ? `<td class="num" title="pontuação bruta">${num(c.pontuacao, 4)}</td>` : ""}</tr>`).join("");
    const intro = avancado()
      ? `<div class="mon-meta">${esc(etapa.nome)} · limiar <code>${num(d.limiar)}</code> · ${cands.length} candidatos · ${num(etapa.ms, 2)} ms</div>`
      : `<p class="mon-dica">Cada candidato ganhou uma <b>confiança</b>. Só passa quem chega ao <b>limiar</b> (a marca laranja). Clique num candidato para ver de onde veio a nota.</p>`;
    const escolhido = cands[i];
    return `<div class="mon-cabeca"><div class="mon-pergunta">${esc(nomeAlgoritmo("busca", exp.algoritmo_busca))}</div>${intro}</div>
      ${cands.length ? `<table class="tabela"><tr><th>Candidato</th><th>Confiança</th><th></th>${avancado() ? "<th>Bruta</th>" : ""}</tr>${linhas}</table>` : `<div class="rotulo">Nenhum candidato.</div>`}
      ${escolhido ? detalheCandidato(escolhido, d.limiar, i === 0) : ""}`;
  }

  /** A conta por trás da nota de um candidato. */
  function detalheCandidato(c, limiar, primeiro) {
    const det = c.detalhes || {};
    let html = `<h3 class="mon-sub">${esc(c.titulo)}</h3>`;
    if (det.contribuicoes) {
      const partes = Object.entries(det.contribuicoes).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
      const maior = Math.max(0.01, ...partes.map(([, v]) => Math.abs(v)));
      const barras = partes.map(([nome, v]) => {
        const larg = (Math.abs(v) / maior) * 50;
        const rotulo = avancado() ? `<code>${esc(nome)}</code> <span class="rotulo">= ${num(det.sinais[nome], 3)}</span>` : esc(SINAIS[nome] || nome);
        return `<div class="contrib"><span class="contrib-nome">${rotulo}</span>
          <span class="contrib-barra"><i class="${v >= 0 ? "pos" : "neg"}" style="${v >= 0 ? "left:50%" : `left:${50 - larg}%`};width:${larg}%"></i></span>
          <span class="num">${v >= 0 ? "+" : ""}${num(v, 3)}</span></div>`;
      }).join("");
      const conta = avancado()
        ? `<div class="formula">z = viés + Σ peso·(x − média)/desvio = ${num(det.vies, 3)} ${partes.length ? "+ (" + num(partes.reduce((s, [, v]) => s + v, 0), 3) + ")" : ""} = <b>${num(det.z, 3)}</b><br>
             p = σ(z) = 1 / (1 + e<sup>−z</sup>) = <b>${num(det.chance, 4)}</b> ${termo("sigmoide", "sigmoide")} ${termo("regressao-logistica", "regressão logística")}</div>`
        : `<p class="mon-dica">Cada sinal empurra a nota para cima (verde) ou para baixo (vermelho). Somados, viram a <b>chance</b> deste candidato ser a resposta: <b>${num(det.chance * 100, 1)}%</b>.</p>`;
      html += conta + `<div class="contribs">${barras}</div>`;
      if (primeiro && det.decisao) {
        html += avancado()
          ? `<div class="formula">2ª etapa ${termo("calibracao", "calibração")}: nota_do_primeiro = ${num(det.decisao.nota_do_primeiro, 3)} ${termo("logito", "logito")},
               distancia_do_segundo = ${num(det.decisao.distancia_do_segundo, 3)}${Object.entries(det.decisao)
                 .filter(([k]) => k.startsWith("topo_")).map(([k, v]) => `, ${esc(k)} = ${num(v, 3)}`).join("")} → P(1º certo) = <b>${num(det.chance_de_estar_certo, 4)}</b>
               ${det.chance_de_estar_certo >= limiar ? "≥" : "<"} limiar ${num(limiar)}</div>`
          : `<p class="mon-dica">Depois, a <b>2ª etapa</b> olha quanto ele ficou à frente do 2º lugar: a chance de esta resposta estar certa é <b>${num(det.chance_de_estar_certo * 100, 1)}%</b>${det.chance_de_estar_certo >= limiar ? ", acima do limiar: respondeu." : ", abaixo do limiar: não respondeu."}</p>`;
      }
      return html;
    }
    if (det.algoritmos) {
      const linhas = Object.entries(det.algoritmos).map(([nome, a]) =>
        `<tr><td>${esc(nome)}</td><td class="num">${a.posicao}º</td><td class="num">${num(a.confianca, 3)}</td><td class="num">1/(60+${a.posicao}) = ${num(1 / (60 + a.posicao), 5)}</td></tr>`).join("");
      html += `<p class="mon-dica">${avancado() ? `${termo("rrf", "RRF")}: soma de 1/(k + posição) em cada lista; aceitar exige consenso.` : "O Híbrido soma a posição do candidato em cada algoritmo e só aceita com consenso."}</p>
        <table class="tabela"><tr><th>Algoritmo</th><th>Posição</th><th>Confiança</th><th>Parcela RRF</th></tr>${linhas}</table>
        <div class="linha-dado"><span class="rotulo">Consenso:</span>${esc(det.consenso || "—")}</div>`;
    } else {
      html += Object.entries(det).map(([k, v]) => `<div class="linha-dado"><span class="rotulo">${esc(k)}:</span>${esc(typeof v === "object" ? JSON.stringify(v) : String(v))}</div>`).join("");
    }
    return html + (avancado() ? json(det) : "");
  }

  async function abaModelo(corpo) {
    if (!estado.modelo) {
      corpo.innerHTML = `<div class="rotulo">Carregando a ficha do modelo…</div>`;
      try { estado.modelo = await api("/api/modelo"); } catch (e) { corpo.innerHTML = vazio("Não foi possível ler a ficha.", e.message); return; }
    }
    const m = estado.modelo;
    const tipos = [["aprendido", "Aprendidos", "ajustados por treino com exemplos rotulados"],
      ["estatística", "Estatísticas", "calculados da base, sem rótulos"],
      ["pré-treinado", "Pré-treinados", "vieram prontos nos addons"],
      ["hiperparâmetro", "Hiperparâmetros", "escolhidos por uma pessoa"]];
    const total = m.total_parametros || 1;
    const pilha = tipos.map(([t]) => `<i class="tipo-${t.replace(/[^a-z]/g, "")}" style="width:${((m.por_tipo[t] || 0) / total) * 100}%" title="${esc(t)}"></i>`).join("");
    const legenda = tipos.map(([t, rotulo, desc]) => `<div class="legenda"><span class="ponto tipo-${t.replace(/[^a-z]/g, "")}"></span>
      <b>${rotulo}</b> <span class="num">${num(m.por_tipo[t] || 0, 0)}</span>${avancado() ? "" : `<span class="legenda-desc">${desc}</span>`}</div>`).join("");
    const linhas = m.componentes.map((c, k) => `
      <details class="componente">
        <summary><span class="ponto tipo-${c.tipo.replace(/[^a-z]/g, "")}"></span><span class="comp-nome">${esc(c.nome)}</span>
          <span class="num">${num(c.parametros, 0)}</span></summary>
        <div class="comp-corpo"><div>${esc(avancado() ? c.tecnica : c.descricao)}</div>
          ${avancado() ? `<div class="rotulo">${esc(c.descricao)}</div>` : ""}
          ${detalhesComponente(c.detalhes)}</div>
      </details>`).join("");
    const t = m.treino_calibrado || {};
    const teste = t.teste ? Object.entries(t.teste).map(([nome, r]) =>
      `<tr><td>${esc(nome)}</td><td class="num">${num(r.acerto * 100, 1)}%</td><td class="num">${num(r.errou * 100, 1)}%</td><td class="num">${num(r.recusou * 100, 1)}%</td><td class="num">${num(r.inventou * 100, 1)}%</td></tr>`).join("") : "";
    const amb = m.ambiente || {};
    corpo.innerHTML = `
      <div class="mon-cabeca"><div class="mon-total">${num(m.total_parametros, 0)}</div>
        <div class="mon-meta">${termo("parametro", "parâmetros")} no total, com os addons ativos</div></div>
      <div class="pilha">${pilha}</div>${legenda}
      ${avancado() ? "" : `<p class="mon-dica">Um modelo de linguagem pequeno tem centenas de milhões de parâmetros. Aqui, quase tudo são vetores de palavras prontos; a parte que <b>aprende</b> com exemplos é pequena, por isso roda em qualquer máquina.</p>`}
      <h3 class="mon-sub">Componentes</h3>${linhas}
      ${teste ? `<h3 class="mon-sub">Treino da busca Calibrada</h3>
        <div class="mon-meta">${esc(t.data || "")} · ${num(t.perguntas_treino || 0, 0)} perguntas de treino · ${num(t.perguntas_teste || 0, 0)} de teste · app ${esc(t.versao_app || "")}</div>
        <table class="tabela"><tr><th>Busca</th><th>Acertou</th><th>Errou</th><th>Recusou</th><th>Inventou</th></tr>${teste}</table>` : ""}
      <h3 class="mon-sub">Ambiente</h3>
      <div class="linha-dado"><span class="rotulo">Aprendiz</span>${esc(amb.aprendiz || "")} <span class="rotulo">· Python</span>${esc(amb.python || "")} <span class="rotulo">· SQLite</span>${esc(amb.sqlite || "")}</div>
      <div class="linha-dado"><span class="rotulo">Sistema</span>${esc(amb.sistema || "")} <span class="rotulo">· CPUs</span>${esc(String(amb.processadores || "?"))} <span class="rotulo">· memória</span>${amb.memoria_mb != null ? num(amb.memoria_mb, 1) + " MB" : "—"}</div>
      <div class="linha-dado"><span class="rotulo">Base</span>${Object.entries(m.base || {}).map(([k, v]) => `${esc(k)}: ${num(v, 0)}`).join(" · ")}</div>
      <button type="button" class="acao" id="mon-recarregar">${icone("reset")}<span>Recarregar ficha</span></button>
      ${avancado() ? json(m) : ""}`;
    $("#mon-recarregar", corpo).addEventListener("click", () => { estado.modelo = null; desenhar(); });
  }

  function detalhesComponente(det) {
    return Object.entries(det || {}).map(([k, v]) => {
      if (v && typeof v === "object" && !Array.isArray(v)) {
        const itens = Object.entries(v).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
        const maior = Math.max(0.01, ...itens.map(([, x]) => Math.abs(Number(x) || 0)));
        return `<div class="rotulo">${esc(k)}</div><div class="contribs">${itens.map(([n, x]) =>
          `<div class="contrib"><span class="contrib-nome">${avancado() ? `<code>${esc(n)}</code>` : esc(SINAIS[n] || n)}</span>
            <span class="contrib-barra"><i class="${x >= 0 ? "pos" : "neg"}" style="${x >= 0 ? "left:50%" : `left:${50 - (Math.abs(x) / maior) * 50}%`};width:${(Math.abs(x) / maior) * 50}%"></i></span>
            <span class="num">${num(x, 3)}</span></div>`).join("")}</div>`;
      }
      return `<div class="linha-dado"><span class="rotulo">${esc(k)}:</span>${Array.isArray(v) ? fichas(v) : esc(typeof v === "number" ? num(v, 5) : String(v))}</div>`;
    }).join("");
  }

  function abaDesempenho() {
    const s = estado.sessao;
    if (!s.length) return vazio("Nenhuma resposta nesta sessão ainda.", "Os tempos e a memória de cada resposta aparecem aqui.");
    const tempos = s.map((r) => r.total).sort((a, b) => a - b);
    const media = tempos.reduce((a, b) => a + b, 0) / tempos.length;
    const p90 = tempos[Math.min(tempos.length - 1, Math.floor(tempos.length * 0.9))];
    const porEtapa = {};
    s.forEach((r) => r.etapas.forEach((e) => {
      const nome = e.nome.split(" · ")[0];
      (porEtapa[nome] = porEtapa[nome] || []).push(e.ms);
    }));
    const medias = Object.entries(porEtapa).map(([n, v]) => [n, v.reduce((a, b) => a + b, 0) / v.length, v.length])
      .sort((a, b) => b[1] - a[1]);
    const maior = Math.max(0.01, ...medias.map((m) => m[1]));
    const linhasEtapa = medias.map(([n, m, q]) => `<tr><td>${esc(n)}</td><td style="width:40%"><div class="barra"><i style="width:${(m / maior) * 100}%"></i></div></td>
      <td class="num">${num(m, 2)} ms</td>${avancado() ? `<td class="num">n=${q}</td>` : ""}</tr>`).join("");
    const linhasResp = s.slice().reverse().map((r) => `<tr><td>${esc(r.pergunta.slice(0, 40))}</td><td>${esc(r.busca)}</td>
      <td class="num">${num(r.total, 1)} ms</td><td class="num">${r.memoria != null ? num(r.memoria, 1) + " MB" : "—"}</td></tr>`).join("");
    const mem = s[s.length - 1].memoria;
    return `<div class="mon-cabeca"><div class="numeros">
        <div><b>${num(media, 1)}</b><span>ms em média</span></div>
        <div><b>${s.length >= 5 ? num(p90, 1) : "—"}</b><span>${avancado() ? "p90 (ms)" : "ms em 90% das vezes"}</span></div>
        <div><b>${mem != null ? num(mem, 0) : "—"}</b><span>MB de memória</span></div></div></div>
      ${avancado() ? "" : `<p class="mon-dica">Quanto tempo cada etapa leva, em média, nesta sessão. As mais caras são as primeiras da lista: é onde vale otimizar.</p>`}
      <h3 class="mon-sub">Tempo médio por etapa</h3><table class="tabela">${linhasEtapa}</table>
      <h3 class="mon-sub">Respostas (${s.length})</h3>
      <table class="tabela"><tr><th>Pergunta</th><th>Busca</th><th>Tempo</th><th>Memória</th></tr>${linhasResp}</table>`;
  }

  function abaGlossario() {
    const f = estado.filtroGlossario.toLowerCase();
    const itens = GLOSSARIO.filter(([id, nome, simples, tecnico]) =>
      !f || (nome + " " + simples + " " + tecnico + " " + id).toLowerCase().includes(f));
    return `<input type="search" id="mon-filtro" placeholder="Procurar termo…" value="${esc(estado.filtroGlossario)}">
      <div class="glossario">${itens.map(([id, nome, simples, tecnico]) => `
        <div class="verbete-mon" id="termo-${esc(id)}"><b>${esc(nome)}</b><div>${esc(simples)}</div>
        ${avancado() ? `<div class="tecnico">${esc(tecnico)}</div>` : ""}</div>`).join("") || `<div class="rotulo">Nenhum termo.</div>`}</div>`;
  }

  function vazio(titulo, texto) {
    return `<div class="mon-vazio">${icone("monitor")}<b>${esc(titulo)}</b><span>${esc(texto)}</span></div>`;
  }

  // ================================================================ DESENHO
  function desenhar() {
    const corpo = $("#monitor-corpo");
    if (!corpo || !estado.aberto) return;
    $$("#monitor-abas .aba-mon").forEach((b) => b.classList.toggle("ativa", b.dataset.aba === estado.aba));
    $$("#seg-nivel button").forEach((b) => b.classList.toggle("ativo", b.dataset.nivel === estado.nivel));
    const abertas = new Set($$(".etapa-mon[open]", corpo).map((d) => d.dataset.indice));
    if (estado.aba === "modelo") { abaModelo(corpo); return; }
    corpo.innerHTML = estado.aba === "pipeline" ? abaPipeline()
      : estado.aba === "busca" ? abaBusca()
        : estado.aba === "desempenho" ? abaDesempenho()
          : abaGlossario();
    $$(".etapa-mon", corpo).forEach((d) => { if (abertas.has(d.dataset.indice)) d.open = true; });
    const filtro = $("#mon-filtro", corpo);
    if (filtro) {
      filtro.addEventListener("input", () => {
        estado.filtroGlossario = filtro.value;
        const pos = filtro.selectionStart;
        desenhar();
        const novo = $("#mon-filtro");
        novo.focus(); novo.setSelectionRange(pos, pos);
      });
    }
  }

  function abrirTermo(id) {
    estado.aba = "glossario";
    estado.filtroGlossario = "";
    desenhar();
    const el = document.getElementById("termo-" + id);
    if (el) { el.scrollIntoView({ block: "center" }); el.classList.add("destaque"); }
  }

  function definirAberto(aberto) {
    estado.aberto = aberto;
    preferencias.gravar("monitor", aberto ? "1" : "0");
    $("#monitor").hidden = !aberto;
    $("#btn-monitor").classList.toggle("ativo", aberto);
    document.body.classList.toggle("com-monitor", aberto);
    if (aberto) desenhar();
  }

  // ================================================================ API PÚBLICA
  window.Monitor = {
    iniciar(deps) {
      ({ $, $$, esc, icone, api, criar, preferencias, nomeAlgoritmo } = deps);
      estado.nivel = preferencias.ler("monitor.nivel", "iniciante");
      estado.lento = preferencias.ler("monitor.lento", "0") === "1";
      const larga = window.matchMedia ? window.matchMedia("(min-width: 1100px)").matches : true;
      $("#monitor-lento").checked = estado.lento;
      $$("#monitor-abas .aba-mon").forEach((b) => b.addEventListener("click", () => { estado.aba = b.dataset.aba; desenhar(); }));
      $$("#seg-nivel button").forEach((b) => b.addEventListener("click", () => {
        estado.nivel = b.dataset.nivel; preferencias.gravar("monitor.nivel", estado.nivel); desenhar();
      }));
      $("#monitor-lento").addEventListener("change", (ev) => {
        estado.lento = ev.target.checked; preferencias.gravar("monitor.lento", estado.lento ? "1" : "0");
      });
      $("#btn-monitor").addEventListener("click", () => definirAberto(!estado.aberto));
      $("#btn-fechar-monitor").addEventListener("click", () => definirAberto(false));
      $("#monitor-corpo").addEventListener("click", (ev) => {
        const t = ev.target.closest(".termo-mon");
        if (t) { ev.preventDefault(); abrirTermo(t.dataset.termo); return; }
        const linha = ev.target.closest("[data-candidato]");
        if (linha) { estado.candidato = Number(linha.dataset.candidato); desenhar(); }
      });
      definirAberto(preferencias.ler("monitor", larga ? "1" : "0") === "1");
    },

    get lento() { return estado.lento; },

    /** Uma pergunta foi enviada: o Pipeline começa vazio, esperando as etapas. */
    comecar(pergunta) {
      estado.aoVivo = { pergunta, etapas: [] };
      filaLenta = Promise.resolve();
      if (estado.aba !== "pipeline" && estado.aba !== "glossario") estado.aba = "pipeline";
      desenhar();
    },

    /** Uma etapa chegou ao vivo. Na câmera lenta, entra na fila com intervalo. */
    etapa(etapa) {
      const mostrar = () => {
        if (!estado.aoVivo) return;
        estado.aoVivo.etapas.push(etapa);
        if (estado.aba === "pipeline") {
          desenhar();
          const linhas = $$(".etapa-mon");
          const nova = linhas[linhas.length - 1];
          if (nova) nova.classList.add("chegou");
        }
      };
      if (!estado.lento) { mostrar(); return Promise.resolve(); }
      filaLenta = filaLenta.then(() => { mostrar(); return espera(ATRASO_LENTO); });
      return filaLenta;
    },

    /** Espera a câmera lenta terminar de mostrar as etapas. */
    terminar() { return filaLenta; },

    /** Mostra uma resposta (nova = entra no Desempenho da sessão). */
    mostrar(mensagem, nova) {
      estado.aoVivo = null;
      estado.mensagem = mensagem;
      estado.candidato = 0;
      const exp = mensagem && mensagem.meta && mensagem.meta.explicacao;
      if (nova && exp) {
        estado.sessao.push({ pergunta: mensagem.meta.pergunta || "", busca: exp.algoritmo_busca,
          total: exp.total_ms, memoria: exp.memoria_mb, etapas: exp.etapas || [] });
        if (estado.sessao.length > 50) estado.sessao.shift();
      }
      desenhar();
    },

    /** Abre o monitor numa mensagem (botão "Ver no monitor"). */
    focar(mensagem) {
      if (!estado.aberto) definirAberto(true);
      if (estado.aba === "glossario" || estado.aba === "modelo" || estado.aba === "desempenho") estado.aba = "pipeline";
      this.mostrar(mensagem, false);
    },

    /** Algo falhou no meio: sai do modo "pensando". */
    cancelar() { estado.aoVivo = null; desenhar(); },

    /** Addons ou configurações mudaram: a ficha do modelo é lida de novo. */
    invalidarModelo() { estado.modelo = null; if (estado.aba === "modelo") desenhar(); },
  };
})();
