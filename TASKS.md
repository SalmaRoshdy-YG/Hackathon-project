# Team task board

What we're building and why is in [REQUIREMENTS.md](REQUIREMENTS.md). The contract is [PLATFORM.md](PLATFORM.md). Parallel-agent prompts for the open work are in [PROMPTS.md](PROMPTS.md). Submission is due **5:00 p.m. Toronto time**.

## Where we are

| Piece | State | Evidence |
| --- | --- | --- |
| Atlas platform (`platform_api/`) | **Built and reported verified live** by a teammate: preflight, unit tests, isolation, GridFS artifacts. | Handoff below. Not re-run by the reviewer. |
| ResNet-50 digits experiment (`experiments/resnet.py`) | **Built.** `seed` publishes three calibration experiments, `train` runs a job, the profile plugs into the platform. | Scratch 29.2% against `reuse` 90.4% on the holdout, once. |
| Workbench (`workbench/`) | **Built.** Embedded Codex terminal, `/mcp` endpoint, research library, run comparison, Atlas activity, Run plan and Reject. | Handoff below, including an HTTPS preview. |
| Crashed-run seed | **Missing.** R1 needs a stored crash that is never offered. | — |
| Single-screen UI from the mockup | **Not done.** The workbench has a sidebar with three views and stacked panels. | [docs/demo/index.html](docs/demo/index.html) is the target. |
| Stability, timing and GPU check | **Not done.** One run each so far, and the install notes use the CPU build of PyTorch. | — |
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
| Crash never offered | The seeded crash is stored and absent from search. | **Open (W1).** |
| Stability | Three repeats of the baseline and the guided run land on the same sides of 80%, and the agent proposes `reuse` each time. | **Open (W1, W3).** |
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

### Live workspace handoff (from the teammate who built it)

- Started from `main` at `fd3a73b`. The [live workspace startup and training steps](BACKEND.md#live-workspace) run the Codex terminal, Atlas-backed research library, and run comparison.
- Ran `python -m experiments.resnet seed` and `python -m experiments.resnet train scratch holdout receipts/resnet-baseline.safetensors`. The scratch run measured 29.2% on the holdout. Codex searched Atlas through MCP and produced a plan citing a compatible calibration result. After browser confirmation the ResNet job measured 90.4% on the same holdout, published a finding, and saved the weights to GridFS. Verified the output byte count and SHA-256 through the download route and a 404 for the second project.
- Passed `python -m platform_api.preflight`, `python -m unittest discover -s tests`, `python -m tests.check_standalone`, and `python -m tests.check_lookup_profile`. The lookup test used its own job catalog and fixture, with 122 comparisons for the baseline and 7 with memory.
- Verified the HTTPS preview from a browser, including sign-in, blocked anonymous API reads, blocked external MCP, the run comparison and the Codex terminal over WebSocket.
