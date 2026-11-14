# Backend setup and frontend handoff

Precedent runs two local Python services against the event MongoDB Atlas Sandbox. The platform owns the authoritative results, vector retrieval, and execution. The presenter gives the browser a same-origin HTTP API and live events; tokens and database credentials stay server-side.

## Run it

Use Python 3.11. On this workstation the repository already has an ignored `.env` with a scoped Atlas account and four server-side demo identities.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-local.txt
# New checkout only: create .env and fill in the Sandbox connection string.
.\.venv\Scripts\python.exe -m demo.setup
.\.venv\Scripts\python.exe -m platform_api.preflight
```

Start the two services from the repo in separate terminals:

```powershell
.\.venv\Scripts\python.exe -m uvicorn platform_api.app:app --host 127.0.0.1 --port 8000
.\.venv\Scripts\python.exe -m uvicorn demo.presenter:app --host 127.0.0.1 --port 8100
```

Put the teammate's static build in `demo/web/` or set `MEMORY_WEB_DIR` to the absolute path of their build output. Open `http://127.0.0.1:8100/`. For frontend development with a separate dev server, use its reverse proxy for `/demo`; preserve the presenter's expected Host and Origin or test the static build on port 8100. Do not put bearer tokens in frontend environment variables. The clickable mockup in `docs/demo/` remains untouched.

For teammates using their own Sandbox account: allow their development IP in Atlas, grant a database user read/write access on the selected database, and run preflight to create and validate collections and the vector index. Never commit the connection string. Start the presenter after the platform is up.

## Browser contract

The [presenter routes](PLATFORM.md#presenter-service) define request fields. Running services expose `/docs` and `/openapi.json` on their own ports. The browser uses relative URLs:

- `GET /demo/state` returns findings, the latest decision, the most recent evidence cards, all recent receipts, and the active stream modes. The latest stage and evidence-card snapshot live for the presenter process; findings, decisions and receipts are durable.
- `new EventSource('/demo/events')` delivers named `atlas` and `change` events. Use `change` to refresh state for the current view. Atlas events contain `command`, `collection`, `ms`, `docs`, `scope`, `ok` and a redacted `shape`; these are from PyMongo monitoring. In particular, `scope: "isolation-check"` labels commands executed with the second project identity. Results and decisions use scoped change streams. Reconnects replay recent events when available.
- `POST /demo/agent-a`, then `POST /demo/agent-b` with `{"memory":"off"}` for a baseline. Call Approve, then Execute, separately. Next run Agent B with `{"memory":"on"}`. Reject prevents execution. The presenter waits for expected versions to appear in the index after publication or correction.
- Use the IDs in `agent-a.refs.promising` and `agent-a.refs.negative` for Correct and Expire respectively. Send `result_id`, `expected_version`, and a reason. After each call, `POST /demo/rerun` repeats the last memory setting on the same task. Approve and execute each new decision. History and evidence are available under `/demo/results/{result_id}/history` and `/demo/results/{result_id}/evidence?version=1`.
- `POST /demo/isolation-check` checks that the unseeded second project returns no candidates and direct result/evidence reads return 404. Preflight also verifies selectivity with a distinct, authorized sentinel in each project.

An expired finding remains listed for inspection during its retention window. The measured 686 → 238 byte comparison excludes the fixed dictionary distribution cost: the sender and receiver already share the dictionary.

## Verification

```text
python -m unittest discover -s tests
python -m platform_api.preflight
python -m demo.rehearse --out receipts/rehearsal
python -m demo.check_presenter
```

Preflight and rehearsals create fresh project IDs and write local receipts under the ignored `receipts/` folder. To clear the configured demo project, stop the presenter and run `python -m demo.reset --project <configured demo project>`, then restart. The reset refuses any project other than the configured `demo-*` namespace. No database or index is dropped.

The tested configuration uses BGE embeddings on CPU and a stateless evidence-first rules planner. BGE's 384 floats are padded with zeros for the 1536-dimensional local index, which preserves cosine ordering. The first run downloads the model. MongoDB Atlas runs vector retrieval and the authoritative checks in the same pipeline in either mode.

For the planned OpenAI path, install `requirements.txt`, set `OPENAI_API_KEY` locally, and set `MEMORY_EMBEDDER=openai` and `MEMORY_PLANNER=openai`. The two settings can be switched independently. Use a fresh project when changing embedding provider and rerun preflight and rehearsal; citations are checked against the same authoritative conditions in both modes. The OpenAI mode needs a team key for a live check.
