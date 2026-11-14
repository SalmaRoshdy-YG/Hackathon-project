# Platform contract

This is the technical contract for [REQUIREMENTS.md](REQUIREMENTS.md) (R1–R12). One live research handoff on a fast CPU benchmark: Agent A publishes measured findings, a fresh Agent B finds them through event Atlas Vector Search, the platform labels which ones apply, B recommends a job, a human approves, the job runs, and human corrections and expiry change B's next recommendation. The same contract can support more agents and studies later through project membership, versioned results, and new job catalogs.

We build our own platform. No ARA or AutoSci code, runtime or adapter is on the build path. See [Credits](#credits).

## Shared entry point

Use Python 3.11, FastAPI and PyMongo. P1 owns `uvicorn platform_api.app:app --host 127.0.0.1 --port 8000` and the HTTP JSON contract below. P2 owns the presenter service that serves the UI and drives the demo (see [Presenter service](#presenter-service)). Callers can work against a stub serving these payloads until the real service is up. P4 owns the top-level rehearsal. Backend startup and the live frontend handoff are in [BACKEND.md](BACKEND.md).

The service maps opaque bearer tokens in server-side `MEMORY_TOKENS_JSON` to a trusted `project_id`, `agent_id`, and `role`. Example mapping entry: `{"<publisher-token>":{"project_id":"team-run-01","agent_id":"agent-a","role":"publisher"}}`. Issue a publisher token for Agent A, a reader token for Agent B, a maintainer token for the human (corrections, expiry, approval), and a reader in a second project for the isolation check. Rehearsals use fresh project IDs in the same Atlas database and index. Each process receives only its own token. Atlas and provider credentials stay with the service and the trusted runner. Tokens never reach the browser. The service sets project and author from the token and rejects caller-supplied identity fields.

| Role | Can |
| --- | --- |
| reader | search, read current results and evidence, list findings, read history, resolve, propose a decision, execute its own approved decision |
| publisher | reader rights, plus publish, and correct or expire its own records |
| maintainer | reader rights, plus publish, correct and expire any record in the project, approve or reject decisions |

## Results

Every result has `schema_version: 1`, `hypothesis`, `fixture_revision`, flat `conditions` and `configuration` objects with scalar values, `metric` with name, value, unit, operator and threshold, `execution` (`completed|crashed|timed_out`), `validity` (`valid|invalid|inconclusive`), `direction` (`positive|negative|undetermined`), `evidence`, `source`, and UTC `expires_at`. A completed, valid measurement with a receipt supports a positive or negative direction according to the threshold. Other combinations require `undetermined` and may have a null metric value. Such records are stored and shown to humans with a "crashed" or "inconclusive" label, but search, applicability and resolve only use completed, valid results. A crash never counts as a failed idea.

Example body for `POST /v1/results`. Evidence is a small inline JSON receipt. The API serves it under the result's visibility and lifecycle.

```json
{
  "schema_version": 1,
  "hypothesis": "A shared phrase dictionary for cohort A will keep independent DEFLATE payloads at or below 40% of input bytes.",
  "fixture_revision": "short-events-v1",
  "conditions": {"cohort": "A", "split": "calibration", "codec": "zlib-wrapped-deflate", "dictionary_revision": "phrases-v1"},
  "configuration": {"job_id": "dict-a-l1", "level": 1, "dictionary_family": "A"},
  "metric": {"name": "wire_ratio", "value": 0.2607758621, "unit": "ratio", "operator": "<=", "threshold": 0.4},
  "execution": "completed",
  "validity": "valid",
  "direction": "positive",
  "evidence": {"kind": "job_receipt", "data": {"run_id": "cal-a-1", "input_bytes": 928, "output_bytes": 242, "roundtrip_ok": true,
    "reproduce": {"command": "python -m benchmark.run --job dict-a-l1 --cohort A --split calibration", "fixture_sha256": "<hex>", "dictionary_sha256": "<hex>", "zlib_version": "1.3.1", "python_version": "3.11.9"}}},
  "source": {"system": "benchmark", "source_agent": "agent-a", "record": "dict-a-l1"},
  "expires_at": "2026-11-15T00:00:00Z"
}
```

Use a fresh future timestamp in the harness. `evidence.data.reproduce` is required for completed runs (R11). `Ref` is `{"result_id":"<uuid>","version":1}`. `Result` is the publish body without `evidence`, plus `Ref` fields, `author_id` and `status` (`current|expired`). Output errors use `{"detail":"<stable code>"}`.

`Applicability` is computed by the platform against the caller's task conditions: `{"status":"applies|mismatch","mismatches":[{"field":"cohort","wanted":"A","found":"B"}]}`. The rule is exact agreement on `fixture_revision`, `conditions.cohort`, `conditions.codec` and `conditions.dictionary_revision`. A calibration result applies to a holdout task (declared transfer); split is otherwise ignored. A result with execution or validity other than completed and valid is never returned by search.

## Routes

| Route | Request and success response |
| --- | --- |
| `GET /v1/health` | → 200 `{"atlas":"ok","index":"READY","database":"<name>","project_id":"<from token>"}`. 503 with the failing part if Atlas or the index is unavailable. |
| `POST /v1/results` | Publish body → 201 `Ref`. Version starts at 1. |
| `GET /v1/results` | → 200 `{"items":[Result]}`: every head in the caller's project, including expired ones with `status:"expired"` and crashed ones. For the Research and Governance pages. Agents do not use it for decisions. |
| `POST /v1/search` | `{"question":"What previously helped shrink one-at-a-time cohort A telemetry packets?","conditions":{"fixture_revision":"short-events-v1","cohort":"A","codec":"zlib-wrapped-deflate","dictionary_revision":"phrases-v1","split":"holdout"}}` → 200 `{"candidates":[{"result":Result,"score":0.82,"applicability":Applicability}]}`. Only current, usable results. Mismatched results are returned with their label so the agent and the UI can show why they were set aside. `conditions` is optional; without it `applicability` is null. May return an empty list. |
| `GET /v1/results/{id}?version=1` | → 200 `Result`. An omitted version means current. 404 if expired or superseded. |
| `GET /v1/results/{id}/evidence?version=1` | → 200 `{"result_id":"<uuid>","version":1,"evidence":{…}}`. Same version rules. |
| `GET /v1/results/{id}/history` | → 200 `{"result_id":"<uuid>","status":"current|expired","current_version":2,"versions":[{"version":1,"state":"superseded","result":Result,"evidence":{…},"replaced_at":"…","replaced_by":"maintainer","reason":"…"},{"version":2,"state":"current",…}],"events":[{"at":"…","actor":"…","action":"publish|correct|expire","version":2,"reason":"…"}]}`. For humans (R7, R8). Any project role. Old versions here are for inspection only: search, read, evidence and resolve never accept them. |
| `POST /v1/results/{id}/correct` | `{"expected_version":1,"reason":"Receipt was linked to the wrong cohort","replacement":{…full publish body…}}` → 200 `Ref` with version 2. |
| `POST /v1/results/{id}/expire` | `{"expected_version":1,"reason":"Superseded by newer measurements"}` → 200 `{"result_id":"<uuid>","version":1,"expired":true}`. A scheduled expiry uses the publish timestamp. |
| `POST /v1/resolve` | `{"refs":[Ref]}` → 200 `{"results":[Result]}` in request order if every ref is current and usable. Validate immediately before dispatch. |
| `POST /v1/decisions` | Agent B's proposal: `{"request":"…","memory":"on|off","conditions":{…},"candidates":[{"ref":Ref,"score":0.86,"applicability":Applicability}],"job_id":"dict-a-l6","used_refs":[Ref],"skipped_jobs":[{"job_id":"dict-b-l6","reason":"…","refs":[Ref]}],"rejected_candidates":[{"ref":Ref,"reason":"…"}],"reason":"…","model":"gpt-4.1-mini-2025-04-14"}` → 201 `Decision` with `status:"pending"`. 422 if the job is not in the catalog, or a used ref is not current or does not apply. |
| `GET /v1/decisions/{id}` | → 200 `Decision`. |
| `POST /v1/decisions/{id}/approve` | `{"note":"Looks right"}` → 200 `Decision` with `status:"approved"`, `decided_by`, `decided_at`. Maintainer only. 409 unless pending. |
| `POST /v1/decisions/{id}/reject` | `{"reason":"Try the baseline first"}` → 200 `Decision` with `status:"rejected"`. Maintainer only. 409 unless pending. Nothing runs. |
| `POST /v1/decisions/{id}/execute` | The platform claims the approved decision atomically, rechecks citations and executes the registered job locally. Returns 201 `Decision` with `status:"executed"` and a server-generated receipt, or `status:"aborted"` without a run if citations were revoked. 409 unless approved and unclaimed. Only the proposer or a maintainer may dispatch. |
| `POST /v1/decisions/{id}/receipt` | Compatibility alias for trusted execution; caller-supplied measurements are not stored. |
| `GET /v1/decisions` | Recent decisions scoped to the project, including receipts. |
| `GET /v1/activity` | Authenticated internal SSE endpoint supplying real PyMongo command events to the presenter. |

`Decision` is the proposal plus `decision_id`, `project_id`, `proposed_by`, `status` (`pending|approved|rejected|running|executed|aborted`), `decided_by`, `decided_at`, `note` or `reason`, and `receipt`.

Use 401 for missing or unknown token, 403 for role denial on visible records, 404 for absent, out-of-scope, expired or historical reads on agent paths and unusable resolve refs, 409 for a stale write or a decision in the wrong state, 422 for invalid bodies, and 503 for unavailable search. A resolve failure aborts dispatch without running the job; the human can review a fresh proposal. Fail closed on authorization, dependency or validation errors. Token roles and source fields are kept distinct.

## Atlas storage and lifecycle

- `MEMORY_ATLAS_URI` and `MEMORY_ATLAS_DB` point to the event Sandbox. `results` holds the authoritative current head keyed by UUID with `project_id`, `author_id`, `version`, `search_key`, normalized fields, inline evidence, `expires_at`, `purge_at` and an `events` array (actor, time, action, version, reason). Each correction copies the current head into `result_versions` and replaces the head, in one transaction conditional on project, current version and active expiry. Manual expiry atomically sets `expires_at` to service time and appends an event. The original publisher keeps ownership.
- `result_versions` holds superseded payloads and their evidence keyed by `(result_id, version)`, with `project_id` and `purge_at`. Only the history route reads it.
- `result_vectors` holds immutable search entries keyed by a generated `search_key` with `project_id`, `result_id`, `version`, `embedding`, `embedding_model`, and `purge_at`. Stage the vector before committing the head. A candidate is accepted only if its key and version match the authoritative head. An orphan or old key is inert and eligible for cleanup. The `research_memory_v1` index has a 1536-dimensional cosine vector field `embedding` and filter fields `project_id` and `embedding_model`. Embed hypothesis, summarized measurement, fixture and conditions using `text-embedding-3-small` at 1536 dimensions, and embed the search question with the same model. Service secrets use `OPENAI_API_KEY`. The verified key-free path uses BGE CPU embeddings with zero padding in a separate `research_memory_local_v1` index. Both paths execute the same Atlas aggregation. [Embedding model](https://developers.openai.com/api/docs/models/text-embedding-3-small)
- **Search is one Atlas aggregation.** MongoDB, not Python, does retrieval, isolation, the stale-version check, expiry and applicability in a single `aggregate` on `result_vectors`. Python only embeds the question and passes the task conditions in. Recheck lifecycle at direct read, evidence read, resolve, decision create and dispatch with equivalent MongoDB filters on `$$NOW`. Both projects get their own sentinel in the selectivity test. [Atlas Vector Search](https://www.mongodb.com/docs/vector-search/query/aggregation-stages/vector-search-stage/) · [$lookup](https://www.mongodb.com/docs/manual/reference/operator/aggregation/lookup/)

```js
db.result_vectors.aggregate([
  { $vectorSearch: { index: "research_memory_v1", path: "embedding", queryVector: q,
      filter: { project_id: P, embedding_model: M },              // isolation, from the token
      exact: true, limit: 12 } },             // ANN fallback: numCandidates 240
  { $addFields: { score: { $meta: "vectorSearchScore" } } },
  { $lookup: { from: "results", let: { id: "$result_id", v: "$version", key: "$_id" }, as: "head",
      pipeline: [ { $match: { $expr: { $and: [
        { $eq: ["$_id", "$$id"] }, { $eq: ["$project_id", P] },
        { $eq: ["$version", "$$v"] }, { $eq: ["$search_key", "$$key"] }, // rejects stale entries
        { $gt: ["$expires_at", "$$NOW"] },     // expired → no match, before TTL runs
        { $eq: ["$execution", "completed"] }, { $eq: ["$validity", "valid"] } ] } } },
        { $project: { evidence: 0 } } ] } },
  { $unwind: "$head" },                        // drops stale, expired and crashed hits
  { $addFields: { mismatches: { $filter: { as: "m", cond: { $ne: ["$$m.found", "$$m.wanted"] }, input: [
      { field: "fixture_revision", wanted: C.fixture_revision, found: "$head.fixture_revision" },
      { field: "cohort", wanted: C.cohort, found: "$head.conditions.cohort" },
      { field: "codec", wanted: C.codec, found: "$head.conditions.codec" },
      { field: "dictionary_revision", wanted: C.dictionary_revision, found: "$head.conditions.dictionary_revision" } ] } } } },
  { $addFields: { applicability: { status: { $cond: [{ $eq: [{ $size: "$mismatches" }, 0] }, "applies", "mismatch"] }, mismatches: "$mismatches" } } },
  { $limit: 8 }
])
```

- **Change streams drive the live UI.** The presenter opens one change stream on `results` and one on `decisions`, each with a `$match` on `fullDocument.project_id` (use `fullDocument: "updateLookup"`). Every publish, correction, expiry, approval and receipt reaches the UI within a second without polling. The UI never reloads to show new findings. [Change streams](https://www.mongodb.com/docs/manual/changeStreams/)
- **Atlas activity is captured, not described.** The platform registers a PyMongo `CommandListener` that records each command's name, collection, duration in ms, documents returned, and a redacted command shape (query vector shown as `[1536 floats]`, no URIs or tokens). The presenter serves it on `/demo/events`. [Command monitoring](https://pymongo.readthedocs.io/en/stable/api/pymongo/monitoring.html)
- Preflight confirms the event Sandbox supports `$vectorSearch` with a filter field, `$lookup` after `$vectorSearch`, multi-document transactions, change streams and TTL indexes. If change streams are unavailable on the Sandbox tier, the presenter polls `results` and `decisions` by `updated_at` every 500 ms and the UI labels the panel “polling”.
- `decisions` holds one document per decision. Approve, reject, dispatch and receipt are conditional updates on `status`, so a decision can't be approved twice or executed without approval.
- Expiry hides the record from every agent path immediately. TTL on each collection's BSON Date `purge_at` with `expireAfterSeconds: 0` is asynchronous cleanup: heads and vectors get `expires_at + 24h`, history entries get the head's purge date. Best-effort deletion of a retired vector after correction or expiry can shorten retention. The API stays correct if deletion or TTL lags. [Atlas TTL](https://www.mongodb.com/docs/manual/core/index-ttl/)

## Experiment profiles

The API and presenter load the same trusted Python profile using `MEMORY_EXPERIMENT_MODULE`. Job IDs, baseline, task validation, match fields, evidence support, and the runner come from the profile. The selected profile ID is persisted in decisions and checked again before dispatch. The example pipeline and workflow below describe the default compression profile. See [BACKEND.md](BACKEND.md#switch-experiments) for the adapter contract and the verified lookup example.

## Benchmark and agent decision

Use `short-events-v1`, a synthetic independent-event compression fixture. Each message is compressed on its own, as if sent one at a time. A pre-shared dictionary models a receiver that already knows the deployment's event vocabulary. Count all zlib stream bytes, including headers and the dictionary ID. Dictionary distribution is a fixed setup cost outside the per-message metric and should be disclosed in the demo. No model is trained anywhere.

Generate 32 ASCII tokens per cohort A and B using the first 24 hex characters of SHA-256 of `"{cohort}:{i}"` for indices 0–31. Join each cohort's 32 tokens with `|` for its pre-shared `phrases-v1` dictionary. Make eight rows per split, each the first 16 hex characters of SHA-256 of `"{cohort}:{split}:{j}"` followed by four tokens, all joined by `|`. Use token indices `(4*j + offset + k) % 32`, where `j=0..7`, `k=0..3`, and offset is 0 for `calibration` and 1 for `holdout`. Each split has 928 input bytes. Compress each row in its own `zlib.compressobj(level, zlib.DEFLATED, 15, **kwargs)` stream, with `zdict` only for dictionary jobs. Decompress with identical dictionary and window settings and verify exact equality and end-of-stream for all rows. Score `wire_ratio = sum(output_bytes) / sum(input_bytes)` with `<= 0.40` as success. Record the rerun command, fixture and dictionary hashes, and zlib and Python versions in the receipt.

| Agent A run | Input | Configuration | Planning probe |
| --- | --- | --- | --- |
| Promising finding | A calibration | `dict-a-l1`, level 1, dictionary A | 242/928, positive |
| Failed approach | A calibration | `dict-b-l1`, level 1, dictionary B | 760/928, completed valid negative with all rows decoded |
| Other cohort | B calibration | `dict-b-l1`, level 1, dictionary B | 234/928, positive under cohort B |
| Crashed run | A calibration | `dict-c-l1`, dictionary C, which is not provisioned | Runner fails before measuring: `crashed / invalid / undetermined`, null metric |

Agent A runs these four jobs, turns each runner receipt into a publish body with `python -m benchmark.publish`, publishes with its own token, then exits. The crashed run shows humans that a crash is labelled differently from a failed idea; search never returns it.

Agent B uses the same request, conditions, one-job budget, prompt and ordered catalog every time. Request: “Can we get individually transmitted cohort A telemetry well under half its original size on unseen events? Aim for 40% or less and spend one trial.” Search question: “What previously helped shrink one-at-a-time cohort A telemetry packets?” A's published text uses “independent DEFLATE event payloads” and “shared phrase dictionaries”, so finding it needs search by meaning. Smoke-check the paraphrase in a set with five unrelated valid findings and the cohort B finding. The required findings must be among the candidates, and at least one applicable finding must rank above all unrelated ones.

Demo and rehearsal states run in this order in one project, with the same request each time:

| State | What changed | Expected recommendation on A holdout | Planning probe |
| --- | --- | --- | --- |
| Memory off | B skips search | `plain-l1`, no dictionary | 686/928 |
| Memory on | — | `dict-a-l6`. Cites the promising finding v1 and the failed approach v1. Skips `dict-b-l6` because dictionary B failed on cohort A. Rejects the cohort B finding as a mismatch. | 238/928 |
| After correction | Maintainer corrects the promising finding: the receipt belonged to cohort B. v2 is the measured `dict-a-l1` on B calibration (probe 760/928, valid negative). | `plain-l1`. v2 now shows as a cohort mismatch. Dictionary B still skipped because of the failed approach. | 686/928 |
| After correction and expiry | Maintainer expires the failed approach (“Superseded by newer measurements”). | `plain-l1`. The failed approach is no longer among the candidates and shows as Expired in the UI. `dict-b-l6` is now skipped for lack of applicable evidence instead of a known failure. | 686/928 |

The job changes once (on → after correction). The expiry changes the evidence and the skip reasons visibly, but not the job, because nothing applicable supports a dictionary by then. Say so in the demo. Scheduled expiry (an `expires_at` that passes on its own) is tested separately in the lifecycle gate, not in the live demo.

The third candidate, `dict-b-l6`, measured 760/928 on A holdout in the probe. Measure it during fixture validation so every candidate is accounted for. Each finding should land on the expected side of the threshold. Byte counts can vary by zlib version, which the runner records.

The catalog order is `plain-l1`, `dict-a-l6`, `dict-b-l6`. The no-evidence baseline is the dictionary-free job because it assumes no shared receiver vocabulary. B fetches each candidate's versioned evidence before deciding and attaches the measurement and the platform's applicability label to the model context. In OpenAI mode, use one stateless `gpt-4.1-mini-2025-04-14` Responses request per decision with a JSON schema for `job_id`, `used_refs`, `skipped_jobs` with reasons and refs, `rejected_candidates` with refs and reasons, and `reason`. Instructions favor a bounded follow-up with applicable support, then the baseline. Level 1 supports testing the same dictionary family at level 6. A valid negative discourages repeating that dictionary family under the same conditions and is advisory across compression levels. Only results labelled `applies` may appear in `used_refs` or as reasons for skips; the platform rejects the decision otherwise. Keep mismatched refs in `rejected_candidates`. [Planner model](https://developers.openai.com/api/docs/models/gpt-4.1-mini)

P3 owns:
- `python -m benchmark.run --job dict-a-l6 --cohort A --split holdout`: one measured run, receipt to stdout.
- `python -m benchmark.publish --out receipts/producer.json`: Agent A's four runs and publishes. Accepts `--project-token-env`.
- `python -m benchmark.agent --memory on --base-url http://127.0.0.1:8000 --out receipts/on.json`: Agent B searches, decides and posts the proposal. Prints the `decision_id`. Never executes. `--memory off` skips search.
- `python -m benchmark.execute --decision ID`: requests trusted execution and prints the resulting decision and receipt; the platform atomically claims the approval, resolves the cited refs, runs the registered configuration once, and stores the receipt.

The tested rules mode is stateless and uses the same evidence-first policy, task, catalog and budget for every state. B reads its token from `MEMORY_TOKEN`. Receipts include request, model, catalog and budget, candidates with applicability, selected and skipped jobs, exact used refs, approval, executed configuration, runtime, status, metric, byte counts, hashes and round-trip evidence. The planning arithmetic above came from a local Python 3.11 standard-library probe. Build acceptance requires receipts from the new runner.

## Presenter service

P2 owns `uvicorn demo.presenter:app --host 127.0.0.1 --port 8100`. It serves the UI at `/`, holds the four tokens server-side, and calls the platform API and P3's commands. The browser only talks to the presenter. It binds to localhost.

| Route | Does |
| --- | --- |
| `GET /demo/state` | Current stage, health from `GET /v1/health`, project, memory setting, findings from `GET /v1/results`, latest decision and receipts. |
| `GET /demo/events` | Server-sent events: `change` events from the change streams (operation, collection, result or decision ID, version, status) and `atlas` events from the command listener (command, collection, ms, docs, redacted shape). The UI subscribes once on load. |
| `POST /demo/agent-a` | Runs `benchmark.publish` with A's token. |
| `POST /demo/agent-b` | `{"memory":"on|off"}`. Runs `benchmark.agent` with B's token. Returns the pending decision. |
| `POST /demo/rerun` | Repeats B's last request with the same memory setting. |
| `POST /demo/decisions/{id}/approve` and `/reject` | Forwards with the maintainer token. |
| `POST /demo/decisions/{id}/execute` | Uses the same trusted platform dispatcher as `benchmark.execute`. |
| `POST /demo/governance/correct` | `{"result_id":…,"expected_version":…,"reason":…}`. Uses the prepared cohort B replacement from P3's receipt. |
| `POST /demo/governance/expire` | `{"result_id":…,"expected_version":…,"reason":…}`. |
| `GET /demo/results/{id}/history` | Forwards the history route. |
| `GET /demo/results/{id}/evidence?version=1` | Forwards the scoped, current evidence route. |
| `POST /demo/isolation-check` | Runs the same search and a direct read with the second project's token and returns both responses (expect no candidates and 404). |

`python -m demo.reset --project demo-live` clears the demo project before a presentation.

## User interface

P4 owns `demo/web/`, a static HTML, CSS and JavaScript bundle served by the presenter. Requirements are in [REQUIREMENTS.md](REQUIREMENTS.md#interface). Visual direction: dark green sidebar, light workspace, restrained green accents, our own product name and mark. Show Atlas status from `/v1/health` without exposing internals.

| Page | Contents |
| --- | --- |
| Demo (default) | Seven stages from the demo sequence, with a Next button the presenter controls. Each stage shows agent activity and the evidence cards for that step. Stage 3 groups candidates as applicable success, applicable failure, and doesn't match, with the mismatched field named. Stage 4 has Approve and Reject. Stage 5 shows the measured result against the baseline and the 0.40 target. Stage 6 has Correct and Expire buttons and a Re-run after each. Stage 7 shows the four receipts side by side. |
| Research | Searchable list from `GET /v1/results` with status (current, expired, superseded count), outcome label, execution label, cohort and conditions, and source agent. A detail view shows evidence, the rerun command, provenance and version history. |
| Governance | Findings to review, Correct and Expire forms with a required reason, the previous and current versions side by side, and the change history. |
| Settings | Atlas health, project, memory on/off for Agent B, environment info (model, embedding model, zlib version), and the isolation check button with its result. |

**MongoDB on screen.** Two elements make the database's work visible during the whole demo. Both use only live data from `/demo/events`; nothing is hardcoded.

- **Atlas activity strip** along the bottom of every page: the latest commands as they run, for example `aggregate result_vectors · $vectorSearch + $lookup · 4 docs · 38 ms`, `update results · transaction · v1 → v2`, `change stream · results · update`. Clicking a line opens the redacted pipeline in the inspector.
- **“In MongoDB” callout** at each Demo stage, one sentence built from that stage's real events:

| Stage | What the callout shows |
| --- | --- |
| 1 Agent A discovers | Four `insert` commands and their change-stream events arriving; findings appear in the list live. |
| 2 MongoDB remembers | The `$vectorSearch` aggregate with the `project_id` filter, the paraphrased question, hits and latency. |
| 3 Agent B recommends | The same pipeline's `$lookup` and applicability stages: which hits matched the live record, and the cohort mismatch computed in the database. |
| 4 Human approves | The conditional `findOneAndUpdate` from `pending` to `approved`, and the 409 on a second click. |
| 5 Agent B executes | `resolve` re-reading the cited versions, then the receipt `update` and its change event. |
| 6 Governance | The correction transaction (head replaced, old version copied to `result_versions`), the expiry `update` of `expires_at`, and the stale index entry still present but dropped by the `$lookup`. TTL `purge_at` shown as future cleanup that nothing waits on. |
| 7 Updated decision | Side-by-side receipts with the exact versions each run read from Atlas. |

Settings shows the isolation check as two real commands: the same `$vectorSearch` with the other project's filter returning nothing, and the direct `find` returning no document.

A right-hand evidence inspector follows the current stage or selection: conditions first, then outcome labels (execution, validity, direction), metric and threshold, evidence receipt with the rerun command, applicability, provenance and version. For a decision it shows the cited versions, skipped jobs, ruled-out findings, approval and the receipt. Use distinct text labels for a valid negative, a crash and a mismatch. Show conditions before the outcome. Support keyboard use, visible focus, and loading, empty and error states. On narrow screens the inspector stacks below.

## Credits

| Upstream | What inspired us | Use |
| --- | --- | --- |
| [ARA](https://github.com/ARA-Labs/Agent-Native-Research-Artifact/tree/e52a925e9d03b4ada3008653e72f99b04116fca2) at `e52a925e9d03b4ada3008653e72f99b04116fca2`, MIT, Orchestra Research | Dead ends kept as first-class records with a reason; results bound to code, config and evidence. The ResNet example artifact is our pitch example. | Ideas and pitch only. No code, data or runtime in the app. |
| [AutoSci](https://github.com/PKU-DAIR/AutoSci/tree/6bc834a805a1744959a9983809e5d6f0263ef791) at `6bc834a805a1744959a9983809e5d6f0263ef791`, MIT, OmegaWiki Contributors | A list of failed ideas with reasons that agents don't revisit (`/ideate`). We scope it by conditions. | Idea only. |

P2 adds `NOTICE.md` with these credits and links. Platform, presenter, benchmark, harness and UI are event-built.
