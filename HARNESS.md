# Platform build harness

Each teammate uses their own coding assistant with the same [platform contract](PLATFORM.md) and [task board](TASKS.md). The [README](README.md) has the prompt to start or resume any task.

## Build and integrate

1. **Verify what exists.** Run the Atlas preflight and the platform and presenter checks against the event Sandbox. Teammates can work against stubs while Atlas is verified. Label stub-only checks in the handoff.
2. **Get one real slice.** Calibrate and publish the seeded ResNet experiments (with weights), search them from event Atlas, and have Claude Code propose a plan citing exact versions.
3. **Close the loop.** Add the approval step and the run: confirm in the terminal, train on the GPU from stored weights, save the result and new weights back.
4. **Wire the screen.** The UI shows the same slice from real events. Then rehearse from a clean checkout.
5. **Only then** add Phase 2 governance (correct, expire) to the live flow.

Use separate branches or worktrees. Agree on an owner for any shared file edited in parallel. Keep credentials in local environment variables and out of the public repo, and record upstream notices.

## Demo acceptance

| Claim | Evidence |
| --- | --- |
| Persistent shared memory | A fresh Claude Code session retrieves relevant experiments via event Atlas Vector Search after the seeding agents have exited, using a differently worded request and a distractor that doesn't fit. |
| Memory changes behavior | With the same request, candidate jobs and budget, compare the executed job, accuracy and GPU time for Claude Code on its own and Claude Code with Precedent. Capture the exact versions cited. |
| Humans decide | A confirmation in the terminal is the only way a plan runs. "Not now" leaves no run, and a plan runs at most once. |
| Isolation | The owning project finds and reads its experiments. A second project fails both search and direct read. |
| MongoDB visibly does the work | The Atlas strip and the per-stage sentence show the real search pipeline, the atomic approval, the weights stream and the live change-stream insert. |

## Fallbacks

If Claude Code is unstable, run a scripted planner that applies the same evidence rules and label it. If the embedded terminal fails, run Claude Code in a normal terminal beside the browser. If Atlas becomes unavailable late, present verified receipts from an earlier real run and say so. Cut polish before cutting the real Atlas search, the approval or the real training run.

## Submission

Center the one-minute video on the different jobs that actually ran. Use the three-minute live demo to walk the four stages. Confirm the repository is public, the video is accessible signed out, and all team members are listed. [Submission form](https://cerebralvalley.ai/events/~/e/mongodb-toronto-hackathon/hackathon/submit)

The timings and the demo script are in [TASKS.md](TASKS.md#time-plan-to-the-500-pm-submission).
