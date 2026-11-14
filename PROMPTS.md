# Prompts for parallel agents

Paste one prompt into a fresh coding-agent session opened at the repository root, one per teammate or agent. Each work item owns different paths, so they can run at the same time. Status and context are in [TASKS.md](TASKS.md). Submission is due at 5:00 p.m. Toronto time, so each prompt asks for the smallest change that passes its check.

## Shared preamble (already included in every prompt below)

> Read AGENTS.md, REQUIREMENTS.md, PLATFORM.md, BACKEND.md and TASKS.md first. Work on your own branch from `main` and edit only the paths your item owns. Never commit credentials, tokens or `.env`. Never push to `main`. Run the checks, then add a short handoff entry under Handoffs in TASKS.md with the exact command and what you observed. Say plainly what you did not verify. Commit and push your branch and open a PR.

## Context every agent needs

- **Demo:** train a ResNet-50 to at least 80% on a handwritten-digit holdout in one four-epoch run. Codex, in a terminal embedded in the web app, searches shared memory on MongoDB Atlas over MCP, proposes a plan, the person presses **Run plan**, and the job trains from a stored checkpoint. Measured once: scratch 29.2%, guided `reuse` 90.4%.
- **Built:** `platform_api/` (Atlas, search, decisions, GridFS), `experiments/resnet.py` (jobs `scratch`, `reuse`, `high-lr`; `seed`; `train`), `workbench/` (app, terminal, `/mcp`, web UI).
- **Rules:** MongoDB does isolation, version, expiry and fit labels in one aggregate. Never fake Atlas activity in the UI. Keep tokens out of the browser. A crash is never a failed idea. No ARA or AutoSci code. The hackathon bans dashboards as the main feature and basic RAG.

---

## W1. Seed completeness, calibration, stability and GPU

```text
Read AGENTS.md, REQUIREMENTS.md, PLATFORM.md, BACKEND.md and TASKS.md. I own W1 in TASKS.md. Work on a new branch from main and edit only experiments/, local receipts/ and the install notes in BACKEND.md. Never commit credentials or .env, and never push to main.

Goal: make the seeded memory complete and the demo numbers trustworthy.
1. experiments/resnet.py `seed` publishes three calibration experiments (reuse at 64 px with a checkpoint, high-lr at 64 px, reuse at 32 px). R1 also needs a CRASHED run that is stored but never returned by search. Add one to `seed`: execution "crashed", validity "invalid", direction "undetermined", metric value null (see the Publish model in platform_api/models.py and PLATFORM.md Results), conditions equal to the task conditions, a short error note in the evidence. Verify through the real API that GET /v1/results lists it and POST /v1/search never returns it.
2. This machine has a GPU. BACKEND.md installs the CPU build of PyTorch. Install the CUDA build, confirm torch.cuda.is_available(), and update the install notes. Note the device in the receipt (already recorded as configuration.device).
3. Stability: run the scratch baseline and the guided `reuse` run on the HOLDOUT three times each. Record accuracy and elapsed_seconds. Pass when scratch stays below 80% and reuse stays at or above 80% every time, and one training run fits comfortably inside a live demo (report the seconds; if over ~60 s, propose the smallest change such as fewer epochs or a smaller split, and keep the calibration and holdout windows disjoint).
4. Confirm the high-lr calibration result really is a valid negative (below 80%) and the 32 px reuse result is positive on its own task.
Do not change the platform API. Report the numbers table, the exact commands, and anything you could not verify. Add the handoff to TASKS.md and open a PR.
```

## W2. Single-screen UI

```text
Read AGENTS.md, REQUIREMENTS.md, PLATFORM.md, BACKEND.md and TASKS.md, then open docs/demo/index.html in a browser. I own W2 in TASKS.md. Work on a new branch from main and edit only workbench/web/ (and, only if unavoidable, a small additive change in workbench/app.py). Never commit credentials, and never push to main.

Goal: move the real workbench UI (workbench/web/) toward the single-screen design in docs/demo/index.html, driven by REAL events, because the hackathon bans projects whose main feature is a dashboard.
- One main screen: a top bar with four stages (Past experiments, Ask the agent, You decide, Result), the embedded terminal in the centre, the experiments list beside it, and a result card after the run. Details open in a drawer on click. Keep the Atlas activity strip at the bottom. Demote Research library and Run comparison to secondary (a link or the drawer), not the primary navigation.
- In the experiments list, mark each experiment using, avoiding, doesn't fit (name the mismatched field, e.g. image_px 32 ≠ 64) or never offered (crashed), from the real plan and search data the app already receives over /api/state and /api/events.
- One "In MongoDB" sentence per stage, built from the real events (the $vectorSearch aggregate with its project filter and $lookup, the conditional approval update, the GridFS stream, the new insert). Never hardcode Atlas lines.
- Result card: the agent on its own (the baseline receipt) against the guided run, with the 80% target marked. Run plan and Reject must work. Reject must leave no run. Keep tokens out of the browser.
- Keep keyboard focus visible, and keep the layout usable at narrow widths.
Verify against the live app with the platform and workbench running (BACKEND.md#live-workspace) and, if Atlas is unavailable, say which parts you checked only against recorded data. Add the handoff and open a PR.
```

## W3. Rehearsal, fallback, video and submission

```text
Read AGENTS.md, REQUIREMENTS.md, PLATFORM.md, BACKEND.md and TASKS.md. I own W3 in TASKS.md. Work on a new branch from main and edit only a new rehearsal/ folder and a new SUBMISSION.md. Never commit credentials, and never push to main.

Goal: make the demo repeatable and the submission safe.
1. rehearsal/: a short written runbook plus any helper script that (a) resets and seeds a fresh project, (b) records the scratch baseline receipt, (c) checks the workbench and platform are healthy, and (d) lists the exact steps for one full run. Add a checklist for three consecutive full runs with a place to record the time for each and whether the agent proposed `reuse`. Target: a complete run in under three minutes.
2. Fallbacks, written down and testable: what to do if the agent proposes the wrong job, if the embedded terminal fails (run the agent in a normal terminal beside the browser), if Atlas is slow or down (show a recorded earlier run and say so). Label any scripted planner clearly.
3. SUBMISSION.md: the one-minute video script from TASKS.md (Demo script), the three-minute live script with one "In MongoDB" sentence per stage, and a pre-submission checklist: repository is public, no secrets in history (run a secrets scan and report), the build uses the event Atlas Sandbox, the video opens signed out, every team member is listed, and the README clearly separates what was built during the event from upstream credit (NOTICE.md).
Do not edit platform_api/, experiments/ or workbench/. Report what you ran and what you could not. Add the handoff and open a PR.
```

## W4. Pitch alignment (mockup and deck)

```text
Read AGENTS.md, REQUIREMENTS.md, PLATFORM.md and TASKS.md. I own W4 in TASKS.md. Work on a new branch from main and edit only docs/demo/index.html and docs/deck/precedent-deck.pptx. Never commit credentials, and never push to main.

Goal: make the mockup and the deck match the real build. They currently show ResNet-18 on CIFAR-10 and "Claude Code", but the build is ResNet-50 on scikit-learn handwritten digits with Codex as the agent.
- Task: train a ResNet-50 to at least 80% on a digit holdout in one four-epoch run. Jobs: scratch, reuse, high-lr. Seeded experiments: reuse at 64 px (positive, with checkpoint), high-lr at 64 px (valid negative), reuse at 32 px (looks good, does not fit: image_px differs), one crashed run (never offered).
- Numbers: use the measured 29.2% (agent on its own) and 90.4% (with Precedent) and label them "measured once"; update them if TASKS.md has newer W1 numbers.
- Mockup: keep the single-screen design and four stages. Change the task, data, agent name (Codex), button labels (Run plan, Reject) and numbers. Keep it clearly labelled as a mockup.
- Deck (a .pptx; edit the slide XML or python-pptx and render with LibreOffice to check): update slides 5-8 and 10 and the speaker notes. The ImageNet and ResNet-paper story stays as the pitch, labelled illustrative. Keep slide 2's cited statistics unchanged. Keep slide 10's governance cards labelled "(next)".
Check by opening the mockup and clicking through all four stages, and by rendering the deck to images and viewing every changed slide for overflow. Report what you checked. Add the handoff and open a PR.
```

## W5. Verify and harden

```text
Read AGENTS.md, REQUIREMENTS.md, PLATFORM.md, BACKEND.md and TASKS.md. I own W5 in TASKS.md. Work on a new branch from main. Edit tests/, .github/ and, only for confirmed bugs, small fixes in platform_api/ (explain each). Never commit credentials, and never push to main.

Goal: prove the claims the demo makes, and find what breaks them.
1. Run python -m unittest discover -s tests, python -m platform_api.preflight, python -m tests.check_standalone and python -m tests.check_lookup_profile against the event Atlas Sandbox (credentials from the local .env, never printed). Record commands and results.
2. Write checks (offline where possible, live where needed) for: cross-project access fails on search, result read, evidence, artifact download (/v1/results/{id}/artifact), history and decisions; an expired or superseded version is not returned by search or accepted by resolve even if its vector entry is still present; a crashed result is never returned by search; a decision can be approved and dispatched only once, even under two concurrent requests; a plan citing a mismatched, crashed or non-current result is refused (422); load of a checkpoint with a wrong SHA-256 is refused.
3. Review workbench/app.py and workbench/terminal.py for token or credential leakage to the browser or the terminal environment, unauthenticated routes, the /mcp loopback-only rule, and the remote-password path.
4. Secrets: scan the repo and its git history for keys, Atlas URIs and tokens. Check .gitignore covers .env and receipts.
5. Confirm requirements.txt, requirements-workbench.txt and requirements-resnet.txt install on a clean machine, and the CI workflow in .github/workflows/backend.yml passes.
Report findings ranked by severity with the exact reproduction, what you fixed and what you left. Add the handoff and open a PR.
```

## W6. Governance in the UI (Phase 2, start only after W1–W5 pass)

```text
Read AGENTS.md, REQUIREMENTS.md, PLATFORM.md, BACKEND.md and TASKS.md. I own W6 in TASKS.md. Start only after W2 is merged and W1, W3 and W5 pass. Work on a new branch from main and edit only workbench/. Never commit credentials, and never push to main.

Goal: add correction, expiry and history to the single-screen UI, using the existing routes (POST /v1/results/{id}/correct, /expire, GET /history, and the maintainer role). In an experiment's drawer: Correct and Expire with a required reason, previous and current versions, and the change history. After each action, ask the agent the same question again and show how its evidence and plan changed. An expired or superseded experiment must stop appearing as evidence immediately, even before cleanup. Run the real Atlas-backed flow, record the result, add the handoff and open a PR.
```

---

## How to run them

- **Start W1, W2, W4 and W5 now.** They touch different paths. W3 can start immediately on the runbook and finish after W1 and W2.
- **Order for merging:** W1, W5, W2, W4, W3. If two PRs touch TASKS.md, keep both handoff entries.
- **Do not start W6** until the others pass.
