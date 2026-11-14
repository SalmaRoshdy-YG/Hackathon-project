# Platform contract

This is the technical contract for [REQUIREMENTS.md](REQUIREMENTS.md) (R1–R11, plus Phase 2 governance G1–G3). One live research handoff on a real training task: seeded agents publish measured experiments and checkpoints, a coding agent (Codex) finds them through event Atlas Vector Search over MCP, the platform labels which ones fit, the agent proposes a plan, a person confirms, the job trains locally and the result is saved back. The same contract supports more agents and studies later through project membership, versioned results and new job profiles.

We build our own platform. No ARA or AutoSci code, runtime or adapter is on the build path. See [Credits](#credits).

**What exists today** (the team's handoff in [TASKS.md](TASKS.md) records the live run):
- `platform_api/`: Atlas storage, vector search as one aggregation, versions, expiry, decisions with atomic approval and one dispatch, GridFS artifacts, command listener.
- `experiments/resnet.py`: the ResNet-50 digits experiment profile (catalog, seed, runner).
- `workbench/`: the web app. It serves the UI, an embedded Codex terminal over a WebSocket, and the `/mcp` endpoint, and relays Atlas activity to the browser.
- `demo/presenter.py`: an earlier scripted-agent presenter, kept as a fallback.

Not built yet: the crashed-run seed, the single-screen UI from the mockup, rehearsal automation, and Phase 2 governance in the UI.

## Shared entry point

Use Python 3.11, FastAPI and PyMongo. The platform owner runs `uvicorn platform_api.app:app --host 127.0.0.1 --port 8000` and the HTTP JSON contract below. The presenter service serves the UI and owns the embedded terminal (see [Presenter service](#presenter-service)). Callers can work against a stub serving these payloads until the real service is up.

The service maps opaque bearer tokens in server-side `MEMORY_TOKENS_JSON` to a trusted `project_id`, `agent_id`, and `role`. Example mapping entry: `{"<publisher-token>":{"project_id":"team-run-01","agent_id":"agent-a","role":"publisher"}}`. Issue a publisher token for the seeding agents, a reader token for the agent, a maintainer token for the person (approval, and in Phase 2 corrections and expiry), and a reader in a second project for the isolation check. Rehearsals use fresh project IDs in the same Atlas database and index. Each process receives only its own token. Atlas and provider credentials stay with the service and the trusted runner. Tokens never reach the browser. The service sets project and author from the token and rejects caller-supplied identity fields.

| Role | Can |
| --- | --- |
| reader | search, read current results and evidence, list findings, read history, resolve, propose a decision, record a run receipt for an approved decision |
| publisher | reader rights, plus publish, and correct or expire its own records |
| maintainer | reader rights, plus publish, correct and expire any record in the project, approve or reject decisions |

## Results

Every result has `schema_version: 1`, `hypothesis`, `fixture_revision`, flat `conditions` and `configuration` objects with scalar values, `metric` with name, value, unit, operator and threshold, `execution` (`completed|crashed|timed_out`), `validity` (`valid|invalid|inconclusive`), `direction` (`positive|negative|undetermined`), `evidence`, `source`, and UTC `expires_at`. A completed, valid measurement with a receipt supports a positive or negative direction according to the threshold. A run that trains and scores below the threshold is a valid negative. A run that never produces a measurement (out of memory, an exception) is a crash. Other combinations require `undetermined` and may have a null metric value. Such records are stored and shown to humans with a "crashed" or "inconclusive" label, but search, applicability and resolve only use completed, valid results. A crash never counts as a failed idea.

Example body for `POST /v1/results`. Evidence is a small inline JSON receipt. The API serves it under the result's visibility and lifecycle.

```json
{
  "schema_version": 1,
  "hypothesis": "ResNet-50 transfer with a pretrained backbone on 64 px handwritten digits",
  "fixture_revision": "sklearn-digits-v1",
  "conditions": {"dataset": "sklearn digits", "architecture": "ResNet-50", "classes": 10, "image_px": 64, "split": "calibration"},
  "configuration": {"job_id": "reuse", "epochs": 4, "learning_rate": 0.01, "seed": 42, "initialization": "TorchVision ImageNet V1", "frozen_backbone": true, "batch_size": 32, "device": "cuda"},
  "metric": {"name": "top-1 accuracy", "value": 0.9, "unit": "fraction", "operator": ">=", "threshold": 0.8},
  "execution": "completed",
  "validity": "valid",
  "direction": "positive",
  "artifact": {"filename": "resnet50-digits.safetensors", "bytes": 94400000, "sha256": "<hex>"},
  "evidence": {"kind": "job_receipt", "data": {"run_id": "<uuid>", "elapsed_seconds": 0, "reproduce": {"command": "python -m experiments.resnet train reuse calibration output.safetensors --image-px 64", "fixture_sha256": "<hex>", "versions": {"python": "3.11.9", "torch": "<x.y.z>", "torchvision": "<x.y.z>", "sklearn": "<x.y.z>"}}}},
  "source": {"system": "resnet-digits", "source_agent": "calibration-agent", "record": "<run id>"},
  "expires_at": "2026-11-21T00:00:00Z"
}
```

Use a fresh future timestamp in the harness. `evidence.data.reproduce` is required for completed runs (R11). `Ref` is `{"result_id":"<uuid>","version":1}`. `Result` is the publish body without `evidence`, plus `Ref` fields, `author_id` and `status` (`current|expired`). Output errors use `{"detail":"<stable code>"}`.

`Applicability` is computed by the platform against the caller's task conditions: `{"status":"applies|mismatch","mismatches":[{"field":"image_px","wanted":64,"found":32}]}`. The rule is exact agreement on `fixture_revision`, `conditions.dataset`, `conditions.model` and `conditions.input_size`. Weights and settings are not match fields, because they are what an agent chooses. They are evidence, not conditions. A result with execution or validity other than completed and valid is never returned by search.

## Routes

| Route | Request and success response |
| --- | --- |
| `GET /v1/health` | → 200 `{"atlas":"ok","index":"READY","database":"<name>","project_id":"<from token>"}`. 503 with the failing part if Atlas or the index is unavailable. |
| `POST /v1/artifacts` | Multipart `upload` from a publisher. Stored in GridFS under the caller's project. → 201 `{"filename","bytes","sha256"}`. Attach it as `artifact` on a published result. |
| `GET /v1/results/{id}/artifact?version=N` | → 200 streamed file with `X-Artifact-SHA256`, for a visible version in the caller's project. Same 404 rules as evidence. |
| `POST /v1/results` | Publish body → 201 `Ref`. Version starts at 1. |
| `GET /v1/results` | → 200 `{"items":[Result]}`: every head in the caller's project, including expired ones with `status:"expired"` and crashed ones. For tooling and Phase 2 governance. Agents do not use it for decisions. |
| `POST /v1/search` | `{"question":"What has worked for transferring a pretrained ResNet to handwritten digits?","conditions":{"fixture_revision":"sklearn-digits-v1","dataset":"sklearn digits","architecture":"ResNet-50","classes":10,"image_px":64}}` → 200 `{"candidates":[{"result":Result,"score":0.82,"applicability":Applicability}]}`. Only current, usable results. Mismatched results are returned with their label so the agent and the screen can show why they were set aside. `conditions` is optional; without it `applicability` is null. May return an empty list. |
| `GET /v1/results/{id}?version=1` | → 200 `Result`. An omitted version means current. 404 if expired or superseded. |
| `GET /v1/results/{id}/evidence?version=1` | → 200 `{"result_id":"<uuid>","version":1,"evidence":{…}}`. Same version rules. |
| `GET /v1/results/{id}/history` | → 200 `{"result_id":"<uuid>","status":"current|expired","current_version":2,"versions":[{"version":1,"state":"superseded","result":Result,"evidence":{…},"replaced_at":"…","replaced_by":"maintainer","reason":"…"},{"version":2,"state":"current",…}],"events":[{"at":"…","actor":"…","action":"publish|correct|expire","version":2,"reason":"…"}]}`. For humans (Phase 2, G1 and G2). Any project role. Old versions here are for inspection only: search, read, evidence and resolve never accept them. |
| `POST /v1/results/{id}/correct` | `{"expected_version":1,"reason":"Weights file was linked to the wrong dataset","replacement":{…full publish body…}}` → 200 `Ref` with version 2. |
| `POST /v1/results/{id}/expire` | `{"expected_version":1,"reason":"Superseded by newer measurements"}` → 200 `{"result_id":"<uuid>","version":1,"expired":true}`. A scheduled expiry uses the publish timestamp. |
| `POST /v1/resolve` | `{"refs":[Ref]}` → 200 `{"results":[Result]}` in request order if every ref is current and usable. Validate immediately before dispatch. |
| `POST /v1/decisions` | The agent's plan: `{"request":"…","conditions":{…},"candidates":[{"ref":Ref,"score":0.86,"applicability":Applicability}],"job_id":"reuse","used_refs":[Ref],"skipped_jobs":[{"job_id":"high-lr","reason":"…","refs":[Ref]}],"rejected_candidates":[{"ref":Ref,"reason":"…"}],"reason":"…","model":"codex"}` → 201 `Decision` with `status:"pending"`. 422 if the job is not in the catalog, or a used ref is not current or does not apply. |
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

## Benchmark: ResNet-50 transfer on handwritten digits

Implemented in `experiments/resnet.py` (profile id `resnet50-digits-v1`).

**Task.** Train a ResNet-50 to at least 80% top-1 accuracy on a handwritten-digit holdout in one four-epoch run. Data is scikit-learn's digits fixture, upsampled to the task's `image_px` (64) and normalised with ImageNet statistics. Calibration and holdout are disjoint index windows of one seeded permutation. Training uses a GPU when PyTorch sees one, otherwise the CPU. Task conditions: `fixture_revision=sklearn-digits-v1`, `dataset=sklearn digits`, `architecture=ResNet-50`, `classes=10`, `image_px=64`.

**Job catalog (ordered).** `scratch`, `reuse`, `high-lr`. The baseline is `scratch`.

| Job | What it runs |
| --- | --- |
| `scratch` | Random initialisation, all layers trained, AdamW lr 0.01. What the agent does on its own. |
| `reuse` | Backbone frozen, new 10-class head trained, AdamW lr 0.01. Starts from a stored checkpoint (SHA-256 checked) when the plan cites one. |
| `high-lr` | Frozen ImageNet backbone with lr 10.0. Known to fail. |

**Seeded experiments** (`python -m experiments.resnet seed`, calibration split):

| Experiment | Conditions | Expected | Role in the demo |
| --- | --- | --- | --- |
| `reuse` at 64 px | Task conditions | Positive. Checkpoint stored in GridFS. | The finding the agent builds on. |
| `high-lr` at 64 px | Task conditions | Valid negative. | The dead end the agent avoids. |
| `reuse` at 32 px | `image_px=32` | Positive on its own task. | Looks good, does not fit: `image_px` differs. |
| Crashed run | Task conditions | `crashed / invalid / undetermined`, null metric. | Stored, shown, never returned by search. **Not seeded yet.** |

**Verified once (team handoff in TASKS.md):** the scratch baseline measured 29.2% on the holdout, and the memory-guided `reuse` run measured 90.4% on the same holdout, with the output checkpoint stored in GridFS. Re-measure on the demo machine before trusting these, and repeat to check stability.

**The decision.** The agent gets the workspace's suggested request ("Train ResNet-50 to at least 80% holdout accuracy on handwritten digits. Find an applicable calibration checkpoint, explain what to avoid, and propose one run."), searches, reads each candidate's evidence, and proposes one job with `propose_plan`. Only results labelled `applies` may be cited as support or as a reason to skip a job. The platform rejects a plan that cites a mismatched, crashed or non-current result (HTTP 422), or a job outside the catalog. A `reuse` plan must cite a positive calibration result that has a `.safetensors` checkpoint.

| Run | Same request and budget | Expected job | Expected result |
| --- | --- | --- | --- |
| Agent on its own | No Precedent, no MCP | `scratch` | About 29% |
| Agent with Precedent | Reads the memory | `reuse`, citing the positive and the failed `high-lr`, setting aside the 32 px result | About 90% |

The baseline is run once before the demo (`python -m experiments.resnet train scratch holdout receipts/resnet-baseline.safetensors`) and shown from `MEMORY_BASELINE_RECEIPT`. An LLM is not deterministic: rehearse several times. If the agent is unstable, a scripted planner that applies the same evidence rules is the labelled fallback. Phase 2 adds a correction and an expiry run on the same request.

## Agent integration (MCP)

The coding agent never talks to Atlas directly. The workbench (`workbench/app.py`) serves a Streamable HTTP MCP endpoint at `/mcp`, bound to loopback, and runs the agent in an embedded terminal (`workbench/terminal.py`, a PTY over `/terminal/codex`). Atlas credentials and tokens stay server-side. The built path uses Codex. Any MCP-capable agent can connect to the same endpoint, and Claude Code has not been tried.

| Tool | Does |
| --- | --- |
| `experiment_profile` | The job catalog and the suggested task defaults. |
| `search_experiments` | `POST /v1/search`. Candidates with fit labels. Crashed, expired and superseded results never come back. |
| `get_experiment` | A current result and its evidence. |
| `load_weights` | Checkpoint metadata for a cited result. The runner streams the bytes itself and checks the SHA-256. |
| `propose_plan` | `POST /v1/decisions`. Stores the plan as `pending`. The cited, avoided and set-aside refs are what the UI highlights. |
| `run_plan` | Returns the decision, or dispatches a previously approved one. |
| `publish_result` | Publishes a structured finding from the agent. |

The person's confirmation is the browser's **Run plan** button, which approves and dispatches through the platform's conditional updates. **Reject** records the rejection and nothing runs. The runner resolves the cited versions first, streams the exact cited checkpoint, trains on the holdout, publishes the measured result and the new checkpoint, and posts the receipt. `/api/events` relays search candidates, Atlas command activity and change-stream notifications to the browser.

For a temporary HTTPS preview, keep the workbench on loopback behind a proxy and set `MEMORY_REMOTE_PASSWORD` (see [BACKEND.md](BACKEND.md#live-workspace)). The external `/mcp` path is blocked.

## Presenter service

`uvicorn demo.presenter:app --host 127.0.0.1 --port 8100` serves the UI at `/`, holds the four tokens server-side, and calls the platform API and the benchmark commands. The browser only talks to the presenter. It binds to localhost.

**Legacy path.** The live demo runs through `workbench/`, not this presenter. The presenter's scripted producer and planner path (tested against the lookup fixture) is kept as a fallback and as a way to run rehearsals unattended. Its governance routes are Phase 2.

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

The design target is the mockup, [docs/demo/index.html](docs/demo/index.html). The built app is `workbench/web/` (HTML, CSS and JavaScript with xterm.js), served by `workbench/app.py`. It currently has a sidebar with Workspace, Research library and Run comparison, stacked panels and an evidence inspector. Moving it to the mockup's single agent-centred screen is open work. Requirements are in [REQUIREMENTS.md](REQUIREMENTS.md#interface). It is **not** a dashboard: one screen, centred on the agent and the decision.

| Area | Contents |
| --- | --- |
| Top bar | Product name and mark, the four stages (Past experiments, Ask the agent, You decide, Result), Atlas status from `/v1/health` without exposing internals. |
| Centre | The embedded terminal (xterm.js over a localhost WebSocket to a PTY in the demo working directory). Beside it, the experiments list. When the agent calls `propose_plan`, the cited, avoided and set-aside experiments are highlighted (using, avoiding, doesn't fit with the mismatched field named). Crashed experiments should be shown as "never offered". |
| After the run | One result card: the agent on its own against the agent with Precedent, with the 80% target marked. |
| Drawer | Opens only when someone clicks an experiment or an Atlas line. Conditions first, then outcome, rerun command, weights and record. |
| Atlas strip | Along the bottom: the latest real commands from the workbench's `/api/events`, for example `aggregate result_vectors · $vectorSearch + $lookup · 4 docs · 38 ms`. Clicking opens the redacted pipeline in the drawer. |

Both MongoDB elements use only live data from the workbench's `/api/events`. Nothing is hardcoded in the real UI. In the mockup they are simulated.

**"In MongoDB" sentence per stage:**

| Stage | What it shows |
| --- | --- |
| 1 Past experiments | The `insert` commands and change-stream events behind the experiments list. The weights are GridFS files. |
| 2 Ask the agent | The one `$vectorSearch` aggregate with the `project_id` filter, hits and latency, plus the `$lookup` and the fit labels. |
| 3 You decide | The conditional `findOneAndUpdate` from `pending` to `approved`, and the 409 on a second click. |
| 4 Result | The `resolve` re-check of cited versions, the GridFS weights stream, the receipt update and the new `insert`, pushed to the screen by a change stream. |

Use distinct text labels for worked, failed, crashed and doesn't fit. Show conditions before outcomes. Support keyboard use, visible focus, and loading, empty and error states. On narrow screens the drawer is full width.

## Phase 2: governance

Correction, expiry and history are already in the backend (`correct`, `expire`, `history`, `result_versions`). They return to the screen after the four-stage demo is rehearsed: a Correct and an Expire action on an experiment's drawer, each followed by asking the agent again, and a version history in the drawer. Keep this off the main path until then.

## Credits

| Upstream | What inspired us | Use |
| --- | --- | --- |
| [ARA](https://github.com/ARA-Labs/Agent-Native-Research-Artifact/tree/e52a925e9d03b4ada3008653e72f99b04116fca2) at `e52a925e9d03b4ada3008653e72f99b04116fca2`, MIT, Orchestra Research | Dead ends kept as first-class records with a reason; results bound to code, config and evidence. The ResNet example artifact is our pitch example. | Ideas and pitch only. No code, data or runtime in the app. |
| [AutoSci](https://github.com/PKU-DAIR/AutoSci/tree/6bc834a805a1744959a9983809e5d6f0263ef791) at `6bc834a805a1744959a9983809e5d6f0263ef791`, MIT, OmegaWiki Contributors | A list of failed ideas with reasons that agents don't revisit (`/ideate`). We scope it by conditions. | Idea only. |
| [PyTorch](https://pytorch.org), [torchvision](https://github.com/pytorch/vision) and [scikit-learn](https://scikit-learn.org) | ResNet-50, the ImageNet weights `ResNet50_Weights.IMAGENET1K_V1`, and the digits fixture. | Used as libraries. Their licenses apply. |

See [NOTICE.md](NOTICE.md). The platform, presenter, benchmark, UI and mockup are event-built.

