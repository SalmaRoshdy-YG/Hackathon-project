# Requirements

Precedent is a shared research memory for AI agents, built on MongoDB Atlas. This is the team's agreed MVP. Technical details are in [PLATFORM.md](PLATFORM.md), owners and checks in [TASKS.md](TASKS.md), and track rules in [BRIEF.md](BRIEF.md).

> **Memory isn't just information an agent can retrieve. It's evidence that can change what an agent does next.**

## In plain words

**What we're building.** A shared memory where AI agents save what they learned from experiments, both what worked and what failed, together with the model weights they trained. Another agent can find that evidence later and use it to choose and run its next experiment. A person watches, decides what runs, and can later correct or expire findings.

**The demo task.** Fine-tune a ResNet-18 to 90% accuracy on CIFAR-10 in one run of about two GPU-minutes, on the team's own GPU PC. Real training, no simulation.

- **Claude Code on its own** has no history. It trains from scratch and lands around 71%.
- **Claude Code with Precedent** searches the memory, finds that fine-tuning stored ImageNet weights worked on this exact task, that a high learning rate from scratch diverged, and that a Fashion-MNIST result doesn't fit. It proposes a plan, you say "Run it", and it reaches about 93%.
- Its result and new weights are saved back as a new experiment for the next agent.

**Why this experiment.** Judges must see memory change an action that really runs. A ResNet-18 on CIFAR-10 trains in about a minute on a GPU, so the whole loop fits in three minutes and the numbers are real. The pitch ties it to the original ResNet paper and to research in general. The mockup numbers are placeholders until the team measures them on the GPU PC.

**What the screen is.** A single guided view built around Claude Code in an embedded terminal. The experiments it reads light up beside it. A plan appears, you confirm, a result appears. This is not an admin dashboard, and the demo never depends on browsing tables.

## Product vision

- A MongoDB-powered memory that lets independent AI agents discover, retrieve and build on earlier research, including stored weights.
- Agents don't repeat failures or apply findings to the wrong conditions.
- Humans decide what runs. Later phases let them correct and expire findings.
- Long term: a general research memory for many agents and studies. Hackathon: prove the value with one real handoff.

## Who does what

| Part | Responsible for |
| --- | --- |
| Platform | Authorization by project, current versions, expiry, evidence validity, structured condition matching and fit labels, returning only authorized evidence, keeping provenance and history. It does not decide scientific truth, only which evidence is valid and applicable under the defined rules. |
| Agent (Claude Code) | Runs in a terminal embedded in the page. Searches the memory through Precedent's MCP tools, interprets what it finds, proposes a plan with reasons, cites the exact versions it used, and runs only what the person confirms. |
| Human | Asks Claude Code what to build on, then confirms ("Run it") or declines ("Not now"). That confirmation is the approval. |
| Execution layer | Running only approved jobs from the allowed catalog on the local GPU, re-checking cited evidence right before running, enforcing the one-run budget, recording a receipt and the new weights. |

## Requirements (the MVP)

| ID | Requirement | Acceptance check |
| --- | --- | --- |
| R1 | **Publish findings.** Agents publish structured experiments: what was tried, conditions (dataset, model, input size), outcome and measurements, source agent, and weights where there are any. Positive and negative results are both stored. Execution status (completed, crashed) is recorded separately from the outcome, so a crash is never read as a failed idea. | Four seeded experiments are in Atlas with provenance. The out-of-memory run is stored as `crashed / undetermined` and is never offered as evidence. |
| R2 | **Find by meaning.** A fresh agent, worded differently from the publisher, retrieves relevant experiments through Atlas Vector Search. | Claude Code's differently worded question returns the ResNet-18 experiments. |
| R3 | **Fit labels from the platform.** Each result is labelled as fitting or not fitting the task, with the mismatched fields named. | The Fashion-MNIST result comes back as "doesn't fit: dataset, input size". |
| R4 | **Evidence-grounded plan.** Claude Code separates what worked, what failed and what doesn't fit, proposes one job, and cites the exact versions it relied on. | With Precedent it proposes fine-tuning from stored weights and cites the positive and the failed run. On its own it trains from scratch. |
| R5 | **Human approval.** Nothing runs without the person's confirmation. "Not now" is recorded and nothing executes. | "Not now" leaves no run. "Run it" allows exactly one run, even if clicked twice. |
| R6 | **Execute and measure for real.** The approved job trains on the GPU, accuracy is measured on the CIFAR-10 test set, and a receipt is stored and compared with Claude Code on its own. | Receipts show the executed configuration, accuracy and GPU seconds, and the Precedent run beats the baseline. |
| R7 | **Claude Code in the loop.** Claude Code reaches Precedent only through MCP tools (`search_experiments`, `get_experiment`, `propose_plan`, `run_plan`, `load_weights`, `publish_result`). The experiments it reads light up as using, avoiding or doesn't fit. | Asking in the terminal highlights the right experiments within a second. Declining leaves no run. Confirming runs once. The new experiment appears and cites the versions it used. |
| R8 | **Reuse stored weights.** Fine-tuning starts from weights stored in MongoDB (GridFS) or a named packaged checkpoint, and the new weights are saved with the new result. | The run loads weights from Atlas, and the new experiment has its own weights file. |
| R9 | **MongoDB does the work, visibly.** One Atlas aggregate per search enforces project isolation, the live-version check and fit labels. The page shows only real commands in the Atlas activity strip and in one "In MongoDB" sentence per stage. New experiments appear without a reload. | The strip shows the real `aggregate`, the atomic approval update and the new insert. No hardcoded lines. |
| R10 | **Project isolation.** Another project cannot find or read these experiments. Required by the hackathon brief. | A second project's search and direct reads return nothing (404). |
| R11 | **How to rerun.** Every measured experiment includes the command, seed and library versions needed to reproduce it. | The detail drawer shows a rerun command for every measured experiment. |

## Phase 2: governance (built in the backend, not on the demo path yet)

The platform already supports these. They stay on the roadmap and in the pitch, but the first demo does not depend on them. Add them to the live demo only after R1–R11 are rehearsed.

| ID | Requirement | Acceptance check |
| --- | --- | --- |
| G1 | **Correct a finding.** A person corrects an experiment. The new version is current, the old one stays readable in history, and agents only see the new version. | After correction, the same question gets a different plan and history shows v1 and v2 with who, when and why. |
| G2 | **Expire a finding.** A person expires an experiment. It stops being evidence immediately, even before database cleanup. | After expiry, the same question no longer returns it. |
| G3 | **Rerun after governance.** Ask the same question after each event and compare the plan and result. | Receipts: on its own, with Precedent, after correction, after correction and expiry. |

## Interface

One screen, built so the presenter can drive it and the judges never need to explore it.

- **Top bar:** product name, the four demo stages, Atlas connection status.
- **Centre:** the embedded Claude Code terminal. Beside it, the experiments Claude Code is reading, each marked using, avoiding, doesn't fit or never offered (crashed).
- **After the run:** one result card comparing Claude Code on its own with Claude Code and Precedent against the 90% target.
- **Details on demand:** clicking an experiment or an Atlas line opens a drawer with conditions, outcome, rerun command, weights and record. No tables, no admin pages.
- **Atlas activity strip** on the bottom: the real commands as they run. One **"In MongoDB"** sentence per stage.
- **Look:** dark green top bar, light workspace, restrained green accents. Our own name and mark, not MongoDB's.
- **Not in the MVP interface:** Research and Governance pages, Settings page, tables of findings, analytics. The clickable mockup is [docs/demo/index.html](docs/demo/index.html).

## Demo sequence (four stages, about three minutes)

| Stage | What happens | What MongoDB does on screen |
| --- | --- | --- |
| 1. Past experiments | Show what other agents tried: what worked, what failed, what crashed, which weights are stored. | Each experiment is a document, weights are in GridFS, new ones stream in through change streams. |
| 2. Ask Claude Code | Ask it to build on past work. The experiments it picks light up as using, avoiding or doesn't fit. | `search_experiments` is one aggregate: vector search inside this project, the live-version check and fit labels. |
| 3. You decide | Claude Code shows its plan. You say "Run it" or "Not now". | The plan is stored as pending. Confirmation is one atomic update, so it runs exactly once. |
| 4. Result | It loads the stored weights, trains on the GPU, and the result sits next to Claude Code on its own. The result is saved as a new experiment. | Cited versions are re-checked, weights stream from GridFS, the new experiment is inserted and pushed to the screen. |

## Out of scope for the hackathon

Governance in the live demo (Phase 2 above). Research tree or graph visualization. Multiple research domains. ImageNet-scale training. Open-experiment board and claiming. ARA or AutoSci adapters or runtimes. Complex multi-agent orchestration. User accounts, invitations and team management. Analytics dashboards. Settings pages. Other databases.

**Priority rule:** if a feature doesn't help show shared research memory, evidence fit, the agent's decision, a real run, or the person's approval, it's outside the MVP.

**Training scope.** The only training in the project is the single approved fine-tuning job in the demo catalog and the calibration runs that produce the seeded experiments. Nothing else trains.

## Next, after the hackathon

- **Governance in the live flow** (Phase 2).
- **Real research content.** Load published studies such as the ResNet artifact from [ARA's examples](https://github.com/ARA-Labs/Agent-Native-Research-Artifact/tree/e52a925e9d03b4ada3008653e72f99b04116fca2/examples/resnet-ara-example), including the original ImageNet results and reproduction gaps.
- **Open experiments.** A board of experiments nobody has run yet, with claiming so agents don't duplicate work.
- **Independent verification.** Re-runs by a second agent.
- **Imports.** ARA and AutoSci adapters.
- **Sharing across teams and organizations.**

## Decisions log

- **November 14, 2026: build our own platform.** We don't run or adapt ARA or AutoSci. ARA's idea of keeping dead ends as first-class records with a reason, and AutoSci's list of failed ideas not to revisit, inspired R1 and R4 and are credited in [PLATFORM.md](PLATFORM.md#credits).
- **November 14, 2026: the baseline lives outside the platform.** There is no memory on/off switch in the demo. The comparison is the same Claude Code run on its own with no Precedent tools, recorded before the demo and shown as "Claude Code on its own". (The backend still accepts a no-evidence proposal for its own contract tests. The demo doesn't use it.)
- **November 14, 2026: Claude Code is the agent in the loop.** The person works with Claude Code in a terminal embedded in the page. It uses Precedent through MCP tools, its chosen experiments are highlighted live, and Claude Code's own permission prompt for `run_plan` is the human approval.
- **November 14, 2026: ResNet-18 on CIFAR-10 replaces the compression benchmark and the handwritten-digit demo.** The team finds a training task easier to understand and has a GPU PC with PyTorch. The compression benchmark and the `use-case-experiment` digit demo were removed. The ImageNet ResNet-50 story stays as the pitch, with illustrative numbers.
- **November 14, 2026: governance moves to Phase 2.** The backend keeps correction, expiry and history, but the live demo is four stages: past experiments, ask, decide, result. This also removes the old contradiction between "no model training" and "Claude Code retrains": real training is now in scope for the single approved job.
- **November 14, 2026: no dashboard pages.** The hackathon guide bans projects whose main feature is a dashboard. The interface is one agent-centred screen.

## Definition of done

- [ ] Four seeded experiments, positive, negative, mismatched and crashed, are in Atlas with provenance and weights where they exist.
- [ ] Claude Code, in the embedded terminal, retrieves them by meaning through MCP.
- [ ] The platform labels each as fitting or not, and the screen highlights what Claude Code uses, avoids and sets aside.
- [ ] Claude Code proposes one job citing exact versions. The person confirms or declines, and execution respects it.
- [ ] The approved job fine-tunes on the GPU from stored weights, and the measured result beats Claude Code on its own.
- [ ] The result and its new weights appear as a new experiment, live, without a reload.
- [ ] Another project gets nothing back.
- [ ] Every stage shows what MongoDB did, from real commands.
- [ ] The whole flow runs through the guided screen in under three minutes.
