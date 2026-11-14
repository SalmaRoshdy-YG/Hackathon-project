# Team task board

What we're building and why is in [REQUIREMENTS.md](REQUIREMENTS.md). The contract is [PLATFORM.md](PLATFORM.md). Parallel-agent prompts for the open work are in [PROMPTS.md](PROMPTS.md). Submission is due **5:00 p.m. Toronto time**.

## Where we are

| Piece | State | Evidence |
| --- | --- | --- |
| Atlas platform (`platform_api/`) | **Built and reported verified live** by a teammate: preflight, unit tests, isolation, GridFS artifacts. | Handoff below. Not re-run by the reviewer. |
| ResNet-50 digits experiment (`experiments/resnet.py`) | **Built and verified on CUDA.** Three calibration measurements and one crash fixture seed through the API. | Three holdout runs each. Scratch scored 9.6–35.0% and checkpoint-guided `reuse` scored 88.75% each time. |
| Workbench (`workbench/`) | **Built.** Embedded Codex terminal, `/mcp` endpoint, research library, run comparison, Atlas activity, Run plan and Reject. | Handoff below, including an HTTPS preview. |
| Crashed-run seed | **Verified.** The crash is listed and excluded from search. | Live Atlas API checks in the W1 handoff below. |
| Single-screen UI from the mockup | **Not done.** The workbench has a sidebar with three views and stacked panels. | [docs/demo/index.html](docs/demo/index.html) is the target. |
| Stability, timing and GPU check | **Passed W1.** All three pairs met the 80% gate on the RTX 3060 Ti. | Guided dispatch took 15.5–24.9 s including Atlas I/O. |
| Mockup and deck numbers | **Out of date.** They show ResNet-18 on CIFAR-10 and "Claude Code". The build is ResNet-50 on digits with Codex. | — |
| Rehearsal, fallback, video, submission | **Not done.** | — |
| Governance in the UI (correct, expire, history) | **Backend built, no UI.** Phase 2. | — |

## Open work

Each item has a ready-to-paste prompt in [PROMPTS.md](PROMPTS.md). Paths are owned by one item at a time so agents can work in parallel without edit conflicts.

| ID | Work | Owns | Depends on | Pass condition |
| --- | --- | --- | --- | --- |
| W1 | Seed completeness, calibration, stability and GPU | `experiments/`, `receipts/` (local), BACKEND install notes | — | A crashed run is seeded and never returned by search. Three consecutive scratch and `reuse` runs on the demo machine give stable results on the right side of 80%. Training time is recorded. PyTorch uses the GPU. |
| W2 | Single-screen UI | `workbench/web/` | — | The four stages run from real events on one screen, highlights show used, avoided and doesn't fit, the result card shows both runs, and "Reject" leaves no run. |
| W3 | Rehearsal, fallback, video, submission | `rehearsal/`, `SUBMISSION.md` | W1 numbers, W2 for the video | Three clean full runs under three minutes, a labelled fallback, a one-minute video script and a checked submission list. |
| W4 | Pitch alignment | `docs/demo/`, `docs/deck/` | W1 numbers (start now with 29.2% and 90.4%) | Mockup and deck show ResNet-50 on digits, Codex, the real job names and measured numbers. |
| W5 | Verify and harden | `tests/`, `.github/`, `platform_api/` fixes only | — | All checks pass and are recorded. Secrets scan is clean. Cross-project reads of results, artifacts and decisions fail. Approval runs once. |
| W6 | Governance in the UI (Phase 2) | `workbench/` correct and expire controls | W2 | Only after W1–W5 pass. Correct and expire an experiment from the UI and ask again. |

## Verification gates

| Check | Pass condition | Status |
| --- | --- | --- |
| `python -m unittest discover -s tests` | Passes offline. | Passed offline on the reviewer's machine (2 tests). The teammate reports it passing in their environment. |
| `python -m platform_api.preflight` on event Atlas | Ping, queryable index, embedding round trip. | Reported passed by the teammate. |
| Live run | Scratch baseline, then agent search, plan, Run plan, `reuse` run, new finding and checkpoint stored. | Reported passed once (29.2% then 90.4%). |
| Isolation | Second project's search returns nothing, and result, evidence, artifact and decision reads return 404. | Reported for the artifact route. W5 verifies all paths. |
| Crash never offered | The seeded crash is stored and absent from search. | **Passed (W1).** The crash was listed with evidence and absent from both live searches after all three calibration controls were visible. |
| Stability | Three repeats of the baseline and the guided run land on the same sides of 80%, and the agent proposes `reuse` each time. | **W1 passed** with scripted plans on the live API. W3 owns the three interactive Codex rehearsals. |
| Single-screen UI | See W2. | **Open.** |
| Clean checkout | A fresh clone runs the demo from the documented steps, and the public repo opens signed out. | **Open (W3, W5).** |

Mark each gate with the commit, exact command and observed result when it passes. A check against a stub or fixture must say so.

## Time plan to the 5:00 p.m. submission

| By | Goal |
| --- | --- |
| Now | W1, W2, W4 and W5 start in parallel. |
| 3:45 | W1 done with real numbers. W2 shows the four stages from real events. W4 has the new mockup and deck text. |
| 4:15 | Freeze. W3 runs three clean rehearsals. If the UI isn't ready, present the working workbench and say so. |
| 4:15–4:30 | Record the one-minute video. Check it opens signed out. |
| 4:30 | Submit with the public repo, the video and all team members. Leave 30 minutes for recovery. |

Fallbacks, in order: if the agent is unstable, use a scripted planner with the same evidence rules and label it. If the embedded terminal fails, run the agent in a normal terminal beside the browser. If Atlas is unavailable late, show verified receipts from an earlier real run and say so. Do not add Phase 2 governance to the live demo until the gates pass.

## Demo script

- **One-minute video.** Keep the Atlas strip in frame. 0–10s past experiments, including the crash and the stored checkpoint. 10–25s the agent searches and its picks light up (using, avoiding, doesn't fit). 25–35s the plan and "Run plan". 35–50s training, then the result next to the agent on its own. 50–60s the new experiment in the list and the public repo.
- **Three-minute live demo.** Four stages, one "In MongoDB" sentence each. 0–25s past experiments. 25–80s the agent searches, point at the highlights including the one that doesn't fit. 80–110s the plan, Reject once to show nothing runs, then Run plan. 110–160s training and the result against the baseline, and the new experiment. 160–180s isolation: another project gets nothing back. Governance (correct, expire) is a talking point until Phase 2 lands.

## Handoffs

Add a short entry with work ID, status, branch or commit, exact check and observed result, and any dependency or next owner. Keep private logs local and link only evidence suitable for the public repo.

### W1 · ResNet seed and CUDA verification

Branch `w1/resnet-calibration`. The CUDA check returned `True` on the NVIDIA GeForce RTX 3060 Ti. Receipts used PyTorch `2.15.0+cu132`, TorchVision `0.29.2+cu132`, and `configuration.device=cuda`.

| Holdout repeat | Scratch accuracy | Scratch elapsed_seconds | Guided `reuse` accuracy | `reuse` elapsed_seconds | `reuse` execute API wall time |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 20.42% | 2.238 | 88.75% | 0.858 | 24.891 s |
| 2 | 9.58% | 2.208 | 88.75% | 0.829 | 16.277 s |
| 3 | 35.00% | 2.170 | 88.75% | 0.775 | 15.526 s |

| Calibration | Accuracy | elapsed_seconds | Observed outcome |
| --- | ---: | ---: | --- |
| `reuse`, 64 px | 85.83% | 0.882 | Valid positive with a GridFS checkpoint |
| `high-lr`, 64 px | 66.67% | 0.719 | Valid negative |
| `reuse`, 32 px | 87.50% | 0.582 | Valid positive with a GridFS checkpoint, labelled `image_px` mismatch for the 64 px task |
| Crash fixture, 64 px | null | — | Crashed, invalid, undetermined |

- Ran `python -m platform_api.preflight --out receipts/w1/preflight.json` against the configured Atlas Sandbox. Ping, `research_memory_local_v1`, and the 1536-dimensional BGE embedding query passed. `python -m unittest discover -s tests` passed both tests and `python -m pip check` found no broken dependencies.
- Ran `python -m experiments.resnet seed` in a fresh Atlas project. `GET /v1/results` listed all four records and the crash evidence route returned the error note. `POST /v1/search` with the demo task and again with the crash's exact hypothesis returned all three completed controls and excluded the crash ID.
- Ran `python -m experiments.resnet train scratch holdout receipts/w1/scratch.safetensors` three times. For each guided repeat, the local verifier posted a plan to `POST /v1/decisions`, approved it through `POST /v1/decisions/{id}/approve`, and dispatched through `POST /v1/decisions/{id}/execute`. Each receipt cited the same 64 px calibration version and checkpoint SHA-256. All six runs used the 240-example holdout, disjoint from the 240-example calibration evaluation window. All three scratch runs stayed below 80% and all three guided runs passed. The four-epoch budget fit the demo timing target.
- Reproduce the combined check from the W1 worktree with the configured `.env` and CUDA environment using `python -u -c "import runpy; runpy.run_path('receipts/w1/verify.py', run_name='__main__')"`. The verifier and raw receipts are local. The first seed attempt hit a GridFS 503 with the Sandbox near its storage limit. The repeat passed after clearing the partial W1 seed. To make room for repeated output uploads, the verifier archived and SHA-256-checked its own 32 px and guided output checkpoints locally, then removed their GridFS copies. The active demo project was left untouched. W3 still needs to verify the interactive Codex proposal and browser flow three times and ensure there is room for new checkpoints before rehearsal.

### Live workspace handoff (from the teammate who built it)

- Started from `main` at `fd3a73b`. The [live workspace startup and training steps](BACKEND.md#live-workspace) run the Codex terminal, Atlas-backed research library, and run comparison.
- Ran `python -m experiments.resnet seed` and `python -m experiments.resnet train scratch holdout receipts/resnet-baseline.safetensors`. The scratch run measured 29.2% on the holdout. Codex searched Atlas through MCP and produced a plan citing a compatible calibration result. After browser confirmation the ResNet job measured 90.4% on the same holdout, published a finding, and saved the weights to GridFS. Verified the output byte count and SHA-256 through the download route and a 404 for the second project.
- Passed `python -m platform_api.preflight`, `python -m unittest discover -s tests`, `python -m tests.check_standalone`, and `python -m tests.check_lookup_profile`. The lookup test used its own job catalog and fixture, with 122 comparisons for the baseline and 7 with memory.
- Verified the HTTPS preview from a browser, including sign-in, blocked anonymous API reads, blocked external MCP, the run comparison and the Codex terminal over WebSocket.

### W5 ? Verification and hardening

Branch `w5/verify-harden`, based on `main` at `968b924`. Added live Atlas regression checks and offline checkpoint and workbench access checks. No production behavior changed.

- `python -m platform_api.preflight --out receipts/w5/preflight.json` passed on the configured event Atlas Sandbox with `research_memory_local_v1` and 1536-dimensional BGE embeddings. `python -m tests.check_standalone` passed with only the platform package on the service path. `python -m tests.check_lookup_profile` passed, measuring 122 comparisons baseline, 7 with memory, and 122 after correction and expiry. These commands initially ran at `925b68f`. The fast-forward to `968b924` changed only documentation.
- `python -m tests.check_governance` passed on Atlas using fresh project IDs and a lightweight lookup profile. Two projects found only their own records and cross-project result, evidence, artifact, history, decision and resolve reads failed. A raw Atlas query still returned expired, superseded and synthetic crash vectors while the public query excluded them. Resolve rejected those references, forged citations returned 422, and an approval whose evidence was superseded aborted before dispatch. Concurrent requests produced 200/409 for approval and 201/409 for execution. Reject left no receipt.
- `python -m unittest discover -s tests` passed three offline tests, including a wrong checkpoint SHA-256 reaching the real ResNet runner's guard before training. `python -m unittest tests.check_workbench_access` passed three offline checks covering anonymous remote requests, password login and cookie flags, remote MCP denial, cross-origin requests and WebSocket authorization. These checks exercise the app in process. They do not certify any live tunnel.
- A redacted pattern and exact-local-value scan covered 59 tracked paths and 224 blobs reachable from local Git refs after fetching branches. Only example Atlas URI strings matched. `git check-ignore .env receipts/w5/scan.py` confirmed both local paths are ignored. No detected credentials were printed.
- A fresh Python 3.11 Windows environment installed `requirements.txt`, `requirements-workbench.txt`, and `requirements-resnet.txt` together and passed `python -m pip check`. The backend workflow also runs the workbench access checks.

Findings by priority:

1. **Submission blocker.** GitHub reported this repository as private. A repository admin must change visibility and the submitter should verify signed-out access.
2. **High for remote deployment.** In `workbench/terminal.py`, the local-trust branch in `access()` uses request hostname and a Cloudflare header. It does not verify the peer address. `workbench/app.py` uses that branch for the local MCP and workbench paths. This places the trust boundary at the documented loopback listener and HTTPS proxy configuration. Keep the recording on its documented loopback setup. Workbench changes belong to the workbench owner.
3. **Medium for remote deployment.** The Codex subprocess allowlist includes `OPENAI_API_KEY` when set. It omits the Atlas URI, project tokens and preview password. The verification environment did not set the provider key. The workbench owner should review this forwarding before offering remote terminal access with provider credentials configured.

The interactive browser-to-Codex recording and fresh CUDA training were outside these checks. W1 and W3 own those gates.
