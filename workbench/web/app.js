import { Terminal } from "/vendor/xterm/lib/xterm.mjs";
import { FitAddon } from "/vendor/addon-fit/lib/addon-fit.mjs";

const el = id => document.getElementById(id);
const model = {
  state: null, search: null, activity: [], changes: [], stage: "past", currentStage: "past",
  busy: null, review: null, inspected: null,
};
const words = value => String(value ?? "—").replaceAll("_", " ");
const percent = (value, decimals = 1) => (value * 100).toFixed(decimals) + "%";
const reference = item => item.result_id + ":" + item.version;
const currentDecision = () => model.state?.decisions[0];
const metric = ({ metric: m } = {}) => m?.value == null ? "Unmeasured" :
  m.unit === "fraction" ? percent(m.value) : m.value + " " + m.unit;

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text != null) element.textContent = text;
  if (className) element.className = className;
  return element;
}

function button(label, action, className = "secondary", key) {
  const result = node("button", label, className);
  result.type = "button";
  if (key) result.dataset.focusKey = key;
  result.addEventListener("click", action);
  return result;
}

function replace(target, children) {
  const active = document.activeElement;
  const key = target.contains(active) && active.dataset.focusKey;
  target.replaceChildren(...children);
  if (key) {
    const next = [...target.querySelectorAll("[data-focus-key]")].find(item => item.dataset.focusKey === key);
    (next || target.closest("section")?.querySelector("h2"))?.focus({ preventScroll: true });
  }
}

function details(target, title, rows) {
  const section = node("section", null, "detail");
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

function showError(error, id = "error") {
  el(id).hidden = !error;
  el(id).textContent = error?.message ?? "";
}

let drawerOpener;
let drawerKey;
function openDrawer(title, library = false) {
  const drawer = el("drawer");
  if (!drawer.open) {
    drawerOpener = document.activeElement;
    drawerKey = drawerOpener.dataset.focusKey;
  }
  model.inspected = null;
  el("drawer-title").textContent = title;
  el("inspector").replaceChildren();
  el("library").hidden = !library;
  if (!drawer.open) drawer.showModal();
  else el("close-drawer").focus();
  drawer.scrollTop = 0;
  return el("inspector");
}

el("close-drawer").addEventListener("click", () => el("drawer").close());
el("drawer").addEventListener("close", () => {
  model.inspected = null;
  const opener = drawerOpener?.isConnected ? drawerOpener :
    [...document.querySelectorAll("[data-focus-key]")].find(item => item.dataset.focusKey === drawerKey);
  (opener || el("findings").previousElementSibling.querySelector("h2")).focus({ preventScroll: true });
});

function artifactLink(label, item) {
  const link = node("a", label);
  link.href = "/api/results/" + encodeURIComponent(item.result_id) + "/artifact?version=" + item.version;
  return link;
}

async function inspect(item) {
  const panel = openDrawer(item.hypothesis);
  const token = model.inspected = Symbol();
  details(panel, "Measurement", [
    ["metric", item.metric.name], ["value", metric(item)], ["target", item.metric.threshold == null ? null :
      item.metric.unit === "fraction" ? percent(item.metric.threshold, 0) : item.metric.threshold],
    ["execution", item.execution], ["validity", item.validity], ["outcome", item.direction],
  ]);
  details(panel, "Conditions", Object.entries({ fixture_revision: item.fixture_revision, ...item.conditions }));
  details(panel, "Configuration", Object.entries(item.configuration));
  details(panel, "Source", [["record", item.source.record], ["author", item.author_id],
    ["agent", item.source.source_agent], ["version", item.version], ["result", item.result_id]]);
  if (item.artifact) {
    const block = details(panel, "Stored weights", [["file", item.artifact.filename],
      ["size", (item.artifact.bytes / (1024 * 1024)).toFixed(1) + " MiB"], ["SHA-256", item.artifact.sha256]]);
    if (item.status !== "expired") block.append(artifactLink("Download checkpoint", item));
  }
  try {
    const history = await request("/api/results/" + encodeURIComponent(item.result_id) + "/history");
    if (token !== model.inspected) return;
    const evidence = history.versions.find(version => version.version === item.version)?.evidence?.data;
    if (evidence?.reproduce) renderReproduction(panel, evidence);
    details(panel, "Versions", history.versions.map(v => ["v" + v.version, v.state]));
  } catch (error) {
    if (token === model.inspected) panel.append(node("p", error.message, "error"));
  }
}

function renderReproduction(panel, receipt) {
  const { reproduce, input_checkpoint } = receipt;
  const block = details(panel, "Reproduction", [
    ["fixture SHA-256", reproduce.fixture_sha256], ...Object.entries(reproduce.versions || {}),
  ]);
  if (reproduce.command) block.append(node("pre", reproduce.command));
  if (input_checkpoint) block.append(artifactLink("Download original input checkpoint", input_checkpoint));
}

function newerSearch(decision) {
  if (!model.search) return false;
  if (!decision) return true;
  return !["pending", "approved", "running"].includes(decision.status) &&
    Date.parse(model.search.body.searched_at) > Date.parse(decision.created_at);
}

function findingLabel(item, applicability, decision) {
  const ref = reference(item);
  if (item.execution === "crashed") return ["Never offered (crashed)", "crash"];
  if (item.status === "expired") return ["Expired", ""];
  if (applicability?.status === "mismatch") {
    return ["Doesn’t fit", "mismatch", applicability.mismatches.map(
      ({ field, found, wanted }) => field + " " + (found ?? "missing") + " ≠ " + (wanted ?? "missing")
    ).join(", ")];
  }
  const skipped = decision?.skipped_jobs.find(job => job.refs.some(r => reference(r) === ref));
  if (skipped) return ["Avoiding", "avoid"];
  if (decision?.used_refs.some(r => reference(r) === ref)) return ["Using", "use"];
  if (applicability?.status === "applies") return ["Fits", ""];
  if (item.execution !== "completed") return [words(item.execution), ""];
  if (item.validity !== "valid") return [words(item.validity), ""];
  if (item.direction === "positive") return ["Worked", "positive"];
  if (item.direction === "negative") return ["Missed target", "negative"];
  return ["Undetermined", ""];
}

function findingRow(item, applicability, decision, prefix = "finding") {
  const [label, style, reason] = findingLabel(item, applicability, decision);
  const entry = button("", () => inspect(item), "entry " + style, prefix + ":" + reference(item));
  entry.setAttribute("aria-haspopup", "dialog");
  const summary = node("span");
  summary.append(node("strong", item.hypothesis));
  summary.append(node("small", [metric(item), item.author_id, "v" + item.version,
    item.artifact && "Stored weights"].filter(Boolean).join(" · ")));
  if (reason) summary.append(node("small", reason, "reason"));
  entry.append(summary, node("span", label, "tag " + style));
  return entry;
}

function renderFindings() {
  if (!model.state) return;
  const latest = currentDecision();
  const useSearch = newerSearch(latest);
  const decision = useSearch ? null : latest;
  const searchRows = useSearch ? model.search.body.candidates : [];
  const labels = new Map(searchRows.map(row => [reference(row.result), row.applicability]));
  for (const row of decision?.candidates || []) labels.set(reference(row.ref), row.applicability);
  const findings = new Map(searchRows.map(row => [reference(row.result), row.result]));
  for (const item of model.state.findings) findings.set(reference(item), item);
  // The latest state wins if a search predates a correction to the same result.
  const currentVersions = new Map(model.state.findings.map(item => [item.result_id, item.version]));
  const rows = [...findings.values()].filter(item =>
    !currentVersions.has(item.result_id) || currentVersions.get(item.result_id) === item.version);
  el("finding-count").textContent = rows.length + (rows.length === 1 ? " record" : " records");
  replace(el("findings"), rows.length ? rows.map(item => findingRow(item, labels.get(reference(item)), decision)) :
    [node("p", "No experiments have been published yet.", "empty")]);
}

function selectStage(stage, manual = false) {
  model.stage = stage;
  for (const step of document.querySelectorAll("[data-stage]")) {
    step.setAttribute("aria-pressed", String(step.dataset.stage === stage));
    if (step.dataset.stage === model.currentStage) step.setAttribute("aria-current", "step");
    else step.removeAttribute("aria-current");
  }
  updatePlanVisibility();
  if (!currentDecision()?.receipt) renderResult();
  renderCallout();
  if (manual) {
    const target = { past: "experiments-title", ask: "agent-title", decide: "plan-title", result: "result-title" }[stage];
    if (el(target).getClientRects().length) el(target).scrollIntoView({ block: "nearest" });
  }
}

function updateStage() {
  const decision = currentDecision();
  const stage = newerSearch(decision) ? "ask" :
    decision?.receipt ? "result" : decision ? "decide" :
    terminalSocket?.readyState < WebSocket.CLOSING ? "ask" : "past";
  if (stage !== model.currentStage) {
    model.currentStage = stage;
    selectStage(stage);
  } else {
    updatePlanVisibility();
    renderCallout();
  }
}

function updatePlanVisibility() {
  const decision = currentDecision();
  const focused = el("decision-panel").contains(document.activeElement);
  el("decision-panel").hidden = (!decision && model.stage !== "decide") ||
    (decision?.status === "executed" && model.stage !== "decide");
  if (el("decision-panel").hidden && focused && decision?.receipt) {
    el("result-title").focus();
  }
}

function renderPlan() {
  const decision = currentDecision();
  if (!decision) {
    el("plan-status").textContent = "Awaiting plan";
    el("plan-actions").hidden = true;
    replace(el("decision"), [node("p", "Ask Codex to propose a plan for review.", "empty")]);
    return;
  }
  const busy = model.busy?.id === decision.decision_id;
  const canRun = ["pending", "approved"].includes(decision.status);
  const canReject = decision.status === "pending";
  const active = document.activeElement;
  el("plan-status").textContent = busy && canRun ?
    (model.busy.action === "run" ? "Starting run" : "Rejecting") : words(decision.status);
  el("plan-actions").hidden = !canRun;
  el("run-plan").disabled = Boolean(model.busy);
  el("reject-plan").disabled = Boolean(model.busy);
  el("reject-plan").hidden = !canReject;
  if ((active === el("run-plan") && !canRun) || (active === el("reject-plan") && !canReject)) {
    el("plan-title").focus({ preventScroll: true });
  }
  const children = [node("h3", decision.job_id + " · " + decision.model), node("p", decision.reason)];
  if (decision.abort_reason) children.push(node("p", words(decision.abort_reason), "error"));
  for (const skipped of decision.skipped_jobs) {
    children.push(node("p", "Avoid " + skipped.job_id + " · " + skipped.reason, "muted"));
  }
  if (decision.status === "running") {
    children.push(node("p", "Training is running. The measured result will appear here.", "muted"));
  } else if (decision.status === "rejected") {
    children.push(node("p", "This plan was rejected before execution.", "muted"));
  }
  replace(el("decision"), children);
}

function measurement(receipt, label, guided = false) {
  const card = node("section", null, "measurement" + (guided ? " guided" : ""));
  card.append(node("h3", label));
  if (!receipt) {
    card.append(node("p", "Baseline receipt unavailable.", "muted"));
    return card;
  }
  card.append(node("p", metric(receipt), "metric-main"));
  if (receipt.metric?.unit === "fraction" && receipt.metric.value != null) {
    const bar = node("div", null, "bar");
    bar.setAttribute("aria-hidden", "true");
    const fill = node("span");
    fill.style.width = Math.min(100, Math.max(0, receipt.metric.value * 100)) + "%";
    bar.append(fill);
    const threshold = receipt.metric.threshold;
    if (Number.isFinite(threshold) && threshold >= 0 && threshold <= 1) {
      const marker = node("i");
      marker.style.left = percent(threshold);
      bar.append(marker);
    }
    card.append(bar);
  }
  card.append(node("p", [receipt.metric?.name, receipt.elapsed_seconds != null && receipt.elapsed_seconds + " s",
    receipt.configuration?.device, receipt.configuration?.initialization].filter(Boolean).join(" · "), "muted"));
  if (receipt.input_checkpoint) {
    card.append(node("p", "Reused " + receipt.input_checkpoint.filename + " · v" + receipt.input_checkpoint.version));
  }
  if (receipt.published) {
    const finding = model.state.findings.find(item => reference(item) === reference(receipt.published));
    if (finding) card.append(button("Inspect published experiment", () => inspect(finding), "text-button",
      "published:" + reference(finding)));
  }
  return card;
}

function renderResult() {
  const decision = currentDecision();
  const receipt = decision?.receipt;
  el("result").hidden = !receipt && model.stage !== "result";
  if (!receipt) {
    el("target").hidden = true;
    const messages = {
      running: "Training is running.",
      rejected: "The plan was rejected before execution.",
      aborted: "The run ended without a measurement (" + words(decision?.abort_reason) + ").",
    };
    replace(el("result-comparison"), [node("p", messages[decision?.status] ||
      "A measured result appears here after a plan runs.", "empty")]);
    return;
  }
  const { metric: m } = receipt;
  el("target").textContent = m?.threshold == null ? "" :
    (m.unit === "fraction" ? percent(m.threshold, 0) : m.threshold + " " + m.unit) + " target";
  el("target").hidden = !el("target").textContent;
  replace(el("result-comparison"), [
    measurement(model.state.baseline, "Codex on its own"),
    measurement(receipt, "Codex with Precedent", true),
  ]);
}

async function act(action) {
  const decision = currentDecision();
  if (!decision || model.busy || (action === "reject" && decision.status !== "pending") ||
      !["pending", "approved"].includes(decision.status)) return;
  const focusWasInPlan = el("decision-panel").contains(document.activeElement);
  model.busy = { id: decision.decision_id, action };
  model.review = { id: decision.decision_id, after: cursor, action };
  showError(null);
  if (focusWasInPlan) el("plan-title").focus({ preventScroll: true });
  renderPlan();
  try {
    const response = await request("/api/decisions/" + encodeURIComponent(decision.decision_id) + "/" + action, {});
    stateRevision += 1;
    model.state.decisions = model.state.decisions.map(item => item.decision_id === response.decision_id ? response : item);
    render();
  } catch (error) {
    showError(error);
  } finally {
    model.busy = null;
    renderPlan();
    void refresh();
  }
}

function render() {
  const { project, health, streams, defaults, codex_available } = model.state;
  el("project").textContent = project;
  el("project").hidden = !project;
  el("connection").textContent = health.atlas === "ok" ? "Index " + words(health.index).toLowerCase() : "Unavailable";
  el("atlas-dot").classList.toggle("online", health.atlas === "ok");
  el("stream-status").textContent = streams.results;
  el("prompt").textContent = defaults.question || "Ask Codex about past experiments.";
  el("match").disabled = !defaults.conditions;
  el("terminal-toggle").disabled = !terminalSocket && !codex_available;
  el("terminal-placeholder").textContent = codex_available ? "Open the terminal to ask Codex what to build on." :
    "Install and sign in to Codex to open a terminal.";
  renderFindings();
  renderPlan();
  renderResult();
  updateStage();
}

let refreshing = false;
let refreshAgain = false;
let stateRevision = 0;
async function refresh() {
  if (refreshing) {
    refreshAgain = true;
    return;
  }
  refreshing = true;
  const revision = stateRevision;
  try {
    const state = await request("/api/state");
    if (revision === stateRevision) {
      model.state = state;
      render();
    } else {
      refreshAgain = true;
    }
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
  if (!consoleView) return;
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
  el("terminal").hidden = true;
  el("terminal-placeholder").hidden = false;
  el("terminal-status").textContent = "";
  el("terminal-toggle").textContent = "Open terminal";
  el("terminal-actions").hidden = true;
  updateStage();
}

function openTerminal() {
  if (terminalSocket) return closeTerminal();
  el("terminal").hidden = false;
  el("terminal-placeholder").hidden = true;
  el("terminal-toggle").textContent = "Close terminal";
  el("terminal-status").textContent = "Starting Codex";
  consoleView = new Terminal({ fontSize: 12, fontFamily: "IBM Plex Mono, monospace", cursorBlink: true,
    theme: { background: "#10251d", foreground: "#dbede2", cursor: "#82e3b1" } });
  fit = new FitAddon();
  consoleView.loadAddon(fit);
  consoleView.open(el("terminal"));
  const socket = terminalSocket = new WebSocket(
    (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/terminal/codex");
  socket.addEventListener("open", () => {
    if (terminalSocket !== socket) return;
    fitTerminal();
    consoleView.focus();
    el("terminal-status").textContent = "Precedent MCP";
    el("terminal-actions").hidden = !model.state?.defaults.question;
  });
  socket.addEventListener("message", event => {
    if (terminalSocket === socket) consoleView.write(event.data);
  });
  socket.addEventListener("close", () => {
    if (terminalSocket !== socket) return;
    el("terminal-status").textContent = "Terminal disconnected";
    el("terminal-actions").hidden = true;
    updateStage();
  });
  consoleView.onData(input => {
    if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ input }));
  });
  updateStage();
  selectStage("ask");
}

el("terminal-toggle").addEventListener("click", openTerminal);
el("send-prompt").addEventListener("click", () => {
  const question = model.state?.defaults.question;
  if (!question || terminalSocket?.readyState !== WebSocket.OPEN) return;
  const guidance = " Use only Precedent MCP. Read experiment_profile, search with its task conditions, and submit propose_plan for review. Put supporting evidence in used_refs, failed jobs in skipped_jobs, and mismatches in rejected_candidates. Cite exact versions. Leave execution to the Run plan button.";
  consoleView.focus();
  consoleView.paste(question + guidance);
});
new ResizeObserver(fitTerminal).observe(el("terminal"));
document.querySelectorAll("[data-stage]").forEach(step =>
  step.addEventListener("click", () => selectStage(step.dataset.stage, true)));
el("run-plan").addEventListener("click", () => act("run"));
el("reject-plan").addEventListener("click", () => act("reject"));

el("open-research").addEventListener("click", () => {
  openDrawer("Research library", true);
  if (!el("query").value) {
    el("search-results").replaceChildren();
    el("search-results").append(...(model.state?.findings || []).map(item => findingRow(item, null, null, "library")));
  }
});
el("open-runs").addEventListener("click", () => {
  const target = openDrawer("Run comparison");
  const receipts = model.state?.decisions.filter(d => d.receipt) || [];
  target.append(measurement(model.state?.baseline, "Codex on its own"),
    ...receipts.map(d => measurement(d.receipt, d.job_id + " · " + d.model, true)));
  if (!receipts.length) target.append(node("p", "Completed guided runs will appear here.", "empty"));
});
el("search").addEventListener("submit", async event => {
  event.preventDefault();
  showError(null, "search-error");
  try {
    const response = await request("/api/search", {
      question: el("query").value,
      conditions: el("match").checked ? model.state?.defaults.conditions : null,
    });
    replace(el("search-results"), response.candidates.length ?
      response.candidates.map(row => findingRow(row.result, row.applicability, null, "library")) :
      [node("p", "No current matching evidence was returned.", "empty")]);
  } catch (error) {
    showError(error, "search-error");
  }
});

const successful = (item, command, collection) =>
  item.kind === "atlas" && item.body.ok && item.body.command === command && item.body.collection === collection;
const searchCommand = item => successful(item, "aggregate", "result_vectors") &&
  item.body.shape.pipeline?.some(stage => stage.$vectorSearch?.filter?.project_id) &&
  item.body.shape.pipeline.some(stage => stage.$lookup?.from === "results");
const publication = item => successful(item, "insert", "results") && item.body.docs > 0;
const chunkRead = item => ["find", "getMore"].some(command =>
  successful(item, command, "artifacts.chunks")) && item.body.docs > 0;

function reviewStatus(item) {
  if (!successful(item, "findAndModify", "decisions") || !item.body.docs) return null;
  return item.body.shape.updates?.find(update => update.filter?.status === "pending" &&
    update.filter.project_id && update.filter._id && ["approved", "rejected"].includes(update.status))?.status;
}

function activityDetails(item) {
  const { body } = item;
  const panel = openDrawer(item.kind === "atlas" ? "MongoDB " + body.command : "Experiment change");
  details(panel, "Activity", [["collection", body.collection], ["operation", body.command || body.operation],
    ["documents", body.docs], ["elapsed", body.ms == null ? null : body.ms + " ms"]]);
  panel.append(node("pre", JSON.stringify(body.shape || body, null, 2)));
}

function stageEvidence() {
  const decision = currentDecision();
  const activity = model.activity;
  if (model.stage === "past") {
    const insert = activity.find(publication);
    if (insert) return [insert, "Atlas inserted " + insert.body.docs + " experiment document" +
      (insert.body.docs === 1 ? "." : "s.")];
    const change = model.changes.find(item => item.body.collection === "results" && item.body.operation === "insert");
    if (change) return [change, "The results change stream delivered a new experiment."];
    return [null, "New experiment events will appear here as they arrive."];
  }
  if (model.stage === "ask") {
    const search = model.search && activity.filter(item => searchCommand(item) &&
      item.body.docs === model.search.body.candidates.length).reduce((closest, item) =>
      !closest || Math.abs(item.id - model.search.id) < Math.abs(closest.id - model.search.id) ? item : closest, null);
    if (search) return [search, "One aggregate ran $vectorSearch with a project_id filter and used $lookup to check current experiment versions."];
    return [null, "Waiting for a project-scoped vector search."];
  }
  if (model.stage === "decide") {
    const action = model.review?.id === decision?.decision_id ? model.review : null;
    const expected = decision?.status === "rejected" || action?.action === "reject" ? "rejected" : "approved";
    const proposal = decision && model.changes.find(item => item.body.decision_id === decision.decision_id &&
      item.body.operation === "insert");
    const after = action?.after ?? proposal?.id;
    const review = after == null ? null : activity.find(item => reviewStatus(item) === expected && item.id > after);
    if (review && (action || ["approved", "running", "executed", "rejected", "aborted"].includes(decision?.status))) {
      return [review, "A conditional findAndModify changed one pending decision to " + expected + "."];
    }
    if (proposal && decision.status === "pending") {
      return [proposal, "The decisions change stream delivered the newly submitted plan."];
    }
    return [null, "Waiting for a decision review event."];
  }
  const receipt = decision?.receipt;
  const action = model.review?.id === decision?.decision_id ? model.review : null;
  const claim = model.changes.find(item => item.body.decision_id === decision?.decision_id &&
    ["approved", "running"].includes(item.body.status));
  const after = action?.after ?? claim?.id;
  const change = receipt?.published && model.changes.find(item => item.body.operation === "insert" &&
    item.body.result_id === receipt.published.result_id && item.body.version === receipt.published.version);
  const insert = after == null ? null : activity.find(item => publication(item) && item.id > after);
  const stream = after == null ? null : activity.find(item => chunkRead(item) && item.id > after &&
    (!insert || item.id < insert.id));
  if (stream && receipt?.input_checkpoint && change) {
    return [insert || change, "GridFS streamed the input checkpoint and the results change stream delivered the new experiment insert."];
  }
  if (change) return [insert || change, "The results change stream delivered the newly inserted experiment."];
  if (stream && decision?.status === "running") return [stream, "GridFS returned chunks from the input checkpoint."];
  if (stream && decision?.status === "aborted") return [stream, "GridFS returned checkpoint chunks before the run aborted."];
  return [null, "Waiting for events from the approved run."];
}

function renderCallout() {
  const [item, sentence] = stageEvidence();
  const key = item ? "callout:" + item.id : "";
  const target = el("stage-activity");
  if (target.textContent === sentence && (target.firstChild?.dataset?.focusKey || "") === key) return;
  replace(target, [item ? button(sentence, () => activityDetails(item), "text-button", key) : node("p", sentence)]);
}

function renderActivity() {
  if (!model.activity.length) return;
  const lines = model.activity.slice(0, 24).map(item => {
    const record = item.body;
    const description = [
      record.command, record.collection, record.docs != null && record.docs + " docs",
      record.ok ? record.ms + " ms" : "failed",
    ].filter(Boolean).join(" · ");
    return button(description, () => activityDetails(item), "", "activity:" + item.id);
  });
  replace(el("event-lines"), lines);
}

let session, cursor = 0;
function receive(nextSession, events) {
  if (session && session !== nextSession) {
    cursor = 0;
    model.activity = [];
    model.changes = [];
    model.search = null;
    model.review = null;
    el("event-lines").replaceChildren(node("p", "Waiting for Atlas events…"));
  }
  session = nextSession;
  let changed = false, searched = false, atlas = false;
  for (const [id, kind, body] of events) {
    if (id <= cursor) continue;
    cursor = id;
    const item = { id, kind, body };
    if (kind === "search") {
      if (body.source === "agent") {
        model.search = item;
        searched = true;
      }
    } else if (kind === "change") {
      model.changes.unshift(item);
      model.changes.length = Math.min(model.changes.length, 300);
      changed = true;
    } else if (kind === "atlas") {
      // Skip reads used by the workspace's own state refresh.
      if ((body.command === "aggregate" && body.collection === "results") ||
          (body.command === "aggregate" && body.shape.pipeline?.some(stage => "$listSearchIndexes" in stage)) ||
          (body.command === "find" && body.collection === "decisions" && !body.shape.filter?._id)) continue;
      model.activity.unshift(item);
      model.activity.length = Math.min(model.activity.length, 300);
      atlas = true;
    }
  }
  if (changed) void refresh();
  if (searched) renderFindings();
  if (atlas) renderActivity();
  updateStage();
}

if (location.protocol === "https:") {
  async function pollActivity() {
    try {
      let batch = await request("/api/event-batch?after=" + cursor);
      if (session && session !== batch.session) batch = await request("/api/event-batch?after=0");
      receive(batch.session, batch.events);
      if (model.state) el("stream-status").textContent = model.state.streams.results;
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
  for (const kind of ["atlas", "search", "change"]) {
    feed.addEventListener(kind, event => {
      const [eventSession, id] = event.lastEventId.split(":");
      receive(eventSession, [[Number(id), kind, JSON.parse(event.data)]]);
    });
  }
}
updateStage();
void refresh();
