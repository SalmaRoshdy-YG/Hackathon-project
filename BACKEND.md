# Backend setup and frontend handoff

`platform_api/` is the reusable Atlas backend. `demo/` provides the presenter service and checks. It calls the same API a separate client would use.

**Status.** The platform, the ResNet-50 digits experiment and the live workspace are built, and a teammate reports them verified on the event Sandbox (see [TASKS.md](TASKS.md#handoffs)). The `demo/` presenter is the earlier scripted-agent path, kept as a fallback. The `memory: on|off` proposal field exists for the backend's own contract tests. The demo's baseline is the agent run outside Precedent, not this flag.

## Live workspace

Use Python 3.11, Node.js, and a signed-in installation of Codex. Set the local Atlas credentials and project tokens as described below.

On the NVIDIA demo workstation, install the CUDA 13.2 builds of PyTorch and TorchVision. Use an NVIDIA driver that supports CUDA 13.2. The availability check should print `True` and the GPU name.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-workbench.txt -r requirements-resnet.txt
.\.venv\Scripts\python.exe -m pip install --no-cache-dir torch==2.15.0+cu132 torchvision==0.29.2+cu132 --index-url https://download.pytorch.org/whl/cu132
.\.venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name() if torch.cuda.is_available() else 'CPU')"
npm ci
.\.venv\Scripts\python.exe -m platform_api.preflight
```

On a CPU-only machine, use `torch==2.15.0+cpu torchvision==0.29.2+cpu` with `--index-url https://download.pytorch.org/whl/cpu` in the PyTorch install command.

Start the platform in one terminal.

```powershell
$env:MEMORY_EXPERIMENT_MODULE = 'experiments.resnet'
.\.venv\Scripts\python.exe -m uvicorn platform_api.app:app --host 127.0.0.1 --port 8123
```

Start the workspace in another. Create the independent baseline once for a side-by-side comparison.

```powershell
$env:MEMORY_API_URL = 'http://127.0.0.1:8123'
$env:MEMORY_EXPERIMENT_MODULE = 'experiments.resnet'
New-Item -ItemType Directory -Force receipts | Out-Null
.\.venv\Scripts\python.exe -m experiments.resnet train scratch holdout receipts/resnet-baseline.safetensors |
  Set-Content -Encoding utf8 receipts/resnet-baseline.json
$env:MEMORY_BASELINE_RECEIPT = 'receipts/resnet-baseline.json'
.\.venv\Scripts\python.exe -m uvicorn workbench.app:app --host 127.0.0.1 --port 8124
```

In a third terminal, populate an empty project with three measured calibration runs and one example crash record. This downloads the TorchVision ImageNet V1 initialization on first use and uploads two checkpoints. Run this once per project.

```powershell
$env:MEMORY_API_URL = 'http://127.0.0.1:8123'
.\.venv\Scripts\python.exe -m experiments.resnet seed
```

Open [the local workspace](http://127.0.0.1:8124). In the Research library, check that the calibration results have appeared. Open the Codex terminal in Workspace. Once the Codex prompt appears, choose **Insert suggested prompt**, then press Enter in the terminal. Review the cited evidence and choose **Run plan**. The trained checkpoint and new finding appear in Run comparison and in the Research library. If Codex is outside PATH, set `MEMORY_CODEX_BIN` to the executable path before starting the workspace.

The Codex terminal connects to the loopback MCP endpoint. The workspace keeps Atlas credentials server-side. The ResNet runner streams the exact checkpoint cited by the plan, checks the SHA-256 before loading it, trains on a split disjoint from calibration, and publishes the observed accuracy and output weights. The locally measured comparison uses four epochs per run. Scratch trains the full model from random initialization, and reuse trains the head with the retrieved backbone frozen, so elapsed times describe the two configurations, including their different trainable parameter counts. The receipt records the device in `configuration.device`. The `elapsed_seconds` metric covers training and evaluation. GridFS transfer and setup time are outside that metric. The deck's ImageNet and GPU-hour figures are simulated.

For another experiment, set `MEMORY_EXPERIMENT_MODULE` to its registered profile in both services, or leave it unset to browse, publish, and search findings without a runner. The optional `DEFAULTS` profile dictionary supplies a suggested `question` and task `conditions`. `MEMORY_BASELINE_RECEIPT` is optional.

For a temporary HTTPS preview, keep the workbench listening on loopback and forward it through an HTTPS proxy that preserves Host and WebSocket upgrades. Set a unique random `MEMORY_REMOTE_PASSWORD` on the workbench and set `MEMORY_LOCAL_MCP_URL` to its loopback MCP URL, such as `http://127.0.0.1:8124/mcp`. The remote browser signs in once and receives a secure cookie. The terminal connects to the local MCP endpoint, and the remote activity view polls through the proxy.

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
