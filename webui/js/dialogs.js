const Dialogs = (() => {
  const root = () => document.getElementById("modal-root");

  function open(cardHtml) {
    const r = root();
    r.innerHTML = `<div class="modal-card">${cardHtml}</div>`;
    r.classList.add("open");
  }

  function close() {
    const r = root();
    r.classList.remove("open");
    r.innerHTML = "";
  }

  function variantHeader(variant) {
    return variant === "error" ? "ERRO" : variant === "warning" ? "AVISO" : variant === "success" ? "SUCESSO" : "CERTIFLOW";
  }

  function alert(title, message, variant = "info") {
    return new Promise((resolve) => {
      open(`
        <div class="modal-header">${variantHeader(variant)} · ${escapeHtml(title)}</div>
        <div class="modal-body"><div class="modal-message">${escapeHtml(message)}</div></div>
        <div class="modal-footer"><button class="btn btn-primary" id="dlg-ok">OK</button></div>
      `);
      document.getElementById("dlg-ok").onclick = () => { close(); resolve(true); };
    });
  }

  function confirm(title, message) {
    return new Promise((resolve) => {
      open(`
        <div class="modal-header">${escapeHtml(title)}</div>
        <div class="modal-body"><div class="modal-message">${escapeHtml(message)}</div></div>
        <div class="modal-footer">
          <button class="btn btn-outline" id="dlg-no">Não</button>
          <button class="btn btn-primary" id="dlg-yes">Sim</button>
        </div>
      `);
      document.getElementById("dlg-yes").onclick = () => { close(); resolve(true); };
      document.getElementById("dlg-no").onclick = () => { close(); resolve(false); };
    });
  }

  function fieldInputHtml(f) {
    if (f.type === "select") {
      const optionsHtml = (f.options || []).map(o => `
        <option value="${escapeHtml(o)}" ${o === f.value ? "selected" : ""}>${escapeHtml(o)}</option>
      `).join("");
      return `
        <select id="dlg-f-${f.name}">
          <option value="">—</option>
          ${optionsHtml}
        </select>
      `;
    }
    return `<input type="text" id="dlg-f-${f.name}" value="${escapeHtml(f.value || "")}" placeholder="${escapeHtml(f.placeholder || "")}">`;
  }

  function prompt(title, message, fields) {
    return new Promise((resolve) => {
      const fieldsHtml = fields.map(f => `
        <div class="field">
          <label>${escapeHtml(f.label)}${f.required ? " *" : ""}</label>
          ${fieldInputHtml(f)}
        </div>
      `).join("");

      open(`
        <div class="modal-header">${escapeHtml(title)}</div>
        <div class="modal-body">
          ${message ? `<div class="modal-message">${escapeHtml(message)}</div>` : ""}
          ${fieldsHtml}
          <div class="modal-message" id="dlg-error" style="color:#D32F2F;display:none;"></div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" id="dlg-cancel">Cancelar</button>
          <button class="btn btn-primary" id="dlg-save">Salvar</button>
        </div>
      `);

      const collect = () => {
        const out = {};
        for (const f of fields) out[f.name] = document.getElementById(`dlg-f-${f.name}`).value.trim();
        return out;
      };

      document.getElementById("dlg-save").onclick = () => {
        const values = collect();
        const missing = fields.find(f => f.required && !values[f.name]);
        if (missing) {
          const err = document.getElementById("dlg-error");
          err.textContent = `Preencha o campo "${missing.label}".`;
          err.style.display = "block";
          return;
        }
        close();
        resolve(values);
      };
      document.getElementById("dlg-cancel").onclick = () => { close(); resolve(null); };
    });
  }

  function escapeHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }

  return { alert, confirm, prompt };
})();
