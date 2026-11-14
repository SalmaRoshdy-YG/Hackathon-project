# Backend setup and frontend handoff

`platform_api/` is the reusable Atlas backend. `demo/` provides the presenter service and checks. It calls the same API a separate client would use.

**Status.** Built and offline-testable, but not yet verified against the event Atlas Sandbox (see [TASKS.md](TASKS.md#verification-gates)). The ResNet experiment profile (`MEMORY_EXPERIMENT_MODULE=benchmark.profile`), the MCP server and the weights routes are not built yet. The presenter's producer and planner modules are the scripted agent path, which is also the fallback for the Claude Code demo. The `memory: on|off` proposal field exists for the backend's own contract tests. The demo's baseline is Claude Code run outside Precedent, not this flag.

## Run it

Use Python 3.11. On this workstation the repository already has an ignored `.env` with a scoped Atlas account and four server-side demo identities.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-local.txt
# New checkout only: create .env and fill in the Sandbox connection string.
.\.venv\Scripts\python.exe -m platform_api.setup
.\.venv\Scripts\python.exe -m platform_api.preflight
```

Start the API on its own:

```powershell
.\.venv\Scripts\python.exe -m uvicorn platform_api.app:app --host 127.0.0.1 --port 8000
```

The standalone API supports publishing, search, correction, expiry, and history. Set `MEMORY_EXPERIMENT_MODULE` to enable proposals and guarded execution.

## Optional browser presenter

Configure the new experiment and its optional guided workflow in the local environment. A fresh local environment can be created with python -m demo.setup.

~~~dotenv
MEMORY_EXPERIMENT_MODULE=benchmark.profile
MEMORY_PRESENTATION_MODULE=your_experiment.presentation
~~~

Start `python -m uvicorn demo.presenter:app --host 127.0.0.1 --port 8100` in a separate terminal.

Put the teammate's static build in `demo/web/` or set `MEMORY_WEB_DIR` to the absolute path of their build output. Open `http://127.0.0.1:8100/`. For frontend development with a separate dev server, use its reverse proxy for `/demo`; preserve the presenter's expected Host and Origin or test the static build on port 8100. Do not put bearer tokens in frontend environment variables.

For teammates using their own Sandbox account: allow their development IP in Atlas, grant a database user read/write access on the selected database, and run preflight to create and validate collections and the vector index. Never commit the connection string. Start the presenter after the platform is up.

## Browser contract

The [presenter routes](PLATFORM.md#presenter-service) define request fields. Running services expose `/docs` and `/openapi.json` on their own ports. The browser uses relative URLs:

- `GET /demo/state` returns findings, the latest decision, the most recent evidence cards, all recent receipts, and the active stream modes. The latest stage and evidence-card snapshot live for the presenter process; findings, decisions and receipts are durable.
- `new EventSource('/demo/events')` delivers named `atlas` and `change` events. Use `change` to refresh state for the current view. Atlas events contain `command`, `collection`, `ms`, `docs`, `scope`, `ok` and a redacted `shape`; these are from PyMongo monitoring. In particular, `scope: "isolation-check"` labels commands executed with the second project identity. Results and decisions use scoped change streams. Reconnects replay recent events when available.
- `POST /demo/agent-a`, then `POST /demo/agent-b` with `{"memory":"off"}` (backend contract tests only; the demo baseline is recorded outside Precedent). Call Approve, then Execute, separately. Next run Agent B with `{"memory":"on"}`. Reject prevents execution. The presenter waits for expected versions to appear in the index after publication or correction.
- Select result IDs from the producer response for Correct and Expire. Send `result_id`, `expected_version`, and a reason. After each call, `POST /demo/rerun` repeats the last memory setting on the same task. Approve and execute each new decision. History and evidence are available under `/demo/results/{result_id}/history` and `/demo/results/{result_id}/evidence?version=1`.
- `POST /demo/isolation-check` checks that the unseeded second project returns no candidates and direct result/evidence reads return 404. The guided platform check also verifies selectivity with a distinct, authorized sentinel in each project.

An expired finding remains listed for inspection during its retention window.

## Verification

```text
python -m unittest discover -s tests
python -m platform_api.preflight
python -m tests.check_standalone
python -m demo.check_platform
python -m demo.check_presenter
```

The integration checks and rehearsals create fresh project IDs and write local receipts under the ignored `receipts/` folder. To clear the configured demo project, stop the presenter and run `python -m demo.reset --project <configured demo project>`, then restart. The reset refuses any project other than the configured `demo-*` namespace. No database or index is dropped.

The Atlas tests use BGE embeddings on CPU and a test planner. BGE's 384 floats are padded with zeros for the 1536-dimensional local index, which preserves cosine ordering. The first run downloads the model. MongoDB Atlas runs vector retrieval and the authoritative checks in the same pipeline in either mode.

For the planned OpenAI path, install `requirements.txt`, set `OPENAI_API_KEY` locally, and set `MEMORY_EMBEDDER=openai`. Planner settings belong to the selected experiment. Use a fresh project when changing embedding provider and rerun preflight and rehearsal; citations are checked against the same authoritative conditions in both modes. The OpenAI mode needs a team key for a live check.


## Switch experiments

Set `MEMORY_EXPERIMENT_MODULE` to a trusted, importable Python module and use it for both services. Give new demo data its own project namespace. Keep a profile ID stable for compatible code and change it when an existing approval should no longer authorize execution.

- Export `EXPERIMENT` with a versioned ID, an ordered job catalog, one baseline, the condition keys that must match, a task validator, a predicate for whether positive evidence supports a job, and a runner that returns the measured receipt. The platform owns project scope, version and expiry checks, evidence labels, approval, execution claims, and receipt storage. The HTTP client supplies an approved decision ID. Registered server code determines what can run.
- Evidence uses flat scalar conditions, a fixture revision, method configuration, a measurement and threshold, and provenance. Completed receipts include a reproduction command, fixture hash, and runtime or library versions. Use `reproduce.versions` for new profiles and include other input hashes as needed. A profile can declare that a calibration finding applies to a holdout task by omitting the split field from its match keys.
- To use the guided presenter, set `MEMORY_PRESENTATION_MODULE` to a module exporting `PRESENTATION` with the search question, task conditions, producer and planner module names, a correction factory, and display metadata. The producer emits `refs` and `receipts` maps keyed by finding label, and can set `index_labels` to the subset the demo must see in its first search. The planner accepts `--memory on|off`, posts a proposal to Atlas through the API, and prints the pending decision with `evidence_candidates`. The presenter endpoints and event shapes stay the same.
- `python -m tests.check_lookup_profile` demonstrates a second profile end to end. It uses a different catalog, an integer applicability field, and a measured comparison count.
