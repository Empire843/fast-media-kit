/* ===== TOOL NAVIGATION ===== */
document.querySelectorAll("[data-tool]").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.classList.contains("upcoming")) return;
    document.querySelectorAll(".nav-tool").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const name = btn.dataset.tool;
    document.querySelectorAll("[data-workspace]").forEach((ws) => {
      ws.classList.toggle("active", ws.dataset.workspace === name);
    });
    // Close mobile sidebar
    document.getElementById("sidebar")?.classList.remove("open");
  });
});

/* ===== CATEGORY COLLAPSE ===== */
document.querySelectorAll("[data-category-toggle]").forEach((label) => {
  label.addEventListener("click", () => {
    label.closest("[data-category]")?.classList.toggle("collapsed");
  });
});

/* ===== SEARCH FILTER ===== */
document.querySelector("[data-tool-search]")?.addEventListener("input", (e) => {
  const q = e.target.value.toLowerCase().trim();
  document.querySelectorAll(".nav-tool").forEach((btn) => {
    const text = (btn.dataset.searchText || btn.textContent || "").toLowerCase();
    btn.hidden = q && !text.includes(q);
  });
  // Show all categories when searching, hide empty ones
  document.querySelectorAll("[data-category]").forEach((cat) => {
    cat.classList.remove("collapsed");
    const visible = cat.querySelectorAll(".nav-tool:not([hidden])").length;
    cat.style.display = q && !visible ? "none" : "";
  });
});

/* ===== MOBILE SIDEBAR ===== */
document.querySelectorAll(".sidebar-toggle, [data-sidebar-toggle]").forEach((btn) => {
  btn.addEventListener("click", () => document.getElementById("sidebar")?.classList.toggle("open"));
});
document.getElementById("sidebar-overlay")?.addEventListener("click", () => {
  document.getElementById("sidebar")?.classList.remove("open");
});

/* ===== ASYNC FORM ===== */
document.querySelectorAll("[data-async-form]").forEach((form) => {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const sub = event.submitter;
    const sel = sub?.dataset.target || form.dataset.target;
    const target = document.querySelector(sel);
    const action = sub?.getAttribute("formaction") || form.action;
    const fd = new FormData(form);
    const t0 = Date.now();
    const name = form.closest(".workspace")?.querySelector("h2")?.textContent?.trim() || "Tool";

    target.innerHTML = `<div class="notice loading"><strong>Processing…</strong><p>Working on it…</p></div><details class="log-panel" open><summary>Log</summary><pre data-live-log>[0s] ${name} started…</pre></details>`;
    const log = target.querySelector("[data-live-log]");
    const timer = setInterval(() => { const s = ((Date.now()-t0)/1000)|0; log.textContent = `[${s}s] ${name} — processing…`; }, 1000);
    [...form.querySelectorAll("button[type=submit]")].forEach((b) => (b.disabled = true));

    try {
      const res = await fetch(action, { method: "POST", body: fd });
      target.innerHTML = await res.text();
    } catch (err) {
      target.innerHTML = `<div class="notice error"><strong>Failed</strong><p>${err}</p></div>`;
    } finally {
      clearInterval(timer);
      [...form.querySelectorAll("button[type=submit]")].forEach((b) => (b.disabled = false));
    }
  });
});

/* ===== COLLAPSIBLE ADVANCED ===== */
document.querySelectorAll("[data-toggle-advanced]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const open = btn.classList.toggle("open");
    btn.nextElementSibling?.classList.toggle("open", open);
  });
});

/* ===== DRAG & DROP ===== */
document.querySelectorAll("[data-drop-zone]").forEach((zone) => {
  const input = zone.querySelector('input[type="file"]');
  if (!input) return;
  zone.addEventListener("click", (e) => { if (!e.target.closest(".remove-file")) input.click(); });
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("dragover"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault(); zone.classList.remove("dragover");
    if (e.dataTransfer.files.length) { input.files = e.dataTransfer.files; input.dispatchEvent(new Event("change", { bubbles: true })); }
  });
  input.addEventListener("change", () => {
    zone.querySelector(".drop-zone-file")?.remove();
    if (input.files?.length) {
      const d = document.createElement("div"); d.className = "drop-zone-file";
      d.innerHTML = `<span>${input.files[0].name}</span><button type="button" class="remove-file">×</button>`;
      d.querySelector(".remove-file").addEventListener("click", (e) => { e.stopPropagation(); input.value = ""; d.remove(); });
      zone.appendChild(d);
    }
  });
});

/* ===== XLSX SHEET LOADER ===== */
document.querySelectorAll("[data-sheet-loader]").forEach((zone) => {
  const input = zone.querySelector('input[type="file"]');
  if (!input) return;
  input.addEventListener("change", async () => {
    const target = document.querySelector(zone.dataset.sheetTarget);
    if (!target || !input.files?.length) return;
    const fd = new FormData(); fd.append(input.name, input.files[0]);
    target.innerHTML = `<div class="notice loading"><strong>Reading workbook…</strong></div>`;
    try { target.innerHTML = await (await fetch("/tools/xlsx-sheets", { method: "POST", body: fd })).text(); }
    catch (err) { target.innerHTML = `<div class="notice error"><strong>Error</strong><p>${err}</p></div>`; }
  });
});

/* ===== PROVIDER DEFAULTS ===== */
document.querySelectorAll("[data-provider-select]").forEach((sel) => {
  const mi = sel.closest("form")?.querySelector("[data-model-input]");
  const defs = { aishop24h: "google/gemini-2.5-pro", openai: "gpt-4o-mini", gemini: "gemini-1.5-flash", openai_compatible: "gpt-4o-mini" };
  let last = defs[sel.value] || "";
  sel.addEventListener("change", () => {
    if (!mi) return; const next = defs[sel.value] || ""; const cur = mi.value.trim();
    if (!cur || cur === last || Object.values(defs).includes(cur)) mi.value = next; last = next;
  });
});
