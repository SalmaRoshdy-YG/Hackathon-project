# Human review guide

Start with one question. **Did a fresh agent use another agent’s measured result to recommend a different experiment, which a human approved and which then ran?** Follow the decision back to the exact version of the result and its evidence. Check that the conditions match and that the platform enforces who can still read and use it.

## Where to read

| File | What to look for |
| --- | --- |
| [README.md](README.md) | The project in one paragraph, the demo, and how to join the build. |
| [REQUIREMENTS.md](REQUIREMENTS.md) | The agreed MVP in plain words, requirements R1–R11, the demo sequence, what is out of scope, and the decisions log. |
| [BRIEF.md](BRIEF.md) | The judging requirements, the event deadline, and the pinned ARA and AutoSci sources. |
| [PLATFORM.md](PLATFORM.md) | The benchmark, API and permissions, approval, history, presenter service, expected receipts, interface and credits. |
| [TASKS.md](TASKS.md) | Owners, acceptance checks, schedule, and the latest commands and observed results. |
| [HARNESS.md](HARNESS.md) | The order of integration and the evidence to show in the demo. Use the task board for current milestones. |
| [AGENTS.md](AGENTS.md) | The instructions teammates and their coding assistants follow when implementing and verifying work. |
| [GOAL-PROMPT.md](GOAL-PROMPT.md) | The original kickoff planning assignment. |

## What you can verify today

The standalone API and presenter can be checked against Atlas independently of the selected experiment. The lookup data in tests is a verification fixture.

The event Atlas round trip, applicability labels, approval, agent execution, lifecycle checks and the guided UI are build gates. Look for a handoff with a commit, an exact command, and an observed result before treating a gate as passed. A fixture or stub result can verify wiring. The live Atlas gate requires an event Sandbox run. [Verification gates](TASKS.md#verification-gates) · [Handoffs](TASKS.md#handoffs)

## How to review a build

From the repository root, use a clean checkout and Python 3.11. Ask P1 for the local Sandbox and credential setup, and P4 for the command and commit from the latest rehearsal handoff. The planned entry points below become runnable as their owners land them. Keep credentials and private receipts local.

```sh
python -m pip install -r requirements.txt
python -m platform_api.preflight
python -m demo.check_platform
python -m demo.check_presenter
```

For API startup and configuring the selected experiment, see [Backend setup](BACKEND.md).

| Claim | What to inspect |
| --- | --- |
| A publishes useful evidence | Find the positive, valid negative, other-cohort and crashed receipts. Completed ones show the fixture, cohort, job, measured ratio, threshold, successful decode and a rerun command. The crash is `crashed / invalid / undetermined` and never appears in search. |
| B finds relevant research | After A exits, use a fresh B session. Its paraphrased question should find the two applicable cohort A findings and the cohort B finding through Atlas Vector Search, with the platform labelling the cohort B finding as a mismatch. |
| Memory changes a real job | Compare the off, on, after-correction and after-correction-and-expiry receipts. Request, candidate jobs and one-job budget should match. Check that the approved memory-on job differs from the baseline because of the cited evidence. Each receipt records who approved it. The rejected decision has no receipt. |
| Access and lifecycle work | Both projects should find their own sentinels. A second project’s direct result and evidence reads should return 404 for the first project’s ref. A superseded or expired version should fail direct read, evidence read, and execution resolution, even if its stale search hit is still present, while history still shows it to project members. |
| Humans stay in control | Start the presenter and walk the Demo page: reject once and confirm nothing ran, approve and see the measured result, correct and expire from the UI and rerun. In Research, the expired finding shows as Expired and the corrected one shows v1 and v2. Settings shows the isolation check. |

## Record what you saw

Add the task ID, commit, exact command or browser steps, observed outcome, and any missing dependency to the task board. Link the redacted receipt or assertion summary if available. For a failed claim, include the smallest reproducible example, the expected behavior, and what actually happened. [Team handoffs](TASKS.md#handoffs)
