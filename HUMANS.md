# Human review guide

Start with one question. **Did a fresh agent use another agent’s measured result to choose and execute a different experiment?** Follow the decision back to the exact version of the result and its evidence. Check that the conditions match and that the platform enforces who can still read and use it.

## Where to read

| File | What to look for |
| --- | --- |
| [README.md](README.md) | The project in one paragraph, the two demos, and how to join the build. |
| [REQUIREMENTS.md](REQUIREMENTS.md) | Business requirements BR1–BR9 in plain words, the showcase use case, and the decision to build our own platform. |
| [BRIEF.md](BRIEF.md) | The judging requirements, the event deadline, and the pinned ARA and AutoSci sources. |
| [PLATFORM.md](PLATFORM.md) | The benchmark, API and permissions, open experiments, showcase seed, expected job receipts, research hub design and upstream credits. |
| [TASKS.md](TASKS.md) | Owners, acceptance checks, schedule, and the latest commands and observed results. |
| [HARNESS.md](HARNESS.md) | The order of integration and the evidence to show in the demo. Use the task board for current milestones. |
| [AGENTS.md](AGENTS.md) | The instructions teammates and their coding assistants follow when implementing and verifying work. |
| [GOAL-PROMPT.md](GOAL-PROMPT.md) | The original kickoff planning assignment. |

## What you can verify today

At kickoff, this checkout contains planning documents. The team inspected the pinned upstream artifact shapes and ran a local Python 3.11 compression probe. The probe measured 686 bytes with plain DEFLATE and 238 bytes with the matched dictionary on the same 928-byte holdout. The metric assumes sender and receiver already share the dictionary. Check the fixture recipe, thresholds, and the expected results for the other jobs. [Benchmark and planning measurements](PLATFORM.md#first-benchmark-and-agent-decision)

The event Atlas round trip, agent execution, lifecycle checks, showcase seed and research hub are build gates. Look for a handoff with a commit, an exact command, and an observed result before treating a gate as passed. A fixture or stub result can verify wiring. The live Atlas gate requires an event Sandbox run. [Verification gates](TASKS.md#verification-gates) · [Handoffs](TASKS.md#handoffs)

## How to review a build

From the repository root, use a clean checkout and Python 3.11. Ask P1 for the local Sandbox and credential setup, and P4 for the command and commit from the latest rehearsal handoff. The planned entry points below become runnable as their owners land them. Keep credentials and private receipts local.

```sh
python -m pip install -r requirements.txt
python -m benchmark.run --job dict-a-l6 --cohort A --split holdout
python -m platform_api.preflight
python -m demo.rehearse --out receipts/rehearsal
```

The benchmark command only needs the local fixture. For the live checks, start the API using the service command and environment setup from the platform contract. Read the assertion summary and the producer and consumer receipts in `receipts/rehearsal/`. Compare executed configurations, measured byte counts, round-trip validity, and exact cited versions. [Service and API](PLATFORM.md#shared-entry-point) · [Receipt handoff](TASKS.md#handoff-between-producers-and-callers)

| Claim | What to inspect |
| --- | --- |
| A publishes useful evidence | Find the positive and valid negative calibration receipts. Each shows the fixture, cohort, job, measured ratio, threshold, and successful decode. |
| B finds relevant research | After A exits, use a fresh B session. Its paraphrased question should find the two applicable cohort A observations and the cohort B distractor through Atlas Vector Search. The receipt should explain the cohort mismatch. |
| Memory changes a real job | Compare off, on, corrected, and expired receipts. Request, candidate jobs, and one-job budget should match. Expect plain level 1 in off, corrected, and expired, and the cohort A dictionary at level 6 in on. Confirm the job ran and the on receipt cites the exact positive and negative versions. |
| Access and lifecycle work | Both projects should find their own sentinels. A second project’s direct result and evidence reads should return 404 for the first project’s ref. A superseded or expired version should fail direct read, evidence read, and execution resolution, even if its stale search hit is still present. |
| The showcase uses the shared API | Run the showcase seed into a fresh project. Read ResNet N08 back and check its conditions, evidence source and `reproducibility.missing`. Claim open experiment G1 twice at once and expect one 200 and one 409. Check `NOTICE.md` credits ARA as the data source. |
| Researchers can review the work | Open `/research` when available. In the hub, search with a paraphrase, tell a valid negative, a ruled-out explanation and a crash apart, and claim an open experiment. In Platform verification, inspect a cited version and its measured receipt and see why the wrong-cohort observation was dropped and when evidence becomes unavailable. |

## Record what you saw

Add the task ID, commit, exact command or browser steps, observed outcome, and any missing dependency to the task board. Link the redacted receipt or assertion summary if available. For a failed claim, include the smallest reproducible example, the expected behavior, and what actually happened. [Team handoffs](TASKS.md#handoffs)
