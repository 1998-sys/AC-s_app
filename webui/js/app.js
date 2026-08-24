window.addEventListener("error", (e) => {
  alert("Erro JS: " + e.message + "\n" + (e.filename || "") + ":" + (e.lineno || ""));
});
window.addEventListener("unhandledrejection", (e) => {
  alert("Promise rejeitada: " + (e.reason && e.reason.message ? e.reason.message : e.reason));
});

const App = (() => {
  const RECENT_KEY = "certiflow_recentes";
  const TRACKER_STEPS = ["PDF", "Revisão", "Saída"];
  let currentTag = null;
  let selectedFiles = [];
  let lastIssues = [];
  let issueSelections = {};

  function $(id) { return document.getElementById(id); }

  function showView(name) {
    document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
    $(`view-${name}`).classList.add("active");
  }

  function setTracker(step) {
    // step: 1 = select, 2 = reading/review, 3 = output
    const html = TRACKER_STEPS.map((label, i) => {
      const n = i + 1;
      const dotState = n < step ? "done" : n === step ? "active" : "";
      const dotContent = n < step ? "✓" : n;
      let out = `<span class="tracker-step ${dotState}">${dotContent}</span><span class="tracker-label ${n === step ? "active" : ""}">${label}</span>`;
      if (n < TRACKER_STEPS.length) out += `<span class="tracker-line ${n < step ? "done" : ""}"></span>`;
      return out;
    }).join("");
    document.querySelectorAll("[data-tracker]").forEach(el => { el.innerHTML = html; });
  }

  // ---------- Tela 1: Selecionar certificado ----------

  function loadRecentes() {
    try { return JSON.parse(localStorage.getItem(RECENT_KEY) || "[]"); } catch { return []; }
  }

  function pushRecente(item) {
    const list = loadRecentes();
    list.unshift(item);
    localStorage.setItem(RECENT_KEY, JSON.stringify(list.slice(0, 6)));
    renderRecentes();
  }

  function renderRecentes() {
    const list = loadRecentes();
    const box = $("recent-list");
    if (!list.length) { box.innerHTML = ""; $("recent-section").style.display = "none"; return; }
    $("recent-section").style.display = "flex";
    box.innerHTML = list.map(item => `
      <div class="recent-item">
        <div class="recent-icon">${item.kind || "PDF"}</div>
        <div class="recent-info">
          <span class="recent-name">${item.name}</span>
          <span class="recent-meta">${item.meta}</span>
        </div>
        <span class="pill pill-${item.status}">${item.statusLabel}</span>
      </div>
    `).join("");
  }

  function resetSelecao() {
    selectedFiles = [];
    $("dropzone").style.display = "flex";
    $("selected-file-chip").style.display = "none";
    $("btn-ler-certificado").disabled = true;
    $("btn-ler-certificado").classList.remove("btn-primary");
    $("select-hint").textContent = "Selecione um PDF para continuar";
    $("select-hint").classList.remove("error");
  }

  function aplicarSelecao(itens) {
    if (!itens || !itens.length) return;
    selectedFiles = itens;
    $("dropzone").style.display = "none";
    $("selected-file-chip").style.display = "flex";
    $("selected-file-name").textContent = selectedFiles.length === 1
      ? selectedFiles[0].nome
      : `${selectedFiles.length} certificados selecionados`;
    $("btn-ler-certificado").disabled = false;
    $("btn-ler-certificado").classList.add("btn-primary");
    $("select-hint").textContent = selectedFiles.length === 1
      ? "Pronto para ler o certificado"
      : "Pronto para ler os certificados";
  }

  async function escolherArquivos() {
    const resultado = await pywebview.api.escolher_arquivos_pdf();
    aplicarSelecao(resultado);
  }

  function trocarArquivo() {
    resetSelecao();
  }

  // ---------- Arrastar e soltar certificados ----------
  // O navegador não dá acesso ao caminho real do arquivo solto no disco
  // (só ao conteúdo) — lê cada um como base64 e manda pro backend salvar
  // numa pasta temporária, que devolve a mesma estrutura {caminho, nome}
  // usada pela seleção via diálogo.

  function fileParaBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result.split(",")[1] || "");
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(file);
    });
  }

  async function processarArquivosSoltos(fileList) {
    const arquivos = Array.from(fileList).filter(f => /\.(pdf|xml)$/i.test(f.name));
    if (!arquivos.length) {
      Dialogs.alert("Arquivo não suportado", "Solte um PDF ou XML de linearização.", "error");
      return;
    }
    const payload = await Promise.all(arquivos.map(async f => ({
      nome: f.name,
      conteudo_base64: await fileParaBase64(f),
    })));
    const resultado = await pywebview.api.receber_arquivos_soltos(payload);
    aplicarSelecao(resultado);
  }

  function initDropzone() {
    const zone = $("dropzone");

    // Impede o comportamento padrão do navegador (abrir o arquivo solto
    // como se fosse uma navegação) em qualquer ponto da janela, não só na
    // dropzone — sem isso, soltar fora da área certa navega pra fora do app.
    ["dragover", "drop"].forEach(evt => {
      window.addEventListener(evt, e => e.preventDefault());
    });

    ["dragenter", "dragover"].forEach(evt => {
      zone.addEventListener(evt, e => {
        e.preventDefault();
        zone.classList.add("dropzone-active");
      });
    });
    ["dragleave", "drop"].forEach(evt => {
      zone.addEventListener(evt, e => {
        e.preventDefault();
        zone.classList.remove("dropzone-active");
      });
    });
    zone.addEventListener("drop", e => {
      e.preventDefault();
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
        processarArquivosSoltos(e.dataTransfer.files);
      }
    });
  }

  function iniciarLeitura() {
    if (!selectedFiles.length) return;
    $("reading-filename").textContent = selectedFiles[0].nome;
    $("reading-instr-summary").style.display = "none";
    $("reading-started-at").textContent = `Iniciado às ${new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
    $("reading-fila-progresso").style.display = "none";
    resetChecklist();
    setTracker(2);
    showView("reading");
    pywebview.api.iniciar_leitura(selectedFiles);
  }

  function cancelarLeitura() {
    pywebview.api.cancelar_leitura();
    setTracker(1);
    showView("select");
  }

  // ---------- Tela 2: Lendo o PDF ----------

  const CHECKLIST_STEPS = ["extract", "compare", "validate", "build"];

  function resetChecklist() {
    $("progress-fill").style.width = "0%";
    $("progress-pct").textContent = "0%";
    CHECKLIST_STEPS.forEach(s => {
      const el = $(`chk-${s}`);
      el.classList.remove("done", "active");
    });
    $(`chk-extract`).classList.add("active");
  }

  function setFilaProgresso(indice, total, nome) {
    // Chamado pelo backend a cada novo arquivo da fila (modo lote) — reseta
    // a tela de leitura pro próximo item.
    $("reading-filename").textContent = nome || "—";
    $("reading-instr-summary").style.display = "none";
    resetChecklist();
    const el = $("reading-fila-progresso");
    el.textContent = `Certificado ${indice} de ${total}`;
    el.style.display = "inline";
  }

  function onProgress(percent, activeStep, doneSteps) {
    $("progress-fill").style.width = `${percent}%`;
    $("progress-pct").textContent = `${percent}%`;
    CHECKLIST_STEPS.forEach(s => {
      const el = $(`chk-${s}`);
      el.classList.remove("done", "active");
      if (doneSteps.includes(s)) el.classList.add("done");
      else if (s === activeStep) el.classList.add("active");
    });
  }

  function fieldsHtml(fields) {
    return (fields || []).map(f => `
      <div>
        <div class="instr-field-label">${f.label}</div>
        <div class="instr-field-value">${f.value ?? "—"}</div>
      </div>
    `).join("");
  }

  function showReadingInstrument(payload) {
    $("reading-badge").textContent = payload.badge || "";
    const photo = $("reading-photo");
    if (payload.photo) {
      photo.src = `assets/${payload.photo}`;
      photo.alt = payload.badge || "";
      photo.style.display = "block";
    } else {
      photo.style.display = "none";
    }
    $("reading-fields").innerHTML = fieldsHtml(payload.fields);
    $("reading-instr-summary").style.display = "flex";
  }

  // ---------- Tela 3: Revisar divergências ----------

  function showReview(payload) {
    currentTag = payload.tag;
    issueSelections = {};
    $("review-tag").textContent = payload.tag || "—";
    $("review-sub").textContent = payload.sub || "";
    $("review-badge").textContent = payload.badge || "";
    const photo = $("review-photo");
    if (payload.photo) {
      photo.src = `assets/${payload.photo}`;
      photo.alt = payload.badge || "";
      photo.style.display = "block";
    } else {
      photo.style.display = "none";
    }
    $("review-fields").innerHTML = fieldsHtml(payload.fields);
    renderIssues(payload.issues || []);
    setTracker(2);
    showView("review");

    if (!(payload.issues || []).length) {
      confirmarGeracao();
    }
  }

  function updateErrorBadge(issues) {
    const abertos = issues.filter(i => i.blocking && !i.resolved).length;
    const badge = $("review-error-badge");
    if (abertos > 0) {
      badge.textContent = `${abertos} erro${abertos > 1 ? "s" : ""} aberto${abertos > 1 ? "s" : ""}`;
      badge.classList.add("show");
    } else {
      badge.textContent = "";
      badge.classList.remove("show");
    }
  }

  function renderIssueCard(issue) {
    if (issue.resolved) {
      // Duas opções e o usuário escolheu "manter o cadastro" (não rodou a
      // ação): o certificado e o cadastro continuam divergentes de fato —
      // não deve parecer uma resolução limpa igual ao caso "usar o
      // certificado" (que atualiza o cadastro e resolve o conflito).
      const mantidoSemCorrigir = issue.opcoes && issue.aplicado === false;
      const cls = mantidoSemCorrigir ? "warn" : "resolved";
      const tag = mantidoSemCorrigir ? `<span class="issue-tag mantido">MANTIDO</span>` : "";
      const mensagem = mantidoSemCorrigir
        ? `${issue.message} · Cadastro mantido — divergência não corrigida.`
        : issue.message;

      return `
        <div class="issue-card ${cls}">
          <div class="issue-row">
            <div>
              <div class="issue-title">${issue.title}</div>
              <div class="issue-message">${mensagem}</div>
            </div>
            <div style="display:flex;align-items:center;gap:10px;flex:none;">
              ${tag}
              <span class="issue-undo" data-undo="${issue.key}">Desfazer</span>
            </div>
          </div>
        </div>
      `;
    }

    if (issue.opcoes && issue.opcoes.length === 2) {
      const recomendadoIdx = issue.opcoes.findIndex(o => o.recomendado);
      const selIdx = issueSelections[issue.key] ?? (recomendadoIdx >= 0 ? recomendadoIdx : 0);
      const opcoesHtml = issue.opcoes.map((o, i) => `
        <div class="issue-option ${i === selIdx ? "selected" : ""}" data-option="${issue.key}:${i}">
          <span class="issue-option-dot"></span>
          <div class="issue-option-body">
            <span class="issue-option-label">${o.label}</span>
            <span class="issue-option-value">${o.valor ?? "—"}</span>
          </div>
          ${o.recomendado ? '<span class="issue-option-tag">Recomendado</span>' : ""}
        </div>
      `).join("");

      return `
        <div class="issue-card error">
          <div class="issue-row">
            <span class="issue-title">${issue.title}</span>
            <span class="issue-tag error">ERRO</span>
          </div>
          <div class="issue-message">${issue.message}</div>
          <div class="issue-options">${opcoesHtml}</div>
          <button class="btn btn-primary" data-confirm-option="${issue.key}">Aplicar e ir para a próxima</button>
        </div>
      `;
    }

    const cls = issue.blocking ? "error" : "warn";
    const tag = issue.blocking
      ? `<span class="issue-tag error">ERRO</span>`
      : `<span class="issue-tag warn">AVISO</span>`;

    let actions = "";
    if (issue.has_action) {
      actions = `<div class="issue-actions">
        <button class="btn btn-outline" data-dismiss="${issue.key}">Ignorar</button>
        <button class="btn btn-primary" data-apply="${issue.key}">Aplicar correção</button>
      </div>`;
    }

    return `
      <div class="issue-card ${cls}">
        <div class="issue-row">
          <span class="issue-title">${issue.title}</span>
          ${tag}
        </div>
        <div class="issue-message">${issue.message}</div>
        ${actions}
      </div>
    `;
  }

  function renderIssues(issues) {
    lastIssues = issues;
    const total = issues.length;
    const resolved = issues.filter(i => i.resolved).length;
    $("issue-count").textContent = total ? `${resolved} de ${total} resolvidas` : "sem divergências";
    $("issue-progress-fill").style.width = total ? `${(resolved / total) * 100}%` : "0%";
    updateErrorBadge(issues);

    $("issue-list").innerHTML = issues.map(renderIssueCard).join("") || `<div class="issue-message">Nenhuma divergência encontrada.</div>`;

    document.querySelectorAll("[data-apply]").forEach(btn => {
      btn.onclick = () => resolverDivergencia(btn.dataset.apply, true);
    });
    document.querySelectorAll("[data-dismiss]").forEach(btn => {
      btn.onclick = () => resolverDivergencia(btn.dataset.dismiss, false);
    });
    document.querySelectorAll("[data-undo]").forEach(el => {
      el.onclick = () => desfazerDivergencia(el.dataset.undo);
    });
    document.querySelectorAll("[data-option]").forEach(el => {
      el.onclick = () => {
        const [key, idx] = el.dataset.option.split(":");
        issueSelections[key] = Number(idx);
        renderIssues(lastIssues);
      };
    });
    document.querySelectorAll("[data-confirm-option]").forEach(btn => {
      btn.onclick = () => {
        const key = btn.dataset.confirmOption;
        const idx = issueSelections[key] ?? 0;
        resolverDivergencia(key, idx === 0);
      };
    });

    const pendentesBloqueantes = issues.filter(i => i.blocking && !i.resolved).length;
    const genBtn = $("btn-gerar");
    genBtn.disabled = pendentesBloqueantes > 0;
    genBtn.classList.toggle("btn-primary", pendentesBloqueantes === 0);
    $("review-hint").textContent = pendentesBloqueantes > 0
      ? `Resolva ${pendentesBloqueantes} erro${pendentesBloqueantes > 1 ? "s" : ""} para liberar a geração`
      : "Pronto para gerar";
    $("review-hint").classList.toggle("error", pendentesBloqueantes > 0);
  }

  async function resolverDivergencia(key, aplicar) {
    delete issueSelections[key];
    const issues = await pywebview.api.resolver_divergencia(key, aplicar);
    renderIssues(issues);
  }

  async function desfazerDivergencia(key) {
    const issues = await pywebview.api.desfazer_divergencia(key);
    renderIssues(issues);
  }

  function pushRecenteFromResultado(resultado) {
    pushRecente({
      name: resultado.pdf_name || resultado.tag || "certificado",
      meta: `Hoje · ${resultado.tag || ""}`,
      kind: (resultado.badge || "PDF").slice(0, 3),
      status: resultado.avisos ? "warn" : "ok",
      statusLabel: resultado.avisos ? `${resultado.avisos} aviso${resultado.avisos > 1 ? "s" : ""}` : "OK",
    });
  }

  async function confirmarGeracao() {
    const resultado = await pywebview.api.confirmar_geracao();
    if (!resultado) return;

    if (resultado.avancando_lote) {
      // Backend já registrou este item e iniciou o próximo da fila — só
      // registra nos recentes e segue (a tela de leitura já foi atualizada
      // via setFilaProgresso).
      pushRecenteFromResultado(resultado.item);
      return;
    }

    if (resultado.lote) {
      resultado.itens.forEach(pushRecenteFromResultado);
      showOutputLote(resultado);
      return;
    }

    pushRecenteFromResultado(resultado);
    showOutput(resultado);
  }

  // ---------- Tela 4: Arquivos gerados ----------

  function wireOpenButtons(root) {
    root.querySelectorAll("[data-open]").forEach(btn => {
      btn.onclick = () => pywebview.api.abrir_arquivo(decodeURIComponent(btn.dataset.open));
    });
  }

  function showOutput(payload) {
    $("output-sub").textContent = payload.sub || "";
    $("output-single").style.display = "flex";
    $("output-lote").style.display = "none";
    $("output-files").innerHTML = (payload.files || []).map(f => `
      <div class="output-file-row">
        <div class="output-file-icon ${f.kind === "XML" ? "xml" : ""}">${f.kind}</div>
        <div class="recent-info">
          <span class="output-file-name">${f.name}</span>
          <span class="output-file-meta">${f.meta}</span>
        </div>
        <button class="btn btn-outline" style="width:auto;padding:0 12px;height:28px;font-size:11px;" data-open="${encodeURIComponent(f.path)}">Abrir</button>
      </div>
    `).join("");
    wireOpenButtons($("output-files"));
    setTracker(3);
    showView("output");
  }

  function showOutputLote(payload) {
    $("output-sub").textContent = payload.sub || "";
    $("output-single").style.display = "none";
    $("output-lote").style.display = "flex";

    const itens = payload.itens || [];
    const eventos = payload.eventos || [];
    $("output-count-label").textContent = `${payload.total_arquivos || 0} arquivo${payload.total_arquivos === 1 ? "" : "s"}`;

    $("output-groups").innerHTML = itens.map(item => `
      <div class="output-group">
        <div class="output-group-head">
          <span class="output-group-tag">${item.tag || "—"}</span>
          <span class="output-group-badge">${item.badge || ""}</span>
          <span class="output-group-meta">${item.sub || ""}</span>
          ${item.avisos ? `<span class="output-group-warn">${item.avisos} aviso${item.avisos > 1 ? "s" : ""}</span>` : ""}
        </div>
        ${(item.files || []).map(f => `
          <div class="output-file-row">
            <div class="output-file-icon ${f.kind === "XML" ? "xml" : ""}">${f.kind}</div>
            <div class="recent-info">
              <span class="output-file-name">${f.name}</span>
              <span class="output-file-meta">${f.meta}</span>
            </div>
            <button class="btn btn-outline" style="width:auto;padding:0 12px;height:28px;font-size:11px;" data-open="${encodeURIComponent(f.path)}">Abrir</button>
          </div>
        `).join("")}
      </div>
    `).join("");
    wireOpenButtons($("output-groups"));

    $("output-events").innerHTML = eventos.map(ev => `
      <div class="output-event ${ev.ok ? "" : "erro"}">
        <span class="output-event-title">${ev.nome} — ${ev.titulo}</span>
        <span class="output-event-msg">${ev.mensagem}</span>
      </div>
    `).join("");

    $("btn-abrir-todos").onclick = () => {
      itens.forEach(item => (item.files || []).forEach(f => pywebview.api.abrir_arquivo(f.path)));
    };

    setTracker(3);
    showView("output");
  }

  function processarOutro() {
    resetSelecao();
    setTracker(1);
    showView("select");
  }

  // ---------- Tela 5: Editar instrumento ----------

  async function abrirEditarInstrumento(tagPrefill) {
    $("edit-tag").value = tagPrefill || "";
    $("edit-fields").style.display = "none";
    showView("edit-instrument");
    if (tagPrefill) await consultarInstrumento();
  }

  async function consultarInstrumento() {
    const tag = $("edit-tag").value.trim().toUpperCase();
    if (!tag) return;
    const reg = await pywebview.api.buscar_instrumento(tag);
    if (!reg) return;
    $("edit-fields").style.display = "flex";
    $("edit-sn").value = reg.sn_instrumento || "";
    const isPO = reg.tipo === "PO";
    $("edit-sec-fields").style.display = isPO ? "none" : "flex";
    if (!isPO) {
      $("edit-sn-sensor").value = reg.sn_sensor || "";
      $("edit-min-range").value = reg.min_range ?? "";
      $("edit-max-range").value = reg.max_range ?? "";
    }
    $("edit-data-calibracao").value = reg.data_calibracao || "";
    $("edit-proxima-calibracao").value = reg.proxima_calibracao || "";
    $("edit-numero-certificado").value = reg.numero_certificado || "";
    $("edit-laboratorio").value = reg.laboratorio || "";
    $("edit-observacoes").value = reg.observacoes || "";
    setUltimaAlteracao(reg.modificado_por, reg.modificado_em);
    setReadOnly(true);
  }

  function setUltimaAlteracao(por, em) {
    const el = $("edit-ultima-alteracao");
    if (!por && !em) {
      el.style.display = "none";
      return;
    }
    el.textContent = `Última alteração por ${por || "—"} em ${em || "—"}.`;
    el.style.display = "flex";
  }

  const CAMPOS_EDIT_TEXTO = [
    "edit-sn", "edit-sn-sensor", "edit-min-range", "edit-max-range",
    "edit-data-calibracao", "edit-proxima-calibracao", "edit-numero-certificado", "edit-observacoes",
  ];

  function setReadOnly(readonly) {
    CAMPOS_EDIT_TEXTO.forEach(id => { $(id).readOnly = readonly; });
    $("edit-laboratorio").disabled = readonly;
  }

  async function salvarInstrumento() {
    const tag = $("edit-tag").value.trim().toUpperCase();
    const isPO = $("edit-sec-fields").style.display === "none";
    const resultado = await pywebview.api.salvar_instrumento({
      tag,
      tipo: isPO ? "PO" : "SEC",
      sn_instrumento: $("edit-sn").value.trim(),
      sn_sensor: $("edit-sn-sensor").value.trim(),
      min_range: $("edit-min-range").value.trim(),
      max_range: $("edit-max-range").value.trim(),
      data_calibracao: $("edit-data-calibracao").value.trim(),
      proxima_calibracao: $("edit-proxima-calibracao").value.trim(),
      numero_certificado: $("edit-numero-certificado").value.trim(),
      laboratorio: $("edit-laboratorio").value,
      observacoes: $("edit-observacoes").value.trim(),
    });
    if (resultado) {
      setReadOnly(true);
      setUltimaAlteracao(resultado.modificado_por, resultado.modificado_em);
    }
  }

  function init() {
    renderRecentes();
    resetSelecao();
    $("dropzone").onclick = escolherArquivos;
    initDropzone();
    $("btn-trocar-arquivo").onclick = trocarArquivo;
    $("btn-ler-certificado").onclick = iniciarLeitura;
    $("btn-cancelar-leitura").onclick = cancelarLeitura;
    $("btn-editar-instrumento").onclick = () => abrirEditarInstrumento(null);
    $("edit-back").onclick = () => showView("select");
    $("btn-consultar").onclick = consultarInstrumento;
    $("btn-editar-campos").onclick = () => setReadOnly(false);
    $("btn-salvar-instrumento").onclick = salvarInstrumento;
    $("btn-importar-xlsx").onclick = () => pywebview.api.importar_xlsx();
    $("btn-exportar-xlsx").onclick = () => pywebview.api.exportar_xlsx();
    $("btn-gerar").onclick = confirmarGeracao;
    $("btn-processar-outro").onclick = processarOutro;
    $("link-editar-instrumento").onclick = () => abrirEditarInstrumento(currentTag);
    setTracker(1);
    showView("select");
  }

  function boot() {
    // window.pywebview.api é injetado de forma assíncrona; se o usuário clicar antes
    // do evento pywebviewready, a chamada falha. Esperamos por ele antes de ligar a UI.
    if (window.pywebview && window.pywebview.api) {
      init();
    } else {
      window.addEventListener("pywebviewready", init, { once: true });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  return {
    onProgress, showReadingInstrument, showReview, showOutput, showOutputLote,
    setFilaProgresso, showView, setTracker,
  };
})();
