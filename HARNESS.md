# Platform build harness

Each teammate uses their own coding assistant with the same [platform contract](PLATFORM.md) and [task board](TASKS.md). The [README](README.md) has the prompt to start or resume any task.

## Kickoff

Assign workstream owners, integration lead, and submitter. Choose one fast CPU benchmark, the shared entry point, and the model and embedding setup. Record decisions and example payloads in PLATFORM.md before callers diverge. The Atlas owner verifies access, starts the search index early, and tests an authorized query. Teammates can use separate fixture namespaces for smoke checks.

## Build and integrate

1. Get one vertical slice working. Publish a measured outcome through the platform, retrieve it from event Atlas, and get a second agent to run a job. Carry the memory ID and version into the decision receipt.
2. Wire the narrow ARA and AutoSci adapters to that same interface. Teammates can work against fixtures while Atlas or the upstream hooks are getting ready. Label fixture-only checks in the handoff.
3. Add correction, expiry, and isolation. Rehearse from a clean checkout. Leave the exact commands and results on the task board so the next teammate can pick up immediately.

Use separate branches or worktrees as needed. Agree on an owner for any shared file being edited in parallel. Keep credentials in local environment variables, use synthetic fixtures, and record upstream notices in the public repository.

## Demo acceptance

| Claim | Evidence |
| --- | --- |
| Persistent governed memory | A fresh agent retrieves applicable evidence via event Atlas Vector Search after the producer exits. Use a paraphrased request and an inapplicable distractor to show why experimental conditions matter. |
| Memory changes behavior | With the same request, candidate jobs, and budget, compare actual executed configurations and outcomes with memory off, on, and after correction or expiry. Capture the exact result versions used. |
| Lifecycle and isolation | The owning project can search and look up the result. A second project fails both paths. Stale hits for expired or superseded versions are excluded. |
| Platform reuse | Show a representative ARA and AutoSci mapping to the same publish contract. If a native hook slips, use the smallest verified adapter and state what integration the demo proves. |

Suggested milestones in Toronto time are a real Atlas round trip by noon, an end-to-end path by 2 p.m., and a demo freeze at 4 p.m. Adjust them at kickoff and protect the 5 p.m. submission deadline. Cut demo polish or simplify adapters first if time is tight.

Center the one-minute submission video on the different jobs actually executed. Use the three-minute live demo to show the Atlas path, changed decision, and project isolation. Confirm the repository is public, the video is accessible, and all team members are listed. [Submission form](https://cerebralvalley.ai/events/~/e/mongodb-toronto-hackathon/hackathon/submit)
