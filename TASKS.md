# Team task board

Claim a role by adding your name. P4 is integration lead and submitter, and owns this board. Each owner edits only their own paths, on a branch. P1 owns changes to the [platform contract](PLATFORM.md) and coordinates them with affected owners. What we're building and why is in [REQUIREMENTS.md](REQUIREMENTS.md). The demo task is ResNet-18 on CIFAR-10 on the team's GPU PC.

## Where we are

| Piece | State | Evidence |
| --- | --- | --- |
| Atlas platform (`platform_api/`) | **Built, not verified live.** Single `$vectorSearch` + `$lookup` aggregation, versions, expiry, decisions with atomic approve and one dispatch, command listener. | Code on `main`. Offline: `python -m unittest discover -s tests`. Live Atlas checks below are pending. |
| Presenter (`demo/presenter.py`) | **Built for a scripted agent path**, with change streams and `/demo/events`. No embedded terminal yet. | Code on `main`. Live check pending. |
| ResNet benchmark and experiment profile | **Not started.** The old compression benchmark and the digit demo were removed. | — |
| MCP server for Claude Code, weights routes (GridFS) | **Not started.** | — |
| Web UI (`demo/web/`) | **Mockup only.** | [docs/demo/index.html](docs/demo/index.html), single-screen, illustrative numbers. |
| Pitch deck | Updated to the ResNet-18 task and four stages. | [docs/deck/precedent-deck.pptx](docs/deck/precedent-deck.pptx) |

## Workstreams

| ID | Workstream | Owner | Status | First task and pass condition |
| --- | --- | --- | --- | --- |
| P1 | Platform and Atlas | Open | Verify, then extend | Run `python -m platform_api.preflight` against the event Sandbox. Pass when the vector index is queryable, one 1536-float embedding round trips, and each project retrieves only its own sentinel. Then add the GridFS weights routes (`GET`/`POST /v1/results/{id}/weights`) with the same lifecycle rules as evidence. |
| P2 | Presenter and terminal | Open | Extend | Add the embedded terminal: xterm.js over a localhost WebSocket to a PTY in the demo working directory, as in [PLATFORM.md](PLATFORM.md#claude-code-integration). Pass when `claude` starts inside the page, `/demo/events` still streams, and no token reaches the browser. Keep the scripted path as the fallback. |
| P3 | Benchmark and Claude Code | Open | Not started | Build `benchmark/` on the GPU PC per [PLATFORM.md](PLATFORM.md#benchmark): `benchmark.run`, `benchmark.publish`, `benchmark.execute`, the `benchmark.profile` experiment module and the calibration. Then `platform_api/mcp.py` with the six tools and the demo folder's `.mcp.json`. Pass when the calibration gate holds (baseline well under 90%, `finetune-lr0.01` over 90% in under two minutes, `scratch-lr0.4` diverges, batch 4096 crashes) and `claude` in the demo folder lists the six tools. |
| P4 | UI, integration and demo | Open | Mockup done | Turn [docs/demo/index.html](docs/demo/index.html) into `demo/web/` wired to `/demo/state` and `/demo/events`. Keep it one screen. Pass when the four stages run from real events, the Atlas strip shows only real commands, and "Not now" leaves no run. Then own clean-checkout rehearsal, the baseline recording, the one-minute video and submission. |

## Verification gates

| Owner | Check | Pass condition | Status |
| --- | --- | --- | --- |
| P1 | `python -m unittest discover -s tests` | Passes offline. | Not run by the reviewer. |
| P1 | `python -m platform_api.preflight` on event Atlas | Ping, index queryable, embedding round trip. | **Pending, needs Sandbox access.** |
| P1 | `python -m demo.check_platform` | Isolation (two projects find only their own sentinel, cross-project reads return 404), search returns labelled hits, a crash is never returned, stale vector hits are dropped. | **Pending.** |
| P1 | MongoDB does the work | The command log shows exactly one `aggregate` on `result_vectors` per search with `$vectorSearch` filtered by project and a `$lookup`. | **Pending.** |
| P2 | `python -m demo.check_presenter` | Approve and reject work once (409 after). Tokens never reach the browser. `change` and `atlas` events arrive within a second. | **Pending.** |
| P3 | Calibration | See the P3 row. Numbers recorded with GPU name and library versions. Replace the mockup numbers. | **Pending.** |
| P3 | Claude Code through MCP | `claude` lists six tools in the demo folder and none outside it. A search highlights the right experiments within a second. Declining leaves no run. Accepting runs once. `load_weights` refuses an expired or superseded result. | **Pending.** |
| P3 + P4 | Full run | Same request and budget: baseline picks `scratch-lr0.1` (about 71%). With Precedent it cites the positive and the failed run, sets aside Fashion-MNIST, runs `finetune-lr0.01` (about 93%). Repeat three times. | **Pending.** |
| P4 | Clean checkout | `python -m pip install -r requirements.txt` works, the demo runs from a fresh clone with local env values, the public repo opens signed out. | **Pending.** |

Mark each gate with the commit, the exact command and the observed result as soon as it passes. Anything checked only against a stub or a fixture must say so.

## Handoff between producers and callers

- The benchmark writes a single-run JSON receipt: `run_id`, `fixture_revision`, `conditions`, `configuration`, `metric`, `execution`, `validity`, `direction`, `train_seconds`, `gpu`, `weights_sha256` and `reproduce` (`command`, `seed`, library versions). Conditions, configuration and metric match the publish body.
- `python -m benchmark.publish` publishes the seeded experiments and uploads weights, then exits. Its output names the refs `positive`, `negative`, `mismatch` and `crash`.
- The baseline is recorded once before the demo: Claude Code run in an empty folder with no `.mcp.json`, same prompt, receipt saved to `receipts/baseline.json`. It never touches the platform.

## Time plan to the 5:00 p.m. submission

Adjust to the actual clock. Protect the submission.

| By | Goal |
| --- | --- |
| Now | P1 runs preflight on event Atlas. P3 starts the GPU calibration. P4 starts `demo/web/` from the mockup. |
| 3:15 | Calibration done, seeded experiments published, real Atlas search returns labelled hits. |
| 3:45 | MCP tools and the embedded terminal work. One full run: ask, propose, confirm, train, result saved. |
| 4:15 | Freeze. Three clean rehearsals. If the UI or the terminal isn't ready, present the working parts and the scripted path, and say which is which. |
| 4:15–4:30 | Record the one-minute video. Check it opens signed out. |
| 4:30 | Submit with the public repo, the video and all team members. Leave 30 minutes for recovery. |

Fallbacks, in order: if Claude Code is unstable, use the scripted planner with the same evidence rules and label it. If the PTY fails, run Claude Code in a normal terminal beside the browser. If Atlas is unavailable late, show verified receipts from an earlier real run and say so. Do not add Phase 2 governance to the live demo until all gates above pass.

## Demo sequence

- **One-minute recording.** Keep the Atlas strip in frame. 0–10s past experiments, including the crash and the stored weights. 10–25s ask Claude Code, with its picks lighting up (using, avoiding, doesn't fit). 25–35s the plan and "Run it". 35–50s training, then the result next to Claude Code on its own. 50–60s the new experiment in the list and the public repo.
- **Three-minute live demo.** Four stages, one "In MongoDB" sentence each. 0–25s past experiments. 25–80s ask Claude Code and point at the highlights, including the one that doesn't fit. 80–110s the plan and "Run it" (show "Not now" first if time allows). 110–160s training and the result against the baseline, and the new experiment. 160–180s isolation: another project gets nothing back. Keep the end for questions. Governance (correct and expire) is a talking point, not part of the run, until Phase 2 lands.

## Handoffs

Add a short entry with task ID, status, branch or commit, exact check and observed result, and any dependency or next owner. Keep private logs local and link only evidence suitable for the public repo.
