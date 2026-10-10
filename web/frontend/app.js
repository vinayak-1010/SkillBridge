// SkillBridge web frontend.
//
// This is a thin client over the SkillBridge API (web/api/main.py). It does
// not run any model itself: it calls /api/skills, /api/validate and
// /api/run on whatever API base URL the user points it at (default
// http://localhost:8000, i.e. their own machine running Ollama).

const els = {
  apiUrl: document.getElementById("apiUrl"),
  connectBtn: document.getElementById("connectBtn"),
  statusDot: document.getElementById("statusDot"),
  statusText: document.getElementById("statusText"),
  skillList: document.getElementById("skillList"),
  taskInput: document.getElementById("taskInput"),
  modelInput: document.getElementById("modelInput"),
  maxStepsInput: document.getElementById("maxStepsInput"),
  budgetInput: document.getElementById("budgetInput"),
  runBtn: document.getElementById("runBtn"),
  runSpinner: document.getElementById("runSpinner"),
  traceLog: document.getElementById("traceLog"),
  finalAnswer: document.getElementById("finalAnswer"),
};

function apiBase() {
  return els.apiUrl.value.trim().replace(/\/+$/, "");
}

function setStatus(ok, text) {
  els.statusDot.className = "status-dot " + (ok === null ? "unknown" : ok ? "ok" : "bad");
  els.statusText.textContent = text;
}

async function connect() {
  setStatus(null, "connecting...");
  try {
    const res = await fetch(`${apiBase()}/api/health`, { method: "GET" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.ollama_reachable) {
      setStatus(true, "connected · Ollama reachable");
    } else {
      setStatus(true, "connected · Ollama NOT reachable (start Ollama)");
    }
    await loadSkills();
  } catch (err) {
    setStatus(false, `cannot reach API (${err.message})`);
    els.skillList.innerHTML = `<p class="placeholder">Could not load skills: ${escapeHtml(err.message)}</p>`;
  }
}

async function loadSkills() {
  els.skillList.innerHTML = `<p class="placeholder">Loading...</p>`;
  try {
    const res = await fetch(`${apiBase()}/api/skills`);
    const skills = await res.json();
    if (!skills.length) {
      els.skillList.innerHTML = `<p class="placeholder">No skills found on the server.</p>`;
      return;
    }
    els.skillList.innerHTML = skills
      .map(
        (s) => `
        <div class="skill-card">
          <div class="name">${escapeHtml(s.name)}</div>
          <div class="desc">${escapeHtml(s.description)}</div>
        </div>`
      )
      .join("");
  } catch (err) {
    els.skillList.innerHTML = `<p class="placeholder">Could not load skills: ${escapeHtml(err.message)}</p>`;
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function appendTraceEvent(event) {
  if (els.traceLog.querySelector(".placeholder")) {
    els.traceLog.innerHTML = "";
  }
  const kind = event.kind || "info";
  const div = document.createElement("div");
  div.className = `trace-event kind-${kind}`;

  let body = "";
  switch (kind) {
    case "routing":
      body = event.message || "";
      break;
    case "routed":
      body = `routed to skill: ${event.skill}`;
      break;
    case "model":
      body = `model step ${event.step} (attempt ${event.attempt}) · ${event.tokens} tokens\n${truncate(event.raw, 400)}`;
      break;
    case "action":
      body = `action: ${JSON.stringify(event.action)}`;
      break;
    case "observation":
      body = `observation (${event.tool}): ${truncate(event.output, 400)}`;
      break;
    case "tool_error":
    case "sandbox_block":
      body = `${kind}: ${event.error}`;
      break;
    case "verify_fail":
      body = `verify failed: ${event.hint}`;
      break;
    case "retries_exhausted":
      body = `retries exhausted at step ${event.step}: ${event.hint || ""}`;
      break;
    case "budget_exceeded":
      body = `token budget exceeded (used ${event.used})`;
      break;
    case "max_steps":
      body = `reached max steps (used ${event.used} tokens)`;
      break;
    case "finish":
      body = `finished at step ${event.step}: ${truncate(event.answer, 300)}`;
      break;
    case "error":
      body = event.message || "unknown error";
      break;
    default:
      body = JSON.stringify(event);
  }

  div.innerHTML = `<span class="kind">${escapeHtml(kind)}</span>${escapeHtml(body)}`;
  els.traceLog.appendChild(div);
  els.traceLog.scrollTop = els.traceLog.scrollHeight;
}

function truncate(str, n) {
  if (!str) return "";
  return str.length > n ? str.slice(0, n) + "…" : str;
}

async function runTask() {
  const task = els.taskInput.value.trim();
  if (!task) {
    els.taskInput.focus();
    return;
  }

  els.runBtn.disabled = true;
  els.runSpinner.classList.remove("hidden");
  els.traceLog.innerHTML = "";
  els.finalAnswer.innerHTML = `<p class="placeholder">Running…</p>`;

  const payload = {
    task,
    model: els.modelInput.value.trim() || "qwen3:1.7b",
    max_steps: parseInt(els.maxStepsInput.value, 10) || 8,
    token_budget: parseInt(els.budgetInput.value, 10) || 6000,
  };

  try {
    const res = await fetch(`${apiBase()}/api/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok || !res.body) {
      throw new Error(`HTTP ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE frames are separated by a blank line; each frame's payload is
      // on a line prefixed with "data: ".
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        const line = frame.split("\n").find((l) => l.startsWith("data: "));
        if (!line) continue;
        const event = JSON.parse(line.slice(6));
        appendTraceEvent(event);
        if (event.kind === "done") {
          renderFinalAnswer(event);
        } else if (event.kind === "error") {
          els.finalAnswer.innerHTML = `<p class="placeholder">Error: ${escapeHtml(event.message)}</p>`;
        }
      }
    }
  } catch (err) {
    appendTraceEvent({ kind: "error", message: err.message });
    els.finalAnswer.innerHTML = `<p class="placeholder">Error: ${escapeHtml(err.message)}</p>`;
  } finally {
    els.runBtn.disabled = false;
    els.runSpinner.classList.add("hidden");
  }
}

function renderFinalAnswer(event) {
  const status = event.finished ? "finished" : event.partial ? "partial" : "stopped";
  els.finalAnswer.innerHTML = `
    <div>${escapeHtml(event.answer || "(no answer)")}</div>
    <div class="meta">[${status}] steps=${event.steps} tokens=${event.tokens_used}</div>
  `;
}

els.connectBtn.addEventListener("click", connect);
els.runBtn.addEventListener("click", runTask);
els.taskInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") runTask();
});

// Try connecting automatically on load (defaults to localhost).
connect();
