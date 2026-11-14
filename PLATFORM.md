# Platform contract

This is the technical contract for [REQUIREMENTS.md](REQUIREMENTS.md) (R1–R11, plus Phase 2 governance G1–G3). One live research handoff on a real GPU task: seeded agents publish measured experiments and weights, Claude Code finds them through event Atlas Vector Search, the platform labels which ones fit, Claude Code proposes a plan, a person confirms, the job trains locally and the result is saved back. The same contract supports more agents and studies later through project membership, versioned results and new job catalogs.

We build our own platform. No ARA or AutoSci code, runtime or adapter is on the build path. See [Credits](#credits).

**What exists today.** `platform_api/` (Atlas storage, search, versions, decisions, command listener) and `demo/presenter.py` are built and described in [BACKEND.md](BACKEND.md). The ResNet experiment profile, the MCP server, the weights routes and the web UI are still to build, per [TASKS.md](TASKS.md). Everything marked "target" below is not built yet.

## Shared entry point

Use Python 3.11, FastAPI and PyMongo. The platform owner runs `uvicorn platform_api.app:app --host 127.0.0.1 --port 8000` and the HTTP JSON contract below. The presenter service serves the UI and owns the embedded terminal (see [Presenter service](#presenter-service)). Callers can work against a stub serving these payloads until the real service is up.

The service maps opaque bearer tokens in server-side `MEMORY_TOKENS_JSON` to a trusted `project_id`, `agent_id`, and `role`. Example mapping entry: `{"<publisher-token>":{"project_id":"team-run-01","agent_id":"agent-a","role":"publisher"}}`. Issue a publisher token for the seeding agents, a reader token for Claude Code, a maintainer token for the person (approval, and in Phase 2 corrections and expiry), and a reader in a second project for the isolation check. Rehearsals use fresh project IDs in the same Atlas database and index. Each process receives only its own token. Atlas and provider credentials stay with the service and the trusted runner. Tokens never reach the browser. The service sets project and author from the token and rejects caller-supplied identity fields.

| Role | Can |
| --- | --- |
| reader | search, read current results and evidence, list findings, read history, resolve, propose a decision, record a run receipt for an approved decision |
| publisher | reader rights, plus publish, and correct or expire its own records |
| maintainer | reader rights, plus publish, correct and expire any record in the project, approve or reject decisions |

## Results

Every result has `schema_version: 1`, `hypothesis`, `fixture_revision`, flat `conditions` and `configuration` objects with scalar values, `metric` with name, value, unit, operator and threshold, `execution` (`completed|crashed|timed_out`), `validity` (`valid|invalid|inconclusive`), `direction` (`positive|negative|undetermined`), `evidence`, `source`, and UTC `expires_at`. A completed, valid measurement with a receipt supports a positive or negative direction according to the threshold. A run that diverges (loss becomes NaN, accuracy stays at chance) completed and measured something, so it is a valid negative. A run that never produces a measurement (out of GPU memory) is a crash. Other combinations require `undetermined` and may have a null metric value. Such records are stored and shown to humans with a "crashed" or "inconclusive" label, but search, applicability and resolve only use completed, valid results. A crash never counts as a failed idea.

Example body for `POST /v1/results`. Evidence is a small inline JSON receipt. The API serves it under the result's visibility and lifecycle.

```json
{
  "schema_version": 1,
  "hypothesis": "Fine-tuning ResNet-18 from ImageNet weights reaches at least 90% test accuracy on CIFAR-10 in three epochs.",
  "fixture_revision": "cifar10-v1",
  "conditions": {"dataset": "cifar10", "model": "resnet18", "input_size": 32},
  "configuration": {"job_id": "finetune-lr0.01", "init": "imagenet-weights", "optimizer": "sgd", "lr": 0.01, "epochs": 3, "batch_size": 128, "seed": 0},
  "metric": {"name": "test_accuracy", "value": 0.934, "unit": "ratio", "operator": ">=", "threshold": 0.90},
  "execution": "completed",
  "validity": "valid",
  "direction": "positive",
  "evidence": {"kind": "job_receipt", "data": {"run_id": "seed-ft-1", "train_seconds": 68.4, "gpu": "<name from torch.cuda>", "weights_sha256": "<hex>",
    "reproduce": {"command": "python -m benchmark.run --job finetune-lr0.01", "seed": 0, "torch_version": "<x.y.z>", "torchvision_version": "<x.y.z>", "python_version": "3.11.9"}}},
  "source": {"system": "benchmark", "source_agent": "vision-agent-1", "record": "finetune-lr0.01"},
  "expires_at": "2026-12-15T00:00:00Z"
}
```

Use a fresh future timestamp in the harness. `evidence.data.reproduce` is required for completed runs (R11). `Ref` is `{"result_id":"<uuid>","version":1}`. `Result` is the publish body without `evidence`, plus `Ref` fields, `author_id` and `status` (`current|expired`). Output errors use `{"detail":"<stable code>"}`.

`Applicability` is computed by the platform against the caller's task conditions: `{"status":"applies|mismatch","mismatches":[{"field":"dataset","wanted":"cifar10","found":"fashion-mnist"}]}`. The rule is exact agreement on `fixture_revision`, `conditions.dataset`, `conditions.model` and `conditions.input_size`. Weights and settings are not match fields, because they are what an agent chooses. They are evidence, not conditions. A result with execution or validity other than completed and valid is never returned by search.

## Routes

| Route | Request and success response |
| --- | --- |
| `GET /v1/health` | → 200 `{"atlas":"ok","index":"READY","database":"<name>","project_id":"<from token>"}`. 503 with the failing part if Atlas or the index is unavailable. |
| `POST /v1/results` | Publish body → 201 `Ref`. Version starts at 1. |
| `GET /v1/results` | → 200 `{"items":[Result]}`: every head in the caller's project, including expired ones with `status:"expired"` and crashed ones. For tooling and Phase 2 governance. Agents do not use it for decisions. |
| `POST /v1/search` | `{"question":"What has worked for training a small ResNet on CIFAR-10 to high accuracy quickly?","conditions":{"fixture_revision":"cifar10-v1","dataset":"cifar10","model":"resnet18","input_size":32}}` → 200 `{"candidates":[{"result":Result,"score":0.82,"applicability":Applicability}]}`. Only current, usable results. Mismatched results are returned with their label so Claude Code and the screen can show why they were set aside. `conditions` is optional; without it `applicability` is null. May return an empty list. |
| `GET /v1/results/{id}?version=1` | → 200 `Result`. An omitted version means current. 404 if expired or superseded. |
| `GET /v1/results/{id}/evidence?version=1` | → 200 `{"result_id":"<uuid>","version":1,"evidence":{…}}`. Same version rules. |
| `GET /v1/results/{id}/history` | → 200 `{"result_id":"<uuid>","status":"current|expired","current_version":2,"versions":[{"version":1,"state":"superseded","result":Result,"evidence":{…},"replaced_at":"…","replaced_by":"maintainer","reason":"…"},{"version":2,"state":"current",…}],"events":[{"at":"…","actor":"…","action":"publish|correct|expire","version":2,"reason":"…"}]}`. For humans (Phase 2, G1 and G2). Any project role. Old versions here are for inspection only: search, read, evidence and resolve never accept them. |
| `POST /v1/results/{id}/correct` | `{"expected_version":1,"reason":"Weights file was linked to the wrong dataset","replacement":{…full publish body…}}` → 200 `Ref` with version 2. |
| `POST /v1/results/{id}/expire` | `{"expected_version":1,"reason":"Superseded by newer measurements"}` → 200 `{"result_id":"<uuid>","version":1,"expired":true}`. A scheduled expiry uses the publish timestamp. |
| `POST /v1/resolve` | `{"refs":[Ref]}` → 200 `{"results":[Result]}` in request order if every ref is current and usable. Validate immediately before dispatch. |
| `POST /v1/decisions` | Claude Code's plan: `{"request":"…","conditions":{…},"candidates":[{"ref":Ref,"score":0.86,"applicability":Applicability}],"job_id":"finetune-lr0.01","used_refs":[Ref],"skipped_jobs":[{"job_id":"scratch-lr0.4","reason":"…","refs":[Ref]}],"rejected_candidates":[{"ref":Ref,"reason":"…"}],"reason":"…","model":"claude-code"}` → 201 `Decision` with `status:"pending"`. 422 if the job is not in the catalog, or a used ref is not current or does not apply. |
| `GET /v1/decisions/{id}` | → 200 `Decision`. |
| `POST /v1/decisions/{id}/approve` | `{"note":"Looks right"}` → 200 `Decision` with `status:"approved"`, `decided_by`, `decided_at`. Maintainer only. 409 unless pending. |
| `POST /v1/decisions/{id}/reject` | `{"reason":"Try the baseline first"}` → 200 `Decision` with `status:"rejected"`. Maintainer only. 409 unless pending. Nothing runs. |
| `POST /v1/decisions/{id}/receipt` | The runner's measured receipt → 201 `Decision` with `status:"executed"` and the receipt attached. 409 unless approved and not yet executed. If the runner's resolve failed, it posts `{"aborted":true,"reason":"…"}` and the decision becomes `aborted`. |

`Decision` is the proposal plus `decision_id`, `project_id`, `proposed_by`, `status` (`pending|approved|rejected|executed|aborted`), `decided_by`, `decided_at`, `note` or `reason`, and `receipt`.

Use 401 for missing or unknown token, 403 for role denial on visible records, 404 for absent, out-of-scope, expired or historical reads on agent paths and unusable resolve refs, 409 for a stale write or a decision in the wrong state, 422 for invalid bodies, and 503 for unavailable search. A resolve failure aborts dispatch and allows one fresh search and decision within the same job budget. Fail closed on authorization, dependency or validation errors. Token roles and source fields are kept distinct.

## Atlas storage and lifecycle

- `MEMORY_ATLAS_URI` and `MEMORY_ATLAS_DB` point to the event Sandbox. `results` holds the authoritative current head keyed by UUID with `project_id`, `author_id`, `version`, `search_key`, normalized fields, inline evidence, `expires_at`, `purge_at` and an `events` array (actor, time, action, version, reason). Each correction copies the current head into `result_versions` and replaces the head, in one transaction conditional on project, current version and active expiry. Manual expiry atomically sets `expires_at` to service time and appends an event. The original publisher keeps ownership.
- `result_versions` holds superseded payloads and their evidence keyed by `(result_id, version)`, with `project_id` and `purge_at`. Only the history route reads it.
- `result_vectors` holds immutable search entries keyed by a generated `search_key` with `project_id`, `result_id`, `version`, `embedding`, `embedding_model`, and `purge_at`. Stage the vector before committing the head. A candidate is accepted only if its key and version match the authoritative head. An orphan or old key is inert and eligible for cleanup. The `research_memory_v1` index has a 1536-dimensional cosine vector field `embedding` and a filter field `project_id`. Embed hypothesis, summarized measurement, fixture and conditions using `text-embedding-3-small` at 1536 dimensions, and embed the search question with the same model. Service secrets use `OPENAI_API_KEY`. [Embedding model](https://developers.openai.com/api/docs/models/text-embedding-3-small)
- **Search is one Atlas aggregation.** MongoDB, not Python, does retrieval, isolation, the stale-version check, expiry and applicability in a single `aggregate` on `result_vectors`. Python only embeds the question and passes the task conditions in. Recheck lifecycle at direct read, evidence read, resolve, decision create and receipt with equivalent `find` filters on `$$NOW`. Both projects get their own sentinel in the selectivity test. [Atlas Vector Search](https://www.mongodb.com/docs/vector-search/query/aggregation-stages/vector-search-stage/) · [$lookup](https://www.mongodb.com/docs/manual/reference/operator/aggregation/lookup/)

```js
db.result_vectors.aggregate([
  { $vectorSearch: { index: "research_memory_v1", path: "embedding", queryVector: q,
      filter: { project_id: P },              // isolation, from the token
      exact: true, limit: 12 } },             // ANN fallback: numCandidates 240
  { $addFields: { score: { $meta: "vectorSearchScore" } } },
  { $lookup: { from: "results", let: { id: "$result_id", v: "$version" }, as: "head",
      pipeline: [ { $match: { $expr: { $and: [
        { $eq: ["$_id", "$$id"] }, { $eq: ["$project_id", P] },
        { $eq: ["$version", "$$v"] },          // stale index entry → no match
        { $gt: ["$expires_at", "$$NOW"] },     // expired → no match, before TTL runs
        { $eq: ["$execution", "completed"] }, { $eq: ["$validity", "valid"] } ] } } },
        { $project: { evidence: 0 } } ] } },
  { $unwind: "$head" },                        // drops stale, expired and crashed hits
  { $addFields: { mismatches: { $filter: { as: "m", cond: { $ne: ["$$m.found", "$$m.wanted"] }, input: [
      { field: "fixture_revision", wanted: C.fixture_revision, found: "$head.fixture_revision" },
      { field: "dataset", wanted: C.dataset, found: "$head.conditions.dataset" },
      { field: "model", wanted: C.model, found: "$head.conditions.model" },
      { field: "input_size", wanted: C.input_size, found: "$head.conditions.input_size" } ] } } } },
  { $addFields: { applicability: { status: { $cond: [{ $eq: [{ $size: "$mismatches" }, 0] }, "applies", "mismatch"] }, mismatches: "$mismatches" } } },
  { $limit: 8 }
])
```

- **Change streams drive the live UI.** The presenter opens one change stream on `results` and one on `decisions`, each with a `$match` on `fullDocument.project_id` (use `fullDocument: "updateLookup"`). Every publish, correction, expiry, approval and receipt reaches the UI within a second without polling. The UI never reloads to show new findings. [Change streams](https://www.mongodb.com/docs/manual/changeStreams/)
- **Atlas activity is captured, not described.** The platform registers a PyMongo `CommandListener` that records each command's name, collection, duration in ms, documents returned, and a redacted command shape (query vector shown as `[1536 floats]`, no URIs or tokens). The presenter serves it on `/demo/events`. [Command monitoring](https://pymongo.readthedocs.io/en/stable/api/pymongo/monitoring.html)
- Preflight confirms the event Sandbox supports `$vectorSearch` with a filter field, `$lookup` after `$vectorSearch`, multi-document transactions, change streams and TTL indexes. If change streams are unavailable on the Sandbox tier, the presenter polls `results` and `decisions` by `updated_at` every 500 ms and the UI labels the panel “polling”.
- `decisions` holds one document per decision. Approve, reject and receipt are conditional updates on `status`, so a decision can't be approved twice or executed without approval.
- Expiry hides the record from every agent path immediately. TTL on each collection's BSON Date `purge_at` with `expireAfterSeconds: 0` is asynchronous cleanup: heads and vectors get `expires_at + 24h`, history entries get the head's purge date. Best-effort deletion of a retired vector after correction or expiry can shorten retention. The API stays correct if deletion or TTL lags. [Atlas TTL](https://www.mongodb.com/docs/manual/core/index-ttl/)

## Benchmark

**Task.** Fine-tune a ResNet-18 on CIFAR-10 to at least 90% test accuracy in one run of at most three epochs and about two GPU-minutes, on the team's GPU PC. `fixture_revision` is `cifar10-v1`: torchvision's CIFAR-10 train and test splits, a fixed validation hold-out from train, fixed seeds, 32 px inputs, and the final test accuracy as the metric (`>= 0.90` is success). Task conditions are `dataset=cifar10`, `model=resnet18`, `input_size=32`. Training is on a local NVIDIA GPU with PyTorch. Nothing else in the project trains.

**Job catalog (registered, ordered).** The approved action is always one of these, run once with a fixed seed and the stored receipt:

| Job | What it runs |
| --- | --- |
| `scratch-lr0.1` | Random init, SGD lr 0.1, 3 epochs. The baseline: what Claude Code does on its own. |
| `finetune-lr0.01` | Start from stored ImageNet weights, SGD lr 0.01, 3 epochs. |
| `scratch-lr0.4` | Random init, SGD lr 0.4, 3 epochs. Known to diverge. |

**Seeded experiments.** The benchmark owner runs these on the GPU PC, publishes them with the seeding agents' token, and stores the weights in GridFS. All numbers in the mockup are illustrative until these are measured.

| Experiment | Conditions | Expected outcome | Role in the demo |
| --- | --- | --- | --- |
| `finetune-lr0.01` | CIFAR-10, ResNet-18, 32 px | Positive, about 93% | The finding Claude Code builds on. Weights stored. |
| `scratch-lr0.4` | CIFAR-10, ResNet-18, 32 px | Valid negative, diverges to chance | The dead end Claude Code avoids. |
| `scratch-lr0.05` on Fashion-MNIST | Fashion-MNIST, ResNet-18, 28 px | Positive, about 95% | Looks great, does not fit: `dataset` and `input_size` differ. |
| Batch 4096 | CIFAR-10, ResNet-18, 32 px | Out of GPU memory in the first step: `crashed / invalid / undetermined`, null metric | Stored and visible, never returned by search. |
| ResNet paper, Table 2 (optional import) | ImageNet, 224 px | Background | Shows how published work loads in. Marked as imported. |

**Calibration gate.** Before the mockup numbers are trusted, run every catalog job and every seeded experiment on the GPU PC, record accuracy, GPU seconds, and the library versions, and check: the baseline lands well below 90%, `finetune-lr0.01` lands above 90% inside two minutes, `scratch-lr0.4` really diverges, and the batch-4096 run really runs out of memory. If a result lands on the wrong side of 90%, change epochs or learning rates and rerun. The decision should not depend on luck: use fixed seeds and re-run three times.

**The decision.** Claude Code gets the same request every time: "Build on what past agents learned about training ResNet-18 on CIFAR-10. Target 90%, one run, 2 GPU-minutes." Claude Code searches, reads each candidate's evidence, and proposes a job through `propose_plan`. Only results labelled `applies` may be cited as support or as a reason to skip a job. The platform rejects a plan that cites a mismatched, crashed or non-current result (HTTP 422), or a job outside the catalog.

| Run | Same request and budget | Expected job | Expected result |
| --- | --- | --- | --- |
| Claude Code on its own | No Precedent tools, no `.mcp.json` | `scratch-lr0.1` | About 71% |
| Claude Code with Precedent | Reads the memory | `finetune-lr0.01`, citing the positive and the failed `scratch-lr0.4`, setting aside Fashion-MNIST | About 93% |

An LLM is not deterministic. Record the baseline and the Precedent run several times during rehearsal. If Claude Code is unstable, keep the same evidence rules and run a scripted planner that applies them (labelled as such). Phase 2 adds a correction and an expiry run on the same request.

**What to build** (owner in [TASKS.md](TASKS.md)):

- `python -m benchmark.run --job <id> [--init <weights>]`: one measured run on the GPU, receipt to stdout, weights saved to a file.
- `python -m benchmark.publish`: runs or loads the seeded experiments, publishes them with the seeding token, uploads weights, then exits.
- `python -m benchmark.execute --decision ID`: runs only if the decision is approved, resolves the cited versions first, runs the registered job once, uploads the new weights and posts the receipt.
- A `benchmark.profile` module exporting the `EXPERIMENT` object that the platform loads through `MEMORY_EXPERIMENT_MODULE` (catalog, baseline, match fields `fixture_revision`, `dataset`, `model`, `input_size`, support predicate, runner). See [BACKEND.md](BACKEND.md#switch-experiments).
- The baseline recording: run Claude Code in an empty folder with no `.mcp.json` and the same prompt, save its receipt to `receipts/baseline.json`.

Receipts include the request, catalog and budget, candidates with fit labels, the selected and skipped jobs, exact cited versions, approval, executed configuration, GPU seconds, accuracy, weights hash and reproduce block.

## Claude Code integration

Claude Code is the agent in the loop. It never talks to Atlas directly; it uses the platform through an MCP server, so every rule in this contract applies to it.

The benchmark and agent owner builds `python -m platform_api.mcp` (stdio MCP server), registered for Claude Code in the demo working directory’s `.mcp.json`. It holds the reader token for the person’s project and the session identity for approvals. Tools:

| Tool | Calls | Notes |
| --- | --- | --- |
| `search_experiments(question, conditions)` | `POST /v1/search` | Returns candidates with applicability labels. Crashed, expired and superseded results never come back. |
| `get_experiment(result_id, version?)` | `GET /v1/results/{id}` and `/evidence` | Current versions only. |
| `propose_plan(job, used_refs, avoided_refs, set_aside_refs, reason)` | `POST /v1/decisions` | Stores the plan as `pending`. The decision document’s cited, avoided and set-aside refs are what the UI highlights, pushed by the `decisions` change stream. |
| `run_plan(decision_id)` | `POST /v1/decisions/{id}/approve`, then the runner | Not in Claude Code’s allowed tools, so Claude Code’s permission prompt asks the person first. That confirmation is the approval; the MCP server records it with the person’s identity. “Not now” calls `/reject`. |
| `load_weights(result_id)` | `GET /v1/results/{id}/weights` | Streams the GridFS file after the same lifecycle check as resolve. Packaged weights (for example `torchvision` `ResNet18_Weights.IMAGENET1K_V1`) are recorded as the source on the result. |
| `publish_result(body, decision_id)` | `POST /v1/results` | Publishes the run as a new experiment, linked to the decision and the versions it used. |

New route for weights: `GET /v1/results/{id}/weights?version=` → 200 streamed file with `X-Weights-SHA256`, from GridFS bucket `weights` (`fs.files` metadata carries `project_id`, `result_id`, `version`, `source`). Same 404 rules as evidence. Publishing may attach weights by upload to `POST /v1/results/{id}/weights` (publisher or maintainer).

**Embedded terminal.** The presenter serves an xterm.js panel connected over a localhost WebSocket (`/demo/terminal`) to a PTY on the presenter’s machine, started in the demo working directory, where the person runs `claude`. It is the person’s own terminal shown inside the page: nothing in the browser holds tokens, and the PTY is only reachable from localhost. If the PTY fails during judging, run Claude Code in a normal terminal beside the browser; the highlights and results still appear through change streams.

The baseline is the same `claude` session started outside the demo directory, with no `.mcp.json`, so it has no Precedent tools. It is recorded before the demo. The platform's `memory: "off"` proposal exists for the backend's own contract tests and is not part of the demo comparison.

## Presenter service

`uvicorn demo.presenter:app --host 127.0.0.1 --port 8100` serves the UI at `/`, holds the four tokens server-side, and calls the platform API and the benchmark commands. The browser only talks to the presenter. It binds to localhost.

**Two ways to drive the demo.** The main path is Claude Code in the embedded terminal through MCP. The routes below also support a scripted path (producer and planner modules) that the presenter already implements. It is the fallback if Claude Code or the PTY misbehaves during judging, and the way rehearsals run unattended. The governance routes (`/demo/governance/*`) are Phase 2.

| Route | Does |
| --- | --- |
| `GET /demo/state` | Current stage, health from `GET /v1/health`, project, the baseline receipt from `receipts/baseline.json`, findings from `GET /v1/results`, latest decision and receipts. |
| `GET /demo/events` | Server-sent events: `change` events from the change streams (operation, collection, result or decision ID, version, status) and `atlas` events from the command listener (command, collection, ms, docs, redacted shape). The UI subscribes once on load. |
| `POST /demo/agent-a` | Runs `benchmark.publish` with the seeding token. |
| `POST /demo/agent-b` | `{}`. Runs `benchmark.agent` with B's token. Returns the pending decision. |
| `POST /demo/rerun` | Repeats B's last request. |
| `POST /demo/decisions/{id}/approve` and `/reject` | Forwards with the maintainer token. |
| `POST /demo/decisions/{id}/execute` | Runs `benchmark.execute`. |
| `POST /demo/governance/correct` | `{"result_id":…,"expected_version":…,"reason":…}`. Phase 2. Uses a prepared replacement body. |
| `POST /demo/governance/expire` | `{"result_id":…,"expected_version":…,"reason":…}`. |
| `GET /demo/results/{id}/history` | Forwards the history route. |
| `GET /demo/terminal` | WebSocket to the embedded terminal’s PTY. Localhost only. |
| `POST /demo/isolation-check` | Runs the same search and a direct read with the second project's token and returns both responses (expect no candidates and 404). |

`python -m demo.reset --project demo-live` clears the demo project before a presentation.

## User interface

The mockup is [docs/demo/index.html](docs/demo/index.html). The web app is one static HTML, CSS and JavaScript bundle in `demo/web/`, served by the presenter. Requirements are in [REQUIREMENTS.md](REQUIREMENTS.md#interface). It is **not** a dashboard: one screen, centred on Claude Code and the decision.

| Area | Contents |
| --- | --- |
| Top bar | Product name and mark, the four stages (Past experiments, Ask Claude Code, You decide, Result), Atlas status from `/v1/health` without exposing internals. |
| Centre | The embedded terminal (xterm.js over a localhost WebSocket to a PTY in the demo working directory). Beside it, the experiments list. When Claude Code calls `propose_plan`, the cited, avoided and set-aside experiments are highlighted (using, avoiding, doesn't fit with the mismatched field named). Crashed experiments are shown as "never offered". |
| After the run | One result card: Claude Code on its own against Claude Code with Precedent, with the 90% target marked. |
| Drawer | Opens only when someone clicks an experiment or an Atlas line. Conditions first, then outcome, rerun command, weights and record. |
| Atlas strip | Along the bottom: the latest real commands from `/demo/events`, for example `aggregate result_vectors · $vectorSearch + $lookup · 4 docs · 38 ms`. Clicking opens the redacted pipeline in the drawer. |

Both MongoDB elements use only live data from `/demo/events`. Nothing is hardcoded in the real UI. In the mockup they are simulated.

**"In MongoDB" sentence per stage:**

| Stage | What it shows |
| --- | --- |
| 1 Past experiments | The `insert` commands and change-stream events behind the experiments list. The weights are GridFS files. |
| 2 Ask Claude Code | The one `$vectorSearch` aggregate with the `project_id` filter, hits and latency, plus the `$lookup` and the fit labels. |
| 3 You decide | The conditional `findOneAndUpdate` from `pending` to `approved`, and the 409 on a second click. |
| 4 Result | The `resolve` re-check of cited versions, the GridFS weights stream, the receipt update and the new `insert`, pushed to the screen by a change stream. |

Use distinct text labels for worked, failed, crashed and doesn't fit. Show conditions before outcomes. Support keyboard use, visible focus, and loading, empty and error states. On narrow screens the drawer is full width.

## Phase 2: governance

Correction, expiry and history are already in the backend (`correct`, `expire`, `history`, `result_versions`). They return to the screen after the four-stage demo is rehearsed: a Correct and an Expire action on an experiment's drawer, each followed by asking Claude Code again, and a version history in the drawer. Keep this off the main path until then.

## Credits

| Upstream | What inspired us | Use |
| --- | --- | --- |
| [ARA](https://github.com/ARA-Labs/Agent-Native-Research-Artifact/tree/e52a925e9d03b4ada3008653e72f99b04116fca2) at `e52a925e9d03b4ada3008653e72f99b04116fca2`, MIT, Orchestra Research | Dead ends kept as first-class records with a reason; results bound to code, config and evidence. The ResNet example artifact is our pitch example. | Ideas and pitch only. No code, data or runtime in the app. |
| [AutoSci](https://github.com/PKU-DAIR/AutoSci/tree/6bc834a805a1744959a9983809e5d6f0263ef791) at `6bc834a805a1744959a9983809e5d6f0263ef791`, MIT, OmegaWiki Contributors | A list of failed ideas with reasons that agents don't revisit (`/ideate`). We scope it by conditions. | Idea only. |
| [PyTorch](https://pytorch.org) and [torchvision](https://github.com/pytorch/vision) | ResNet-18 architecture, ImageNet weights `ResNet18_Weights.IMAGENET1K_V1`, and the CIFAR-10 loader. | Used as libraries. Their licenses apply. |

See [NOTICE.md](NOTICE.md). The platform, presenter, benchmark, UI and mockup are event-built.

