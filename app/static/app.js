// ============================================================================
// Agentic AI Workbench — Frontend Application Architecture
// Senior Frontend Developer Implementation — Air-Gapped Enterprise Runtime
// Includes Additive Interactive P&ID (Piping & Instrumentation) Viewer Module
// ============================================================================

const appLayout = document.getElementById("app-layout");
const toggleLeftBtn = document.getElementById("toggle-left-sidebar");
const toggleRightBtn = document.getElementById("toggle-right-sidebar");

const directOutputBox = document.getElementById("direct-output-box");
const traceLogsEl = document.getElementById("trace-logs");
const stepCountBadge = document.getElementById("step-count-badge");
const modelListEl = document.getElementById("model-list");
const sessionListEl = document.getElementById("session-list");
const newChatBtn = document.getElementById("new-chat-btn");
const ollamaDot = document.getElementById("ollama-dot");
const ollamaStatusText = document.getElementById("ollama-status-text");
const ragStatusText = document.getElementById("rag-status-text");
const outputListEl = document.getElementById("output-list");
const ingestLogEl = document.getElementById("ingest-log");
const runBtn = document.getElementById("run-btn");
const clearBtn = document.getElementById("clear-btn");
const exportContainer = document.getElementById("export-container");
const exportDocxBtn = document.getElementById("export-docx-btn");
const exportMdBtn = document.getElementById("export-md-btn");
const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");

// P&ID Viewer Modal Elements
const openPidViewerBtn = document.getElementById("open-pid-viewer-btn");
const pidModal = document.getElementById("pid-modal");
const closePidModalBtn = document.getElementById("close-pid-modal-btn");
const pidDocSelect = document.getElementById("pid-doc-select");
const pidCanvasContainer = document.getElementById("pid-canvas-container");
const pidZoomInBtn = document.getElementById("pid-zoom-in-btn");
const pidZoomOutBtn = document.getElementById("pid-zoom-out-btn");
const pidZoomResetBtn = document.getElementById("pid-zoom-reset-btn");
const toggleSymbolsCb = document.getElementById("toggle-symbols-cb");
const toggleTextsCb = document.getElementById("toggle-texts-cb");

let isLeftCollapsed = false;
let isRightCollapsed = false;

let currentSessionId = null;
let currentStreamedText = "";
let lastTaskTitle = "Task_Summary";
let totalStepsCount = 0;

let currentPidZoom = 1.0;
let currentPidData = null;

// Track files generated during the CURRENT session only
const currentSessionOutputs = new Set();

// ---------------- Dual Sidebar Toggle Controls ----------------

if (toggleLeftBtn) {
  toggleLeftBtn.addEventListener("click", () => {
    isLeftCollapsed = !isLeftCollapsed;
    if (isLeftCollapsed) {
      appLayout.classList.add("left-collapsed");
      toggleLeftBtn.classList.add("active");
    } else {
      appLayout.classList.remove("left-collapsed");
      toggleLeftBtn.classList.remove("active");
    }
  });
}

if (toggleRightBtn) {
  toggleRightBtn.addEventListener("click", () => {
    isRightCollapsed = !isRightCollapsed;
    if (isRightCollapsed) {
      appLayout.classList.add("right-collapsed");
      toggleRightBtn.classList.add("active");
    } else {
      appLayout.classList.remove("right-collapsed");
      toggleRightBtn.classList.remove("active");
    }
  });
}

// ---------------- Interactive Visual P&ID Viewer Module ----------------

if (openPidViewerBtn) {
  openPidViewerBtn.addEventListener("click", () => {
    pidModal.style.display = "flex";
    loadPidDocumentList();
  });
}

if (closePidModalBtn) {
  closePidModalBtn.addEventListener("click", () => {
    pidModal.style.display = "none";
  });
}

async function loadPidDocumentList(preferredPidId = null) {
  if (!pidDocSelect) return;
  try {
    const res = await fetch("/api/pid/list");
    const docs = await res.json();
    const currentVal = pidDocSelect.value;
    pidDocSelect.innerHTML = '<option value="">Select P&ID Drawing...</option>';
    docs.forEach(d => {
      const opt = document.createElement("option");
      opt.value = d.pid_id;
      opt.textContent = `${d.filename} (${d.total_symbols} symbols, ${d.total_texts} tags)`;
      pidDocSelect.appendChild(opt);
    });

    if (docs.length > 0) {
      let targetId = docs[0].pid_id;
      if (preferredPidId && docs.some(d => d.pid_id === preferredPidId)) {
        targetId = preferredPidId;
      } else if (currentVal && docs.some(d => d.pid_id === currentVal)) {
        targetId = currentVal;
      }
      pidDocSelect.value = targetId;
      renderPidDrawing(targetId);
    }
  } catch (e) {}
}

if (pidDocSelect) {
  pidDocSelect.addEventListener("change", (e) => {
    if (e.target.value) renderPidDrawing(e.target.value);
  });
}

async function renderPidDrawing(pidId) {
  try {
    pidCanvasContainer.innerHTML = '<div class="pid-viewer-placeholder">Loading high-resolution P&ID drawing...</div>';
    const resData = await fetch(`/api/pid/${pidId}/data`);
    currentPidData = await resData.json();

    const imgUrl = `/api/pid/${pidId}/page/1`;
    const img = new Image();
    img.src = imgUrl;

    img.onload = () => {
      pidCanvasContainer.innerHTML = "";
      pidCanvasContainer.style.width = img.width + "px";
      pidCanvasContainer.style.height = img.height + "px";
      pidCanvasContainer.appendChild(img);

      renderPidOverlays();
    };
  } catch (e) {
    pidCanvasContainer.innerHTML = `<div class="pid-viewer-placeholder">Failed to render P&ID: ${e}</div>`;
  }
}

function renderPidOverlays(highlightTags = []) {
  if (!currentPidData || !currentPidData.pages || !currentPidData.pages.length) return;

  const existingOverlays = pidCanvasContainer.querySelectorAll(".pid-overlay-box");
  existingOverlays.forEach(el => el.remove());

  const page = currentPidData.pages[0];

  // Render Symbol Bounding Boxes
  if (toggleSymbolsCb.checked && page.symbols) {
    page.symbols.forEach(s => {
      const box = document.createElement("div");
      const [x1, y1, x2, y2] = s.bbox;
      const isHigh = highlightTags.some(t => t.toUpperCase() === (s.tag || "").toUpperCase() || t.toUpperCase() === s.id.toUpperCase());

      box.className = `pid-overlay-box ${isHigh ? "highlight" : ""}`;
      box.style.left = x1 + "px";
      box.style.top = y1 + "px";
      box.style.width = (x2 - x1) + "px";
      box.style.height = (y2 - y1) + "px";

      if (s.tag) {
        const tagLabel = document.createElement("div");
        tagLabel.className = "pid-overlay-tag";
        tagLabel.textContent = s.tag;
        box.appendChild(tagLabel);
      }

      box.title = `${s.type.toUpperCase()} [${s.tag || s.id}] (Conf: ${s.confidence})`;
      pidCanvasContainer.appendChild(box);
    });
  }
}

if (pidZoomInBtn) {
  pidZoomInBtn.addEventListener("click", () => {
    currentPidZoom = Math.min(currentPidZoom + 0.2, 3.0);
    pidCanvasContainer.style.transform = `scale(${currentPidZoom})`;
  });
}

if (pidZoomOutBtn) {
  pidZoomOutBtn.addEventListener("click", () => {
    currentPidZoom = Math.max(currentPidZoom - 0.2, 0.4);
    pidCanvasContainer.style.transform = `scale(${currentPidZoom})`;
  });
}

if (pidZoomResetBtn) {
  pidZoomResetBtn.addEventListener("click", () => {
    currentPidZoom = 1.0;
    pidCanvasContainer.style.transform = "scale(1.0)";
  });
}

if (toggleSymbolsCb) toggleSymbolsCb.addEventListener("change", () => renderPidOverlays());
if (toggleTextsCb) toggleTextsCb.addEventListener("change", () => renderPidOverlays());

// ---------------- Markdown & Code Renderer (Zero Emojis) ----------------

function escapeHtml(str) {
  if (typeof str !== "string") str = String(str);
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function renderFormattedMarkdown(rawText) {
  if (!rawText) return "";

  let text = rawText;

  // Code Blocks ```lang ... ```
  const codeBlockRegex = /```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g;
  text = text.replace(codeBlockRegex, (match, lang, code) => {
    const language = lang.trim() || "CODE";
    const escapedCode = escapeHtml(code.trim());
    const codeId = "code-" + Math.random().toString(36).substring(2, 9);

    return `
      <div class="code-container">
        <div class="code-bar">
          <span class="code-lang">CODE: ${escapeHtml(language.toUpperCase())}</span>
          <button type="button" class="copy-code-btn" onclick="copyCodeSnippet('${codeId}')">
            <svg class="btn-svg" viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            <span>Copy</span>
          </button>
        </div>
        <pre><code id="${codeId}" class="code-content">${escapedCode}</code></pre>
      </div>
    `;
  });

  // Inline Code `code`
  text = text.replace(/`([^`]+)`/g, (match, inlineCode) => {
    return `<code class="inline-code">${escapeHtml(inlineCode)}</code>`;
  });

  // Headers (#, ##, ###)
  text = text.replace(/^### (.*$)/gim, '<h4 class="md-h3">$1</h4>');
  text = text.replace(/^## (.*$)/gim, '<h3 class="md-h2">$1</h3>');
  text = text.replace(/^# (.*$)/gim, '<h2 class="md-h1">$1</h2>');

  // Bold & Italic
  text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');

  // Bullet Lists
  text = text.replace(/^\s*[-*]\s+(.*$)/gim, '<li class="md-li">$1</li>');
  text = text.replace(/(<li class="md-li">[\s\S]*?<\/li>)/gi, '<ul class="md-ul">$1</ul>');
  text = text.replace(/<\/ul>\s*<ul class="md-ul">/gi, '');

  // Line breaks outside code containers
  const parts = text.split(/(<div class="code-container">[\s\S]*?<\/div>)/gi);
  const formattedParts = parts.map(part => {
    if (part.startsWith('<div class="code-container">')) return part;
    return part.replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>');
  });

  return formattedParts.join('');
}

window.copyCodeSnippet = function(codeId) {
  const codeEl = document.getElementById(codeId);
  if (!codeEl) return;
  const text = codeEl.innerText || codeEl.textContent;
  navigator.clipboard.writeText(text).then(() => {
    const btn = codeEl.parentElement.parentElement.querySelector(".copy-code-btn");
    if (btn) {
      const orig = btn.innerHTML;
      btn.innerHTML = "<span>Copied</span>";
      setTimeout(() => { btn.innerHTML = orig; }, 2000);
    }
  });
};

function addTraceLogEntry(labelClass, labelText, bodyText) {
  const empty = traceLogsEl.querySelector(".trace-empty");
  if (empty) traceLogsEl.innerHTML = "";

  totalStepsCount++;
  stepCountBadge.textContent = `${totalStepsCount} Steps`;

  const entry = document.createElement("div");
  entry.className = "trace-entry";
  entry.innerHTML = `
    <div>
      <span class="trace-label ${labelClass}">${labelText}</span>
      <span style="color: var(--text-secondary); margin-left: 8px;">${escapeHtml(bodyText)}</span>
    </div>
  `;
  traceLogsEl.appendChild(entry);
  traceLogsEl.scrollTop = traceLogsEl.scrollHeight;
}

function fmtArgs(obj) {
  try {
    return JSON.stringify(obj, null, 0);
  } catch {
    return String(obj);
  }
}

// ---------------- Chat Sessions & History Management ----------------

async function refreshSessions() {
  if (!sessionListEl) return;
  try {
    const res = await fetch("/api/sessions");
    const sessions = await res.json();
    
    if (!sessions.length) {
      sessionListEl.innerHTML = '<div class="trace-empty">No saved chats yet.</div>';
      return;
    }

    sessionListEl.innerHTML = "";
    sessions.forEach(sess => {
      const row = document.createElement("div");
      const isActive = sess.id === currentSessionId;
      row.className = `session-item ${isActive ? "active" : ""}`;
      
      const timeStr = new Date(sess.updated_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      row.innerHTML = `
        <div class="session-info">
          <div class="session-title" title="${escapeHtml(sess.title)}">${escapeHtml(sess.title)}</div>
          <div class="session-time">${timeStr} · ${escapeHtml(sess.model || 'auto')}</div>
        </div>
        <button type="button" class="btn-del-session" title="Delete chat session">
          <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        </button>
      `;

      row.addEventListener("click", (e) => {
        if (e.target.closest(".btn-del-session")) return;
        loadSession(sess.id);
      });

      const delBtn = row.querySelector(".btn-del-session");
      if (delBtn) {
        delBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          deleteSessionItem(sess.id);
        });
      }

      sessionListEl.appendChild(row);
    });
  } catch (e) {}
}

async function loadSession(sessionId) {
  try {
    const res = await fetch(`/api/sessions/${sessionId}`);
    const sess = await res.json();
    if (sess.error) return;

    currentSessionId = sess.id;
    lastTaskTitle = sess.title || "Task_Summary";
    
    // Set prompt input
    const taskInput = document.getElementById("task-input");
    if (taskInput) taskInput.value = sess.task || "";

    // Set target model
    const modelSelect = document.getElementById("model-select");
    if (modelSelect && sess.model) modelSelect.value = sess.model;

    // Render output
    currentStreamedText = sess.output || "";
    if (currentStreamedText && currentStreamedText !== "Processing task...") {
      directOutputBox.innerHTML = renderFormattedMarkdown(currentStreamedText);
      exportContainer.style.display = "flex";
    } else {
      directOutputBox.innerHTML = '<div class="output-placeholder">No completed output recorded for this chat session.</div>';
      exportContainer.style.display = "none";
    }

    // Restore trace logs
    traceLogsEl.innerHTML = "";
    totalStepsCount = 0;
    if (sess.trace_logs && sess.trace_logs.length) {
      sess.trace_logs.forEach(log => {
        if (log.type === "routing") {
          addTraceLogEntry("route", "ROUTE", `Task: ${log.task_type} -> Model: ${log.model}`);
        } else if (log.type === "thinking") {
          addTraceLogEntry("call", "THINK", log.content);
        } else if (log.type === "tool_call") {
          addTraceLogEntry("call", `CALL: ${log.tool}`, fmtArgs(log.args));
        } else if (log.type === "tool_result") {
          addTraceLogEntry("result", `OBSERVE: ${log.tool}`, fmtArgs(log.result));
        }
      });
    } else {
      traceLogsEl.innerHTML = '<div class="trace-empty">Technical execution step logs will record here.</div>';
      stepCountBadge.textContent = "0 Steps";
    }

    // Restore session deliverables
    currentSessionOutputs.clear();
    if (sess.deliverables) {
      sess.deliverables.forEach(f => currentSessionOutputs.add(f));
    }
    refreshOutputs();
    refreshSessions();
  } catch (e) {}
}

async function deleteSessionItem(sessionId) {
  try {
    await fetch(`/api/sessions/${sessionId}`, { method: "DELETE" });
    if (currentSessionId === sessionId) {
      startNewChat();
    } else {
      refreshSessions();
    }
  } catch (e) {}
}

function startNewChat() {
  currentSessionId = `session_${Date.now()}`;
  currentStreamedText = "";
  lastTaskTitle = "Task_Summary";

  const taskInput = document.getElementById("task-input");
  if (taskInput) taskInput.value = "";

  directOutputBox.innerHTML = '<div class="output-placeholder">Submit a task or select a prompt above. The direct answer will stream below cleanly in real-time.</div>';
  traceLogsEl.innerHTML = '<div class="trace-empty">Technical execution step logs will record here.</div>';
  exportContainer.style.display = "none";
  totalStepsCount = 0;
  stepCountBadge.textContent = "0 Steps";

  currentSessionOutputs.clear();
  refreshOutputs();
  refreshSessions();
}

if (newChatBtn) {
  newChatBtn.addEventListener("click", startNewChat);
}

refreshSessions();

// ---------------- Status Polling & Model Registry ----------------

async function refreshStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();

    ollamaDot.className = "dot " + (data.ollama_running ? "on" : "off");
    ollamaStatusText.textContent = data.ollama_running ? "Ollama Connected" : "Ollama Offline";
    ragStatusText.textContent = `${data.rag_stats.total_chunks} Chunks Indexed`;

    const modelSelect = document.getElementById("model-select");
    const currentSel = modelSelect ? modelSelect.value : "auto";
    if (modelSelect) {
      modelSelect.innerHTML = '<option value="auto">Auto-detect (Smart Task Router)</option>';
    }

    modelListEl.innerHTML = "";
    data.registered_models.forEach((m) => {
      if (modelSelect && (m.role === "chat" || m.role === "vision")) {
        const opt = document.createElement("option");
        opt.value = m.name;
        opt.textContent = `${m.display_name} (${m.name}) ${m.pulled ? "" : "[not pulled]"}`;
        if (!m.pulled) opt.disabled = true;
        modelSelect.appendChild(opt);
      }

      const row = document.createElement("div");
      row.className = "model-row";
      row.innerHTML = `
        <span class="dot ${m.pulled ? "on" : "off"}"></span>
        <div class="model-meta">
          <div class="model-name">${escapeHtml(m.display_name)}</div>
          <div class="model-caps">${escapeHtml(m.capabilities.join(", "))}</div>
          <div class="model-vram">~${m.vram_gb} GB VRAM · ${m.pulled ? "ready" : "not pulled"}</div>
        </div>`;
      modelListEl.appendChild(row);
    });

    if (modelSelect && currentSel && Array.from(modelSelect.options).some(o => o.value === currentSel)) {
      modelSelect.value = currentSel;
    }
  } catch (e) {
    ollamaDot.className = "dot off";
    ollamaStatusText.textContent = "Backend Unreachable";
  }
}

refreshStatus();
setInterval(refreshStatus, 8000);

// ---------------- Current Chat Session Deliverables Only ----------------

async function refreshOutputs() {
  try {
    const res = await fetch("/api/outputs");
    const allFiles = await res.json();
    
    // Filter to ONLY files generated during the current active session
    const sessionFiles = allFiles.filter(f => currentSessionOutputs.has(f.filename));

    if (!sessionFiles.length) {
      outputListEl.innerHTML = '<div class="trace-empty">Current session deliverables will appear here.</div>';
      return;
    }

    outputListEl.innerHTML = "";
    sessionFiles.forEach((f) => {
      const row = document.createElement("div");
      row.className = "output-row";
      row.innerHTML = `
        <div class="output-meta">
          <span class="output-name" title="${escapeHtml(f.filename)}">${escapeHtml(f.filename)}</span>
          <span class="output-size">${f.size_kb} KB</span>
        </div>
        <a href="/outputs/${encodeURIComponent(f.filename)}" download>Download</a>`;
      outputListEl.appendChild(row);
    });
  } catch (e) {}
}

refreshOutputs();
setInterval(refreshOutputs, 6000);

// ---------------- Drag & Drop Ingestion ----------------

if (dropZone && fileInput) {
  dropZone.addEventListener("click", () => fileInput.click());

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files.length) {
      fileInput.files = e.dataTransfer.files;
      const name = fileInput.files[0].name;
      dropZone.querySelector(".drop-text").textContent = `Selected: ${name}`;
    }
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) {
      const name = fileInput.files[0].name;
      dropZone.querySelector(".drop-text").textContent = `Selected: ${name}`;
    }
  });
}

document.getElementById("upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!fileInput.files.length) return;

  const file = fileInput.files[0];
  const mode = document.getElementById("mode-select").value;
  const formData = new FormData();
  formData.append("file", file);

  const logEntry = document.createElement("div");
  logEntry.className = "entry";
  logEntry.textContent = `Uploading ${file.name}...`;
  ingestLogEl.prepend(logEntry);

  try {
    await fetch("/api/upload", { method: "POST", body: formData });
    logEntry.textContent = `Ingesting ${file.name}...`;

    if (mode === "pid" || file.name.toLowerCase().endsWith(".pdf")) {
      const params = new URLSearchParams({ filename: file.name, dpi: "300" });
      const pidRes = await fetch(`/api/pid/ingest?${params}`, { method: "POST" });
      const pidResult = await pidRes.json();

      if (pidResult.error) {
        logEntry.textContent = `Failed P&ID: ${file.name} - ${pidResult.error}`;
      } else {
        logEntry.textContent = `Ingested P&ID ${pidResult.filename} (${pidResult.total_symbols} symbols, ${pidResult.total_texts} tags)`;
        if (pidModal) {
          pidModal.style.display = "flex";
          loadPidDocumentList(pidResult.pid_id);
        }
      }
    } else {
      const params = new URLSearchParams({ filename: file.name });
      if (mode) params.append("mode", mode);
      const ingestRes = await fetch(`/api/ingest?${params}`, { method: "POST" });
      const result = await ingestRes.json();

      if (result.error) {
        logEntry.textContent = `Failed: ${file.name} - ${result.error}`;
      } else {
        logEntry.textContent = `Ingested ${result.source} (${result.chunks_indexed} chunks)`;
      }
    }
    refreshStatus();
  } catch (err) {
    logEntry.textContent = `Failed: ${file.name} - ${err}`;
  }
});

// ---------------- Quick Prompts ----------------

document.querySelectorAll(".chip").forEach(chip => {
  chip.addEventListener("click", () => {
    const prompt = chip.getAttribute("data-prompt");
    const input = document.getElementById("task-input");
    if (input) {
      input.value = prompt;
      input.focus();
    }
  });
});

// ---------------- Clear Workspace ----------------

clearBtn.addEventListener("click", () => {
  startNewChat();
});

// ---------------- Summary Export Handlers ----------------

async function handleExport(format) {
  if (!currentStreamedText) return;
  try {
    const res = await fetch("/api/export-summary", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: lastTaskTitle,
        content: currentStreamedText,
        format: format,
      }),
    });
    const data = await res.json();
    if (data.url && data.filename) {
      currentSessionOutputs.add(data.filename);
      const link = document.createElement("a");
      link.href = data.url;
      link.download = data.filename;
      link.click();
      refreshOutputs();
    }
  } catch (e) {
    alert("Export failed: " + e);
  }
}

exportDocxBtn.addEventListener("click", () => handleExport("docx"));
exportMdBtn.addEventListener("click", () => handleExport("md"));

// ---------------- WebSocket Event Streaming ----------------

let ws;
function connectWs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws/agent`);

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    handleAgentEvent(data);
  };

  ws.onclose = () => {
    setTimeout(connectWs, 1500);
  };
}
connectWs();

function handleAgentEvent(data) {
  if (data.session_id) {
    currentSessionId = data.session_id;
  }

  switch (data.type) {
    case "routing":
      addTraceLogEntry("route", "ROUTE", `Task: ${data.task_type} -> Model: ${data.model}`);
      refreshSessions();
      break;

    case "thinking":
      addTraceLogEntry("call", "THINK", data.content);
      break;

    case "tool_call":
      addTraceLogEntry("call", `CALL: ${data.tool}`, fmtArgs(data.args));
      if (data.args && data.args.filename) {
        currentSessionOutputs.add(data.args.filename);
      }
      break;

    case "tool_result":
      addTraceLogEntry("result", `OBSERVE: ${data.tool}`, fmtArgs(data.result));
      refreshOutputs();
      break;

    case "stream_chunk":
      currentStreamedText += data.chunk;
      directOutputBox.innerHTML = renderFormattedMarkdown(currentStreamedText);
      directOutputBox.scrollTop = directOutputBox.scrollHeight;
      break;

    case "final":
      if (data.content && !currentStreamedText) {
        currentStreamedText = data.content;
        directOutputBox.innerHTML = renderFormattedMarkdown(currentStreamedText);
      }
      runBtn.disabled = false;
      exportContainer.style.display = "flex";
      refreshOutputs();
      refreshSessions();
      break;

    case "error":
      addTraceLogEntry("error", "ERROR", data.content);
      directOutputBox.innerHTML += `<div style="color: var(--rose-accent); margin-top: 12px;"><strong>Execution Error:</strong> ${escapeHtml(data.content)}</div>`;
      runBtn.disabled = false;
      refreshSessions();
      break;
  }
}

document.getElementById("task-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = document.getElementById("task-input");
  const modelSelect = document.getElementById("model-select");
  const task = input.value.trim();
  const model = modelSelect ? modelSelect.value : "auto";
  if (!task) return;

  if (!currentSessionId) {
    currentSessionId = `session_${Date.now()}`;
  }

  lastTaskTitle = task.slice(0, 30).replace(/[^a-zA-Z0-9]/g, "_");
  currentStreamedText = "";
  directOutputBox.innerHTML = '<div class="output-placeholder">Processing task... Answer streaming in real-time...</div>';
  exportContainer.style.display = "none";
  runBtn.disabled = true;

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ task, model, session_id: currentSessionId }));
    setTimeout(refreshSessions, 300);
  } else {
    directOutputBox.innerHTML = '<div style="color: var(--rose-accent);">WebSocket connecting... Retrying task...</div>';
    runBtn.disabled = false;
  }
});

// ---------------- Privacy & Security Dashboard Modal Handlers ----------------

const openPrivacyDashboardBtn = document.getElementById("open-privacy-dashboard-btn");
const privacyDashboardModal = document.getElementById("privacy-dashboard-modal");
const closePrivacyModalBtn = document.getElementById("close-privacy-modal-btn");

async function loadPrivacyDashboardData() {
  try {
    const res = await fetch("/api/security/privacy-dashboard");
    const data = await res.json();

    const blockedCountEl = document.getElementById("privacy-blocked-count");
    if (blockedCountEl && data.stats) {
      blockedCountEl.textContent = data.stats.blocked_external_attempts || 0;
    }

    const checksContainer = document.getElementById("privacy-startup-checks");
    if (checksContainer && data.startup_check) {
      checksContainer.innerHTML = data.startup_check.checks.map(c => `
        <div class="check-item">
          <span class="check-icon" style="color: ${c.passed ? 'var(--emerald-accent)' : 'var(--rose-accent)'}">${c.passed ? '✓' : '✗'}</span>
          <span>${escapeHtml(c.name)}: ${escapeHtml(c.detail)}</span>
        </div>
      `).join("");
    }

    const compTable = document.getElementById("privacy-component-rows");
    if (compTable && data.components) {
      compTable.innerHTML = data.components.map(c => `
        <tr>
          <td><strong>${escapeHtml(c.name)}</strong></td>
          <td>${escapeHtml(c.type)}</td>
          <td><code>${escapeHtml(c.location)}</code></td>
          <td><span class="pill-green">${escapeHtml(c.status)}</span></td>
        </tr>
      `).join("");
    }

    const netLogs = document.getElementById("privacy-network-logs");
    if (netLogs && data.activity_log) {
      if (!data.activity_log.length) {
        netLogs.innerHTML = '<div class="log-entry">No external outbound network requests recorded. Local-Only Mode Active.</div>';
      } else {
        netLogs.innerHTML = data.activity_log.map(l => `
          <div class="log-entry" style="color: ${l.status === 'BLOCKED' ? 'var(--rose-accent)' : 'var(--emerald-accent)'}">
            ${l.timestamp} | ${escapeHtml(l.component)} &rarr; ${escapeHtml(l.host)}:${l.port} | ${l.protocol} ${l.direction} | ${l.status}
          </div>
        `).join("");
      }
    }
  } catch (e) {}
}

if (openPrivacyDashboardBtn && privacyDashboardModal) {
  openPrivacyDashboardBtn.addEventListener("click", () => {
    privacyDashboardModal.classList.remove("hidden");
    loadPrivacyDashboardData();
  });
}

if (closePrivacyModalBtn && privacyDashboardModal) {
  closePrivacyModalBtn.addEventListener("click", () => {
    privacyDashboardModal.classList.add("hidden");
  });
}

// Backdrop click and Escape key handlers to close all modals cleanly
window.addEventListener("click", (e) => {
  if (privacyDashboardModal && e.target === privacyDashboardModal) {
    privacyDashboardModal.classList.add("hidden");
    privacyDashboardModal.style.display = "none";
  }
  if (pidModal && e.target === pidModal) {
    pidModal.style.display = "none";
  }
});

window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    if (privacyDashboardModal) {
      privacyDashboardModal.classList.add("hidden");
      privacyDashboardModal.style.display = "none";
    }
    if (pidModal) {
      pidModal.style.display = "none";
    }
  }
});


