import { Terminal } from "/vendor/xterm/lib/xterm.mjs";
import { FitAddon } from "/vendor/addon-fit/lib/addon-fit.mjs";

const el = id => document.getElementById(id);
const titles = { workspace: "Experiment workspace", research: "Research library", runs: "Run comparison" };
const model = { state: null, candidates: [], events: [], view: "workspace", inspected: "", busy: null };
const words = value => String(value ?? "—").replaceAll("_", " ");
const percent = value => (Number(value) * 100).toFixed(1) + "%";
const metric = item => {
  const m = item?.metric;
  return m?.value == null ? "Unmeasured" : m.unit === "fraction" ? percent(m.value) : m.value + " " + m.unit;
};
const reference = item => item.result_id + ":" + item.version;

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text != null) element.textContent = text;
  if (className) element.className = className;
  return element;
}

function button(label, action, className = "secondary") {
  const result = node("button", label, className);
  result.addEventListener("click", action);
  return result;
}

function details(target, title, rows) {
  const section = node("div", null, "detail");
  section.append(node("h3", title));
  const dl = node("dl");
  for (const [field, value] of rows) dl.append(node("dt", words(field)), node("dd", value ?? "—"));
  section.append(dl);
  target.append(section);
  return section;
}

async function request(path, body) {
  const response = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(typeof error.detail === "string" ? words(error.detail) : "Request failed (" + response.status + ")");
  }
  return response.json();
}

function showError(error) {
  el("error").hidden = !error;
  el("error").textContent = error?.message ?? "";
}

function show(view) {
  model.view = view;
  for (const tab of document.querySelectorAll("[data-view]")) {
    document.getElementById(tab.dataset.view).hidden = tab.dataset.view !== view;
    if (tab.dataset.view === view) tab.setAttribute("aria-current", "page");
    else tab.removeAttribute("aria-current");
  }
  el("title").textContent = titles[view];
  if (view === "workspace") fitTerminal();
}

function currentDecision() {
  return model.state?.decisions[0];
}

function labels(row) {
  const decision = currentDecision();
  const key = reference(row.result);
  if (decision?.used_refs.some(r => reference(r) === key)) return ["Used", "use"];
  if (decision?.skipped_jobs.some(job => job.refs.some(r => reference(r) === key))) return ["Avoided", "avoid"];
  if (row.applicability?.status === "mismatch") return ["Doesn’t fit", "mismatch"];
  if (row.applicability?.status === "applies") return ["Fits", "use"];
  return ["Related", ""];
}

function row(item, label, style, note) {
  const entry = button("", () => inspect(item), "entry " + (style || ""));
  const metadata = node("span");
  metadata.append(node("strong", item.hypothesis));
  metadata.append(node("small", [metric(item), item.author_id, "v" + item.version,
    item.artifact && "GridFS checkpoint", note].filter(Boolean).join(" · ")));
  entry.append(metadata, node("span", label, "tag " + (style || "")));
  return entry;
}

function renderCandidates(target, rows, empty) {
  target.replaceChildren(...(rows.length ? rows.map(candidate => {
    const [label, style] = labels(candidate);
    const mismatches = candidate.applicability?.mismatches.map(m => words(m.field) + " " + m.found + " → " + m.wanted);
    return row(candidate.result, label, style, mismatches?.length ? mismatches.join(", ") : "");
  }) : [node("p", empty, "empty")]));
}

async function inspect(item) {
  const token = model.inspected = reference(item);
  const panel = el("inspector");
  panel.replaceChildren(node("h2", item.hypothesis));
  details(panel, "Measurement", [
    ["metric", item.metric.name], ["value", metric(item)], ["execution", item.execution], ["outcome", item.direction],
  ]);
  details(panel, "Conditions", Object.entries({fixture_revision: item.fixture_revision, ...item.conditions}));
  details(panel, "Configuration", Object.entries(item.configuration));
  details(panel, "Source", [["record", item.source.record], ["author", item.author_id],
    ["agent", item.source.source_agent], ["version", item.version], ["result", item.result_id]]);
  if (item.artifact) {
    const block = details(panel, "Stored weights", [["file", item.artifact.filename],
      ["size", (item.artifact.bytes / (1024 * 1024)).toFixed(1) + " MiB"], ["SHA-256", item.artifact.sha256]]);
    if (item.status !== "expired") {
      const link = node("a", "Download checkpoint");
      link.href = "/api/results/" + item.result_id + "/artifact?version=" + item.version;
      block.append(link);
    }
  }
  try {
    const history = await request("/api/results/" + item.result_id + "/history");
    if (token !== model.inspected) return;
    const evidence = history.versions.find(version => version.version === item.version)?.evidence?.data;
    const reproduce = evidence?.reproduce;
    if (reproduce) {
      const block = details(panel, "Reproduction", [["fixture SHA-256", reproduce.fixture_sha256],
        ...Object.entries(reproduce.versions || {})]);
      block.append(node("pre", reproduce.command));
      if (evidence.input_checkpoint) {
        const input = evidence.input_checkpoint;
        const link = node("a", "Download original input checkpoint");
        link.href = "/api/results/" + input.result_id + "/artifact?version=" + input.version;
        block.append(link);
      }
    }
    details(panel, "Versions", history.versions.map(v => ["v" + v.version, v.state]));
  } catch (error) {
    if (token === model.inspected) panel.append(node("p", error.message, "error"));
  }
}

async function act(decision, action) {
  model.busy = { id: decision.decision_id, action };
  showError(null);
  renderPlan();
  try {
    const response = await request("/api/decisions/" + decision.decision_id + "/" + action, {});
    if (response.status === "executed") {
      model.state.decisions = model.state.decisions.map(item =>
        item.decision_id === response.decision_id ? response : item);
      render();
      show("runs");
    }
  } catch (error) {
    showError(error);
  } finally {
    model.busy = null;
    await refresh();
  }
}

function renderPlan() {
  const decision = currentDecision();
  const target = el("decision");
  const busy = model.busy?.id === decision?.decision_id;
  el("plan-status").replaceChildren();
  target.replaceChildren();
  const stage = decision?.status === "executed" ? 2 :
    ["pending", "approved", "running"].includes(decision?.status) ? 1 : 0;
  [...document.querySelectorAll(".workflow span")].forEach((span, index) => {
    if (index === stage) span.setAttribute("aria-current", "step");
    else span.removeAttribute("aria-current");
  });
  if (!decision) {
    target.append(node("p", "Ask an agent to submit a plan. Its recommendation and citations will appear here.", "empty"));
    return;
  }
  const status = busy && model.busy.action === "run" && decision.status !== "running" &&
    decision.status !== "executed" ? "Starting run" : words(decision.status);
  el("plan-status").append(node("span", status, "tag"));
  const content = node("div", null, "decision-body");
  content.append(node("h3", decision.job_id + " · " + decision.model), node("p", decision.reason));
  if (decision.abort_reason) content.append(node("p", words(decision.abort_reason), "error"));
  for (const skipped of decision.skipped_jobs) {
    content.append(node("p", "Avoid " + skipped.job_id + " · " + skipped.reason, "muted"));
  }
  const actions = node("div", null, "actions");
  for (const ref of decision.used_refs) {
    const finding = model.state.findings.find(item => reference(item) === reference(ref));
    if (finding) actions.append(button("Inspect " + ref.result_id.slice(0, 8) + " · v" + ref.version, () => inspect(finding)));
  }
  if (decision.status === "pending" || decision.status === "approved") {
    const run = button("Run plan", () => act(decision, "run"), "primary");
    run.disabled = busy;
    actions.append(run);
    if (decision.status === "pending") {
      const reject = button("Not now", () => act(decision, "reject"));
      reject.disabled = busy;
      actions.append(reject);
    }
  } else if (decision.status === "executed") {
    actions.append(button("View results", () => show("runs")));
  } else if (decision.status === "running") {
    content.append(node("p", "Training is running. The measured result will appear here when it finishes.", "muted"));
  }
  content.append(actions);
  target.append(content);
}

function runCard(receipt, label) {
  const card = node("div", null, "panel run-summary");
  card.append(node("h2", label), node("p", metric(receipt), "metric-main"));
  if (receipt.metric?.unit === "fraction") {
    const bar = node("div", null, "bar");
    const fill = node("span");
    fill.style.width = Math.min(100, Math.max(0, receipt.metric.value * 100)) + "%";
    bar.append(fill);
    card.append(bar);
  }
  card.append(node("p", [receipt.metric?.name, receipt.elapsed_seconds != null && receipt.elapsed_seconds + " s",
    receipt.configuration?.device, receipt.configuration?.initialization].filter(Boolean).join(" · "), "muted"));
  if (receipt.input_checkpoint) {
    card.append(node("p", "Reused " + receipt.input_checkpoint.filename + " · v" + receipt.input_checkpoint.version));
  }
  if (receipt.published) {
    const finding = model.state.findings.find(item => reference(item) === reference(receipt.published));
    if (finding) card.append(button("Inspect published result", () => inspect(finding)));
  }
  return card;
}

function render() {
  if (!model.state) return;
  const { project, health, streams, defaults, codex_available, findings, decisions, baseline } = model.state;
  el("project").textContent = project;
  el("connection").textContent = health.atlas === "ok" ? "Index " + words(health.index).toLowerCase() : "Unavailable";
  el("atlas-dot").classList.toggle("online", health.atlas === "ok");
  el("stream-status").textContent = streams.results;
  el("prompt").textContent = defaults.question || "Ask about past experiments, or open the research library.";
  el("match").disabled = !defaults.conditions;
  el("terminal-toggle").disabled = !terminalSocket && !codex_available;
  if (!codex_available) el("prompt").textContent = "Install and sign in to Codex to open a terminal.";
  el("finding-count").textContent = findings.length + " records";
  el("findings").replaceChildren(...(findings.length ? findings.map(item =>
    row(item, item.status === "expired" ? "Expired" : item.execution === "completed" ? words(item.direction) : words(item.execution),
      item.status === "expired" ? "" : item.direction)) : [node("p", "No experiments have been published yet.", "empty")]));
  const latest = currentDecision();
  const remembered = latest?.candidates.flatMap(candidate => {
    const result = findings.find(item => reference(item) === reference(candidate.ref));
    return result ? [{ ...candidate, result }] : [];
  }) || [];
  renderCandidates(el("candidates"), model.candidates.length ? model.candidates : remembered,
    "Results from the agent’s semantic search will appear here.");
  renderPlan();
  const receipts = decisions.filter(d => d.receipt);
  el("comparisons").replaceChildren(
    ...(baseline ? [runCard(baseline, "Independent baseline")] : []),
    ...receipts.map(d => runCard(d.receipt, d.job_id + " · " + d.model)),
    ...(receipts.length ? [] : [node("p", "A submitted plan appears here after training completes.", "empty")]),
  );
}

let refreshing = false;
let refreshAgain = false;
async function refresh() {
  if (refreshing) {
    refreshAgain = true;
    return;
  }
  refreshing = true;
  try {
    model.state = await request("/api/state");
    render();
  } catch (error) {
    showError(error);
  } finally {
    refreshing = false;
    if (refreshAgain) {
      refreshAgain = false;
      void refresh();
    }
  }
}

let terminalSocket, consoleView, fit;
function fitTerminal() {
  if (!consoleView || el("workspace").hidden) return;
  fit.fit();
  if (terminalSocket?.readyState === WebSocket.OPEN) {
    terminalSocket.send(JSON.stringify({ size: [consoleView.rows, consoleView.cols] }));
  }
}

function closeTerminal() {
  if (terminalSocket) terminalSocket.close();
  terminalSocket = null;
  consoleView?.dispose();
  consoleView = null;
  el("terminal-shell").hidden = true;
  el("terminal-toggle").textContent = "Open terminal";
  el("send-prompt").hidden = true;
}

function openTerminal() {
  if (terminalSocket) return closeTerminal();
  el("terminal-shell").hidden = false;
  el("terminal-toggle").textContent = "Close terminal";
  el("terminal-status").textContent = "Starting Codex";
  consoleView = new Terminal({ fontSize: 12, fontFamily: "IBM Plex Mono, monospace", cursorBlink: true,
    theme: { background: "#0e211a", foreground: "#dbede2", cursor: "#7bdcaf" } });
  fit = new FitAddon();
  consoleView.loadAddon(fit);
  consoleView.open(el("terminal"));
  const socket = terminalSocket = new WebSocket(
    (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/terminal/codex");
  socket.addEventListener("open", () => {
    if (terminalSocket !== socket) return;
    fitTerminal();
    consoleView.focus();
    el("terminal-status").textContent = "Codex · Precedent MCP";
    el("send-prompt").hidden = !model.state?.defaults.question;
  });
  socket.addEventListener("message", event => { if (terminalSocket === socket) consoleView.write(event.data); });
  socket.addEventListener("close", () => {
    if (terminalSocket !== socket) return;
    el("terminal-status").textContent = "Terminal disconnected";
    el("send-prompt").hidden = true;
  });
  consoleView.onData(input => {
    if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ input }));
  });
}

el("terminal-toggle").addEventListener("click", openTerminal);
el("send-prompt").addEventListener("click", () => {
  const question = model.state?.defaults.question;
  if (!question || terminalSocket?.readyState !== WebSocket.OPEN) return;
  const guidance = " Use only Precedent MCP. Read experiment_profile, search with its task conditions, and submit propose_plan for review. Put supporting evidence in used_refs, failed jobs in skipped_jobs, and mismatches in rejected_candidates. Cite exact versions. Leave execution to the Run plan button.";
  consoleView.focus();
  consoleView.paste(question + guidance);
});
window.addEventListener("resize", fitTerminal);
document.querySelectorAll("[data-view]").forEach(tab => tab.addEventListener("click", () => show(tab.dataset.view)));
el("open-research").addEventListener("click", () => show("research"));
el("search").addEventListener("submit", async event => {
  event.preventDefault();
  showError(null);
  try {
    const response = await request("/api/search", { question: el("query").value,
      conditions: el("match").checked ? model.state.defaults.conditions : null });
    renderCandidates(el("search-results"), response.candidates, "No current matching evidence was returned.");
  } catch (error) {
    showError(error);
  }
});
function showSearch(payload) {
  if (!model.state) return;
  model.candidates = payload.candidates;
  render();
}

function showActivity(record) {
  if (record.command === "aggregate" && record.collection === "results" &&
      !record.shape.pipeline?.some(stage => stage.$lookup)) return;
  model.events.unshift(record);
  model.events.length = Math.min(20, model.events.length);
  const lines = model.events.map(item => button(
    [item.command, item.collection, item.ok ? item.ms + " ms" : "failed"].filter(Boolean).join(" · "), () => {
      model.inspected = "";
      const panel = el("inspector");
      panel.replaceChildren(node("h2", "MongoDB " + item.command), node("pre", JSON.stringify(item.shape, null, 2)));
    }, ""));
  el("event-lines").replaceChildren(...lines);
}

if (location.protocol === "https:") {
  let session, after = 0;
  async function pollActivity() {
    try {
      const batch = await request("/api/event-batch?after=" + after);
      if (session && session !== batch.session) after = 0;
      else {
        let changed = false;
        for (const [id, kind, body] of batch.events) {
          after = id;
          if (kind === "atlas") showActivity(body);
          else if (kind === "search") showSearch(body);
          else if (kind === "change") changed = true;
        }
        if (changed) void refresh();
      }
      session = batch.session;
    } catch {
      el("stream-status").textContent = "Reconnecting";
    } finally {
      window.setTimeout(pollActivity, 1000);
    }
  }
  void pollActivity();
} else {
  const feed = new EventSource("/api/events");
  feed.addEventListener("open", () => { void refresh(); });
  feed.addEventListener("error", () => { el("stream-status").textContent = "Reconnecting"; });
  feed.addEventListener("change", () => { void refresh(); });
  feed.addEventListener("search", event => showSearch(JSON.parse(event.data)));
  feed.addEventListener("atlas", event => showActivity(JSON.parse(event.data)));
}
el("inspector").append(node("p", "Select an experiment or an Atlas event to inspect its evidence.", "empty"));
void refresh();
