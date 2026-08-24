window.addEventListener("error", (e) => {
  alert("Erro JS: " + e.message + "\n" + (e.filename || "") + ":" + (e.lineno || ""));
});
window.addEventListener("unhandledrejection", (e) => {
  alert("Promise rejeitada: " + (e.reason && e.reason.message ? e.reason.message : e.reason));
});

const App = (() => {
  const RECENT_KEY = "certiflow_recentes";
  let currentTag = null;

  function $(id) { return document.getElementById(id); }

  function showView(name) {
    document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
    $(`view-${name}`).classList.add("active");
  }

  function setTracker(step) {
    // step: 1 = select, 2 = reading/review, 3 = output
    const dot1 = $("tk-1"), dot2 = $("tk-2"), dot3 = $("tk-3");
    const lbl1 = $("tkl-1"), lbl2 = $("tkl-2"), lbl3 = $("tkl-3");
    const line1 = $("tkline-1"), line2 = $("tkline-2");

    [dot1, dot2, dot3].forEach(d => d.classList.remove("done", "active"));
    [lbl1, lbl2, lbl3].forEach(l => l.classList.remove("active"));
    [line1, line2].forEach(l => l.classList.remove("done"));

    if (step >= 1) { dot1.textContent = step > 1 ? "✓" : "1"; dot1.classList.add(step > 1 ? "done" : "active"); if (step === 1) lbl1.classList.add("active"); }
    if (step > 1) line1.classList.add("done");
    if (step >= 2) { dot2.textContent = step > 2 ? "✓" : "2"; dot2.classList.add(step > 2 ? "done" : "active"); if (step === 2) lbl2.classList.add("active"); }
    if (step > 2) line2.classList.add("done");
    if (step >= 3) { dot3.textContent = "3"; dot3.classList.add("active"); lbl3.classList.add("active"); }
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

  async function selecionarPdf() {
    const nome = await pywebview.api.selecionar_pdf();
    if (!nome) return;
    $("reading-filename").textContent = nome;
    setTracker(2);
    resetChecklist();
    showView("reading");
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

  // ---------- Tela 3: Revisar divergências ----------

  function showReview(payload) {
    currentTag = payload.tag;
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
    $("review-fields").innerHTML = (payload.fields || []).map(f => `
      <div>
        <div class="instr-field-label">${f.label}</div>
        <div class="instr-field-value">${f.value ?? "—"}</div>
      </div>
    `).join("");
    renderIssues(payload.issues || []);
    setTracker(2);
    showView("review");

    if (!(payload.issues || []).length) {
      confirmarGeracao();
    }
  }

  function renderIssues(issues) {
    const total = issues.length;
    const resolved = issues.filter(i => i.resolved).length;
    $("issue-count").textContent = total ? `${resolved} de ${total} resolvidas` : "sem divergências";
    $("issue-progress-fill").style.width = total ? `${(resolved / total) * 100}%` : "0%";

    $("issue-list").innerHTML = issues.map(issue => {
      const cls = issue.resolved ? "resolved" : (issue.blocking ? "error" : "warn");
      const tag = issue.resolved
        ? `<span class="issue-undo">Resolvida</span>`
        : issue.blocking
          ? `<span class="issue-tag error">ERRO</span>`
          : `<span class="issue-tag warn">AVISO</span>`;

      let actions = "";
      if (!issue.resolved) {
        if (issue.has_action) {
          actions = `<div class="issue-actions">
            <button class="btn btn-outline" data-dismiss="${issue.key}">Ignorar</button>
            <button class="btn btn-primary" data-apply="${issue.key}">Aplicar correção</button>
          </div>`;
        } else if (!issue.blocking) {
          actions = `<div class="issue-actions"><button class="btn btn-outline" data-dismiss="${issue.key}">Ciente</button></div>`;
        }
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
    }).join("") || `<div class="issue-message">Nenhuma divergência encontrada.</div>`;

    document.querySelectorAll("[data-apply]").forEach(btn => {
      btn.onclick = () => resolverDivergencia(btn.dataset.apply, true);
    });
    document.querySelectorAll("[data-dismiss]").forEach(btn => {
      btn.onclick = () => resolverDivergencia(btn.dataset.dismiss, false);
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
    const issues = await pywebview.api.resolver_divergencia(key, aplicar);
    renderIssues(issues);
  }

  async function confirmarGeracao() {
    const resultado = await pywebview.api.confirmar_geracao();
    if (resultado) {
      pushRecente({
        name: resultado.pdf_name || currentTag || "certificado",
        meta: `Hoje · ${currentTag || ""}`,
        kind: (resultado.badge || "PDF").slice(0, 3),
        status: resultado.avisos ? "warn" : "ok",
        statusLabel: resultado.avisos ? `${resultado.avisos} aviso${resultado.avisos > 1 ? "s" : ""}` : "OK",
      });
      showOutput(resultado);
    }
  }

  // ---------- Tela 4: Arquivos gerados ----------

  function showOutput(payload) {
    $("output-sub").textContent = payload.sub || "";
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
    document.querySelectorAll("[data-open]").forEach(btn => {
      btn.onclick = () => pywebview.api.abrir_arquivo(decodeURIComponent(btn.dataset.open));
    });
    setTracker(3);
    showView("output");
  }

  function processarOutro() {
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
    setReadOnly(true);
  }

  function setReadOnly(readonly) {
    ["edit-sn", "edit-sn-sensor", "edit-min-range", "edit-max-range"].forEach(id => {
      $(id).readOnly = readonly;
    });
  }

  async function salvarInstrumento() {
    const tag = $("edit-tag").value.trim().toUpperCase();
    const isPO = $("edit-sec-fields").style.display === "none";
    const ok = await pywebview.api.salvar_instrumento({
      tag,
      tipo: isPO ? "PO" : "SEC",
      sn_instrumento: $("edit-sn").value.trim(),
      sn_sensor: $("edit-sn-sensor").value.trim(),
      min_range: $("edit-min-range").value.trim(),
      max_range: $("edit-max-range").value.trim(),
    });
    if (ok) setReadOnly(true);
  }

  function init() {
    renderRecentes();
    $("dropzone").onclick = selecionarPdf;
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

  return { onProgress, showReview, showOutput, showView, setTracker };
})();
