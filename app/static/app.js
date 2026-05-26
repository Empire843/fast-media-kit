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
    zone.querySelectorAll(".drop-zone-file").forEach((el) => el.remove());
    if (input.files?.length) {
      const d = document.createElement("div"); d.className = "drop-zone-file";
      const fileText = input.multiple ? `Đã chọn ${input.files.length} ảnh` : input.files[0].name;
      d.innerHTML = `<span>${fileText}</span><button type="button" class="remove-file">×</button>`;
      d.querySelector(".remove-file").addEventListener("click", (e) => {
        e.stopPropagation();
        input.value = "";
        d.remove();
        input.dispatchEvent(new Event("change", { bubbles: true }));
      });
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

/* ===== BACKGROUND REMOVER BATCH PROCESSING ===== */
const bgImagesInput = document.getElementById("bg-images-input");
const bgSelectedList = document.getElementById("bg-selected-list");
const bgRemoveForm = document.getElementById("bg-remove-form");
const bgSubmitBtn = document.getElementById("bg-submit-btn");

if (bgImagesInput && bgSelectedList) {
  bgImagesInput.addEventListener("change", () => {
    if (!bgImagesInput.files || !bgImagesInput.files.length) {
      bgSelectedList.className = "sheet-list-empty";
      bgSelectedList.innerHTML = "No images selected.";
      return;
    }
    bgSelectedList.className = "sheet-picker";
    let html = `<strong>Ảnh đã chọn (${bgImagesInput.files.length})</strong>`;
    html += `<div class="file-list" style="max-height: 150px; overflow-y: auto;">`;
    for (let i = 0; i < bgImagesInput.files.length; i++) {
      const file = bgImagesInput.files[i];
      const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
      html += `
        <div class="file-row" style="padding: 6px 10px; margin-top: 4px;">
          <span style="font-size: 12px; font-weight: 500; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">${file.name}</span>
          <strong style="font-size: 11px; color: var(--muted);">${sizeMB} MB</strong>
        </div>
      `;
    }
    html += `</div>`;
    bgSelectedList.innerHTML = html;
  });
}

if (bgRemoveForm && bgSubmitBtn) {
  bgRemoveForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!bgImagesInput.files || !bgImagesInput.files.length) return;

    const files = bgImagesInput.files;
    const target = document.getElementById("background-result");
    if (!target) return;

    // Build the container HTML
    target.innerHTML = `
      <div class="notice loading">
        <strong id="bg-progress-title">Đang khởi tạo xử lý...</strong>
        <p id="bg-progress-desc">Đang chuẩn bị gửi ${files.length} ảnh lên máy chủ...</p>
      </div>
      <div class="btn-row" id="bg-download-all-container" style="margin-top: 12px; display: none;"></div>
      <div class="image-results" id="bg-results-grid" style="margin-top: 16px;"></div>
      <details class="log-panel" open style="margin-top: 16px;">
        <summary>Nhật ký xử lý (Live Log)</summary>
        <pre id="bg-live-log" style="max-height: 200px; overflow-y: auto; padding: 10px; font-size: 11px; color: var(--text2); background: var(--bg); border-top: 1px solid var(--line); margin: 0; font-family: monospace;"></pre>
      </details>
    `;

    const progTitle = document.getElementById("bg-progress-title");
    const progDesc = document.getElementById("bg-progress-desc");
    const grid = document.getElementById("bg-results-grid");
    const liveLog = document.getElementById("bg-live-log");
    const downloadAllContainer = document.getElementById("bg-download-all-container");

    const appendLog = (msg) => {
      const now = new Date().toLocaleTimeString();
      liveLog.textContent += `[${now}] ${msg}\n`;
      liveLog.scrollTop = liveLog.scrollHeight;
    };

    appendLog(`Bắt đầu xử lý hàng loạt ${files.length} ảnh...`);

    // Helper function to safely escape filename for DOM ID
    const getCardId = (name) => "bg-card-" + name.replace(/[^a-zA-Z0-9]/g, "_");

    // Populate placeholder cards in grid
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const card = document.createElement("div");
      card.className = "image-card";
      card.id = getCardId(file.name);
      card.innerHTML = `
        <div style="aspect-ratio: 1; display: grid; place-items: center; border-radius: 6px; background: var(--bg); border: 1px dashed var(--line); position: relative; overflow: hidden; padding: 10px;">
          <div style="width: 24px; height: 24px; border: 2.5px solid var(--line); border-top-color: var(--b1); border-radius: 50%; animation: spin 1s linear infinite;"></div>
          <span style="font-size: 10px; color: var(--muted); position: absolute; bottom: 8px;">Đang chờ luồng...</span>
        </div>
        <div style="font-size: 11px; font-weight: 600; color: var(--text2); margin-top: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; text-align: center;" title="${file.name}">
          ${file.name}
        </div>
      `;
      grid.appendChild(card);
    }

    // Disable submit
    bgSubmitBtn.disabled = true;
    const t0 = Date.now();

    try {
      const fd = new FormData(bgRemoveForm);
      const res = await fetch(bgRemoveForm.action, { method: "POST", body: fd });
      
      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let totalImages = files.length;
      let finishedImages = 0;

      progTitle.textContent = "Đang xử lý tách nền...";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop(); // Keep partial line

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith("data: ")) continue;

          try {
            const data = JSON.parse(trimmed.slice(6));
            
            if (data.event === "start") {
              appendLog(`Đã kết nối máy chủ thành công. Job ID: ${data.job_id}`);
              progDesc.textContent = `Tiến trình: 0 / ${data.total} ảnh đã hoàn thành`;
              totalImages = data.total;
            } 
            else if (data.event === "progress") {
              finishedImages++;
              const result = data.result;
              const cardId = getCardId(result.filename);
              const card = document.getElementById(cardId);
              const duration = ((Date.now() - t0) / 1000).toFixed(1);

              progDesc.textContent = `Tiến trình: ${finishedImages} / ${totalImages} ảnh đã hoàn thành (${duration}s)`;

              if (result.status === "success") {
                appendLog(`✓ Thành công: ${result.filename} (đã tách nền)`);
                if (card) {
                  const imageUrl = `/files/processed/${result.job_id}/${result.output_name}`;
                  card.innerHTML = `
                    <div class="transparent-bg" style="aspect-ratio: 1; display: grid; place-items: center; border-radius: 6px; overflow: hidden; border: 1px solid var(--line); position: relative; box-shadow: inset 0 0 10px rgba(0,0,0,0.05);">
                      <img src="${imageUrl}" style="width: 100%; height: 100%; object-fit: contain; display: block;" />
                      <span style="position: absolute; top: 4px; right: 4px; background: var(--success); color: white; border-radius: 50%; width: 18px; height: 18px; display: grid; place-items: center; font-size: 10px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">✓</span>
                    </div>
                    <div style="font-size: 11px; font-weight: 600; color: var(--text); margin-top: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; text-align: center;" title="${result.filename}">
                      ${result.filename}
                    </div>
                    <a href="${imageUrl}" download="${result.output_name}" class="btn-download-single" style="display: flex; align-items: center; justify-content: center; gap: 4px; margin-top: 6px; color: var(--b1); font-size: 11px; font-weight: 700; text-decoration: none;">
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="width: 12px; height: 12px;">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="7 10 12 15 17 10" />
                        <line x1="12" y1="15" x2="12" y2="3" />
                      </svg>
                      Tải ảnh (.PNG)
                    </a>
                  `;
                }
              } 
              else {
                appendLog(`✗ Thất bại: ${result.filename}. Lỗi: ${result.error}`);
                if (card) {
                  card.innerHTML = `
                    <div style="aspect-ratio: 1; display: grid; place-items: center; border-radius: 6px; background: rgba(220,38,38,.06); border: 1px solid var(--danger); position: relative; padding: 8px; text-align: center;">
                      <span style="color: var(--danger); font-size: 24px; font-weight: bold;">✗</span>
                      <span style="font-size: 9px; color: var(--danger); overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;" title="${result.error}">${result.error}</span>
                    </div>
                    <div style="font-size: 11px; font-weight: 600; color: var(--danger); margin-top: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; text-align: center;" title="${result.filename}">
                      ${result.filename}
                    </div>
                    <div style="font-size: 11px; font-weight: 600; color: var(--danger); margin-top: 4px; text-align: center;">Lỗi xử lý</div>
                  `;
                }
              }
            } 
            else if (data.event === "complete") {
              const duration = ((Date.now() - t0) / 1000).toFixed(1);
              appendLog(`✓ Hoàn thành toàn bộ phiên làm việc. Tổng thời gian: ${duration} giây.`);
              
              const noticeDiv = target.querySelector(".notice");
              if (noticeDiv) {
                noticeDiv.className = "notice success";
                progTitle.textContent = "Hoàn thành tách nền!";
                progDesc.textContent = `Đã hoàn tất xử lý ${finishedImages} ảnh trong ${duration} giây.`;
              }

              if (data.zip_url) {
                appendLog(`✓ Đã tạo thành công gói nén ZIP chứa tất cả các ảnh tách nền.`);
                downloadAllContainer.style.display = "block";
                downloadAllContainer.innerHTML = `
                  <a href="${data.zip_url}" class="btn btn-primary" style="text-decoration: none; width: 100%; display: flex; align-items: center; justify-content: center; gap: 8px;">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="width: 16px; height: 16px;">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="7 10 12 15 17 10" />
                      <line x1="12" y1="15" x2="12" y2="3" />
                    </svg>
                    Tải về toàn bộ ảnh (.ZIP)
                  </a>
                `;
              }
            } 
            else if (data.event === "error") {
              throw new Error(data.message);
            }
          } catch (jsonErr) {
            console.error("JSON parse error:", jsonErr, trimmed);
          }
        }
      }
    } catch (err) {
      appendLog(`✗ Có lỗi xảy ra trong quá trình xử lý: ${err.message}`);
      target.innerHTML = `<div class="notice error"><strong>Lỗi xử lý hàng loạt</strong><p>${err.message}</p></div>`;
    } finally {
      bgSubmitBtn.disabled = false;
    }
  });
}


/* ===== MARKDOWN PREVIEW: WORD COUNTER + CLEAR + COPY HTML ===== */
(function () {
  const ta      = document.getElementById('markdown-text');
  const counter = document.getElementById('md-word-count');
  const clearBtn = document.getElementById('md-clear-btn');
  const copyBtn  = document.getElementById('md-copy-html-btn');

  if (ta && counter) {
    const update = () => {
      const text  = ta.value.trim();
      const words = text ? text.split(/\s+/).length : 0;
      const chars = ta.value.length;
      counter.textContent = `${words} từ · ${chars} ký tự`;
    };
    ta.addEventListener('input', update);
    update();
  }

  if (ta && clearBtn) {
    clearBtn.addEventListener('click', () => {
      ta.value = '';
      ta.dispatchEvent(new Event('input'));
      ta.focus();
    });
  }

  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      const previewEl = document.getElementById('markdown-preview-result');
      if (!previewEl) return;
      const outputEl = previewEl.querySelector('.markdown-preview-output');
      const html = outputEl ? outputEl.innerHTML : '';
      if (!html) return;
      navigator.clipboard.writeText(html).then(() => {
        const prevHTML = copyBtn.innerHTML;
        copyBtn.classList.add('copied');
        copyBtn.textContent = '✓ Đã sao chép!';
        setTimeout(() => { copyBtn.innerHTML = prevHTML; copyBtn.classList.remove('copied'); }, 1800);
      });
    });
  }
})();

/* ===== TEXT COMPARE: LINE COUNTERS ===== */
(function () {
  const makeCounter = (taId, elId) => {
    const ta = document.getElementById(taId);
    const el = document.getElementById(elId);
    if (!ta || !el) return;
    const update = () => {
      const n = ta.value ? ta.value.split('\n').length : 0;
      el.textContent = `${n} dòng`;
    };
    ta.addEventListener('input', update);
    update();
  };
  makeCounter('text-compare-a', 'cmp-a-count');
  makeCounter('text-compare-b', 'cmp-b-count');
})();
