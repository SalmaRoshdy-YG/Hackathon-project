# Requirements

Shared research memory for AI agents, built on MongoDB Atlas. This is the team's agreed MVP. It merges the team requirements list with the hackathon brief. Technical details are in [PLATFORM.md](PLATFORM.md), owners and checks in [TASKS.md](TASKS.md).

> **Memory isn't just information an agent can retrieve. It's evidence that can change what an agent does next.**

## In plain words

**What we're building.** A shared memory where AI agents save what they learned from experiments, both what worked and what failed. Another agent can find that evidence later and use it to choose its next experiment. Humans can inspect the evidence, approve the agent's choice, and correct or expire findings so agents stop relying on bad information.

**How we prove it.** One complete, live research handoff on a tiny experiment that runs in seconds on a laptop, with no model training: making 8 short messages as small as possible. Agent A tries options and saves the findings. A fresh Agent B finds them, skips what failed, ignores a finding from a different group of messages, and recommends a job. A human approves, the job runs, and the result is measured. Then a human corrects one finding and expires another, Agent B reruns the same question, and its evidence and recommendation change.

**Why this experiment.** The judges need to see memory change an action that really runs. Real research such as training neural networks can't run in a five-minute demo, so we use a small, honest stand-in. The ResNet paper is the example we use in the pitch to explain where this goes next; the app does not use it.

## Product vision

- A MongoDB-powered memory that lets independent AI agents discover, retrieve and build on earlier research.
- Agents learn from successful and failed experiments, and don't repeat failures or apply findings to the wrong conditions or cohort.
- Humans inspect the evidence and govern what agents may rely on.
- Long term: a general-purpose research memory for many agents and studies. Hackathon: prove the value with one reproducible handoff.

## Who does what

| Part | Responsible for |
| --- | --- |
| Platform | Authorization by project, current versions, expiry, evidence validity, structured condition matching and applicability labels, returning only authorized evidence, keeping provenance and version history. It does not decide scientific truth, only which evidence is valid and applicable under the defined rules. |
| Agent | Interpreting evidence, reasoning, choosing the next experiment, explaining the recommendation, citing the exact evidence versions it used. |
| Human | Inspecting evidence, approving or rejecting the recommendation, correcting and expiring findings. |
| Execution layer | Running only approved jobs from the allowed catalog, re-checking cited evidence right before running, enforcing the one-trial budget, recording a receipt. |

## Requirements

| ID | Requirement | Acceptance check |
| --- | --- | --- |
| R1 | **Publish findings.** Agent A publishes structured findings: method and configuration, conditions and cohort, outcome, measurements, source agent and provenance. Positive and negative findings are both stored. Execution status (completed, crashed, timed out) is recorded separately from the scientific outcome, so a crash is never read as a failed idea. | A's three findings are stored in Atlas with provenance. A crashed test run is stored as `crashed / undetermined` and never offered as evidence. |
| R2 | **Find by meaning.** A fresh Agent B, worded differently from A, retrieves A's findings through Atlas Vector Search after A has exited. | B's paraphrased question returns A's findings. |
| R3 | **Applicability labels from the platform.** Each retrieved finding is labelled as applying or not applying to B's conditions, with the mismatched fields named. | The cohort B finding is returned labelled "doesn't match: cohort B ≠ A". |
| R4 | **Evidence-grounded recommendation.** B separates applicable successes, applicable failures, mismatched findings, and corrected or expired findings, then recommends one job and cites the exact versions it relied on. | With memory on, B recommends `dict-a-l6`, cites the positive and the negative, skips dictionary B because it failed, and rejects the cohort B finding. With memory off, B recommends the baseline `plain-l1`. |
| R5 | **Human approval.** A human approves or rejects the recommendation. Nothing runs without approval. A rejection is recorded and nothing executes. | Reject leaves no run receipt. Approve allows exactly one run. |
| R6 | **Execute and measure.** The approved job runs, the actual result is measured and stored as a receipt, and it is compared with the memory-off baseline. | Receipts show the executed configuration and byte counts, with memory on beating the baseline. |
| R7 | **Correct a finding.** A human corrects a finding. The new version is identifiable, the previous version and its provenance stay inspectable in the version history, and future retrieval uses only the corrected version. | After correction, B's rerun sees v2 and recommends differently. History shows v1 and v2 with who, when and why. |
| R8 | **Expire a finding.** A human expires a different finding. It stops being eligible evidence immediately, even before database cleanup runs, and the UI shows it as expired. | After expiry, B's rerun no longer receives it, and its skip reasons change. The record still appears as Expired in Research and Governance. |
| R9 | **Rerun after governance.** B reruns the same query after each governance event. Correction and expiry are separate events with separately visible effects. | Four receipts: off, on, after correction, after correction and expiry. |
| R10 | **Project isolation.** Another project cannot find or read these findings. Required by the hackathon brief. | A second project's search and direct reads return nothing (404). |
| R12 | **MongoDB does the work, visibly.** Atlas itself enforces isolation, the current-version check, expiry and applicability in one search query, pushes changes to the UI live, and guarantees governance writes. The demo shows each of these as it happens, from the real commands the platform ran. | One `aggregate` per search returns labelled candidates with stale and expired hits already gone. New and changed findings appear in the UI within a second, without a reload. The Atlas activity strip and each stage's “In MongoDB” callout show only real commands. |
| R11 | **How to rerun.** Each finding's receipt includes the command, fixture and dictionary hashes and library versions needed to reproduce it. | The evidence view shows a rerun command for every measured finding. |

## Interface

A polished web app the presenter drives. Judges should not need to explore it themselves.

- **Look:** inspired by MongoDB: dark green sidebar, light workspace, restrained green accents. Use our own product name and logo, not MongoDB's. Show the Atlas connection without exposing database internals.
- **Sidebar:**
  - **Demo** (default): a guided seven-stage flow with agent activity and evidence, Approve and Reject, the execution result, and governance replay.
  - **Research:** a searchable list of findings with status, outcome, cohort and conditions, source agent, and a detail view with provenance and version history.
  - **Governance:** findings to review, Correct and Expire actions, previous and current versions, change history.
  - **Settings:** Atlas connection status, current project, memory on/off, demo environment info, and an isolation check.
- **Right-hand evidence inspector** that changes with the demo stage.
- **MongoDB visible throughout:** a live Atlas activity strip on every page showing the real commands as they run, and an “In MongoDB” callout at each Demo stage saying what the database just did (for example: searched by meaning inside this project only, dropped a stale version, hid an expired finding before cleanup, approved exactly once).
- **Working buttons:** Approve, Reject, Correct, Expire and Re-run all work, and the UI visibly updates.

## Demo sequence

Each stage names what MongoDB did, shown live from the real commands.

| Stage | What happens | What MongoDB does on screen |
| --- | --- | --- |
| 1. Agent A discovers | A publishes a success, a failure, a finding from another cohort, and a crash. | Inserts land and stream into the UI live through change streams. |
| 2. MongoDB remembers | A fresh Agent B retrieves A's findings by meaning. | Atlas Vector Search, filtered to this project inside the query. |
| 3. Agent B recommends | Applicable, failed and mismatched evidence, then the recommendation. | The same query checks each hit against the live record and labels the cohort mismatch. |
| 4. Human approves | Approve, or reject. | An atomic update approves exactly once; a second click is refused. |
| 5. Agent B executes | The job runs and is compared with the baseline. | Cited versions are re-read right before running; the receipt is stored and streamed. |
| 6. Governance | Correct one finding and rerun; expire another and rerun. | A transaction keeps v1 in history and makes v2 current. The old search entry is still in the index but the query drops it. Expiry hides the finding instantly; TTL cleanup comes later and nothing waits on it. |
| 7. Updated decision | How the evidence and recommendation changed. | Each receipt lists the exact versions it read from Atlas. |

## Out of scope for the hackathon

Research tree or graph visualization. Multiple research domains, including the ResNet showcase. Open-experiment board and claiming. ARA or AutoSci adapters or runtimes. Complex multi-agent orchestration. Complex permissions, user accounts, invitations and team management. Analytics dashboards. Extensive settings. Other databases and broad third-party integrations. General-purpose autonomous agent infrastructure. Model training of any kind.

**Priority rule:** if a feature doesn't help show shared research memory, evidence applicability, agent decision-making, execution or human governance, it's outside the MVP.

## Next, after the hackathon

These come from the original business goals and stay on the roadmap:

- **Real research content.** Load published studies such as the ResNet artifact from [ARA's examples](https://github.com/ARA-Labs/Agent-Native-Research-Artifact/tree/e52a925e9d03b4ada3008653e72f99b04116fca2/examples/resnet-ara-example), with ruled-out explanations and reproduction gaps (missing seeds, framework version, batch-norm momentum).
- **Open experiments.** A board of experiments nobody has run yet, with claiming so agents don't duplicate work.
- **Independent verification.** Re-runs by a second agent.
- **Imports.** ARA and AutoSci adapters.
- **Research tree.** A visual of how findings connect.
- **Sharing across teams and organizations.**

## Decisions log

- **November 14, 2026: build our own platform.** We don't run or adapt ARA or AutoSci. ARA's idea of keeping dead ends as first-class records with a reason, and AutoSci's list of failed ideas not to revisit, inspired R1 and R4 and are credited in [PLATFORM.md](PLATFORM.md#credits).
- **November 14, 2026: follow the team requirements list.** One domain, one guided handoff, human approval, both governance events live, and visible version history. Where the team list was silent, the brief's requirements were added: project isolation (R10), paraphrased search (R2), stale search hits dropped (R7, R8), and the exact versions cited in each decision (R4). The team list mentioned both a "six-stage workflow" and seven demo steps; we use seven.

## Definition of done

- [ ] Agent A publishes structured findings, positive and negative, with provenance in Atlas.
- [ ] A fresh Agent B retrieves them by meaning after A exits.
- [ ] The platform labels each finding as applicable or not, and B separates applicable, failed and mismatched evidence.
- [ ] B makes a recommendation that cites exact versions.
- [ ] A human approves or rejects it, and execution respects the decision.
- [ ] The approved job runs and records a measured receipt that beats the memory-off baseline.
- [ ] A human corrects one finding and expires another, both from the UI.
- [ ] B reruns the same query after each, and its evidence and recommendation reflect the change.
- [ ] Another project gets nothing back.
- [ ] Every Demo stage shows what MongoDB did, from real commands, and findings update live without a reload.
- [ ] The whole flow is shown through the guided interface in under three minutes.
