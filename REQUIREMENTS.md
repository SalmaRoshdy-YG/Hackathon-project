# Business requirements

Precedent (working name) is a shared research memory for AI agents. Agents check it before they spend compute, skip what already failed under the same conditions, build on what worked, and publish every outcome back, positive or negative. Researchers use it to see what is known and to pick experiments nobody has run yet. The platform controls who can read each result, which version is current, and when it expires.

[Platform contract](PLATFORM.md) · [Team board](TASKS.md) · [Design reference mockup](docs/mockup/index.html)

## In plain words

**What we're building.** A shared notebook for AI research agents. Before an agent runs an experiment, it looks up what other agents already tried. After it runs one, it writes down what happened, whether it worked or not.

**What it must do today:**

1. **Save every result, good or bad.** Each result says what was tested, under what conditions, what happened, and the proof. A crash is labelled as a crash, never as a failed idea.
2. **Find results by meaning.** An agent can ask in its own words and still find related work.
3. **Help the agent choose.** The agent skips what already failed under the same conditions, builds on what worked, and records which results it relied on.
4. **Show what's needed to repeat a result.** Code, settings, environment and proof, plus a list of what's missing.
5. **List experiments nobody has done yet.** Anyone on the project can claim one so two agents don't do the same work.
6. **Keep it under control.** Only your project can see its results. Fixes keep a history. Expired results disappear right away.

**How we show it:**

- **Research hub (the showcase).** Real data from the ResNet study in ARA's open-source examples: what failed, what worked, and what's still open. Nothing gets trained live.
- **Platform check (the proof).** A small task that runs in seconds. With memory on, the agent picks a better job (238 bytes vs 686). After a fix or expiry, it stops relying on the old result.

**What we're not doing.** We don't run ARA or AutoSci, and we don't build importers for them. We reuse their ideas and the ResNet data, with credit. Re-running experiments and sharing across organizations come later.

## Goals

| Goal | What it means for the product |
| --- | --- |
| Faster research | An agent finds applicable prior results by meaning before it runs anything, and its decision cites the exact versions it relied on. |
| Negative results count | Failed experiments and ruled-out explanations are published and searchable like successes. A crash or inconclusive run is labelled so it is never read as a failed idea. |
| Reproducible and verifiable | Each result carries links to its code, config, environment and evidence, and the platform lists what is missing to reproduce it. |
| Find what hasn't been tried | Researchers and agents browse open experiments and claim one, so nobody duplicates it. |
| Governed memory | Access is scoped to a project by the caller's token. Corrections create versions with an audit trail. Expired results disappear from every read immediately. This is the hackathon track requirement. |

## Users

| User | Question | What the platform gives them |
| --- | --- | --- |
| AI research agent | What should I run next? | Applicable results, dead ends to skip, open experiments to claim, an API to publish its outcome |
| Human researcher | What did my agents do, and why? | Research hub with results, the research tree, evidence and decision receipts |
| Verifier or reviewer | Is this number real? | Reproduction bundle with missing-detail flags, provenance, verification level |
| Project admin | Who can see and change this? | Project tokens and roles, corrections with audit, expiry |

## Two demos with different jobs

| | Showcase: Research hub | Verification: governed handoff |
| --- | --- | --- |
| Purpose | Shows the product idea to judges and researchers | Proves memory changes a job an agent really executes |
| Content | The ResNet research artifact from ARA's open-source examples, plus one crashed run from the ARA Triton artifact | Synthetic `short-events-v1` compression benchmark |
| Runs live? | No model training. Data is seeded once through the publish API. The agent session view is labelled illustrative. | Yes. Agent A publishes, a fresh Agent B searches Atlas, decides and runs a CPU job in under two seconds. |
| Where | `/research` hub views | `/research` Platform verification views and `receipts/rehearsal/` |

The UI keeps the two areas visibly separate so nobody mistakes the illustration for the measurement.

### Showcase use case: ResNet

Source: `examples/resnet-ara-example` in [ARA-Labs/Agent-Native-Research-Artifact at e52a925](https://github.com/ARA-Labs/Agent-Native-Research-Artifact/tree/e52a925e9d03b4ada3008653e72f99b04116fca2/examples/resnet-ara-example) (MIT). Research question: *Is learning better networks as easy as stacking more layers?*

- **Didn't work.** Deeper plain nets degrade on CIFAR-10 (N02) and ImageNet: plain-34 at 28.54% vs plain-18 at 27.94% top-1 error (N03).
- **Ruled out.** Vanishing gradients are not the cause (N04). Training 3× longer does not fix it (N05, inferred from a footnote). Single-layer residual blocks showed no advantage (N10, one remark).
- **Worked.** ResNet-34 at 25.03%, 3.51 points better than plain-34 (N08). Identity shortcuts suffice (N09). Error falls to 21.43% at 152 layers (N12). 110 and 1,202 layers train on CIFAR-10, with 1,202 overfitting at 7.93% vs 6.43% (N13). Detection transfer (N15).
- **Open experiments.** ResNet-1202 with stronger regularization (`solution/constraints.md`). Measure single-layer residual blocks (N10). Log curves for 3× plain training (N05). Test assumption A1 (footnote 2). Pin seeds for ResNet-110 (`src/environment.md`). Retry the Triton kernel loaded by import (Triton N120 crashed, so the idea is untested).
- **Reproducibility gaps.** Seeds, framework version and batch-norm momentum are not specified (`src/environment.md`).

Agent journey shown in the hub: ask in its own words → search by meaning → skip known failures → build on applicable results → claim an open experiment → publish the outcome, positive or negative.

## Requirements

Scope: **MVP** is built today. **Next** and **Later** are roadmap only.

| ID | Requirement | Scope | Acceptance check |
| --- | --- | --- | --- |
| BR1 | Publish experiment results and ruled-out explanations with conditions, metric, evidence, source and lifecycle. Execution status, validity and direction are recorded separately. | MVP | Seed publishes the ResNet results and Triton N120. N120 stays `crashed / invalid / undetermined`, is visible in direct read and the hub, and is excluded from search and resolve. Agent A publishes its three benchmark results. |
| BR2 | Search by meaning, filtered to the caller's project from its token. Hits are re-checked against the authoritative record. | MVP | A paraphrased question returns the applicable results. A second project gets only its own sentinel. Stale and expired hits are dropped. |
| BR3 | An agent skips known failures and builds on applicable results under matching conditions, and records a decision receipt with exact cited versions. | MVP | Verification rehearsal: memory off, on, corrected and expired produce the expected jobs and receipts. |
| BR4 | Each result can carry a reproduction bundle. The platform computes which standard items are missing. | MVP | ResNet N08 returns `missing: ["seeds", "framework version", "batch-norm momentum"]`. A benchmark result with a full runner receipt returns `complete: true`. |
| BR5 | Open-experiment board: create, list, claim, release. A published result can close the open experiment it answers. | MVP | Two concurrent claims on G1 give one 200 and one 409. Another project gets 404. Publishing a result with `closes_open_id` marks the item closed and links the result. |
| BR6 | Corrections with versions and audit, manual and scheduled expiry, project isolation on every read path. | MVP | Existing lifecycle and isolation gates in [TASKS.md](TASKS.md#verification-gates). |
| BR7 | Import ARA and AutoSci artifacts through adapters. | Optional, deferred | Not required. The showcase uses a hand-built seed file instead. |
| BR8 | Platform re-runs and independent verification by a second agent. | Next | MVP stores `verification: "reported"` for imported results and `"measured"` for runner receipts. |
| BR9 | Sharing results across organizations. | Later | Out of scope. |

## Decision: our own platform, ARA's ideas and data

Decided November 14, 2026. BR7 is optional, and the team builds its own platform instead of running ARA or AutoSci.

- **Why.** ARA is a file layout plus agent skills for a single researcher. AutoSci is a Claude Code wiki runtime. Neither has a shared store, an API, cross-agent search, or access, correction and expiry rules, so BR2, BR3, BR5 and BR6 must be built either way. The judging weights implementation difficulty and the MongoDB Atlas memory track, and the event requires the demo to identify event-built work.
- **What we reuse.** ARA's concepts shape the result model: dead ends as first-class records with a reason, explicit versus inferred support, and results bound to code, config and evidence. The ResNet artifact and the Triton N120 node become showcase data. AutoSci's failed-idea banlist (`/ideate`) inspired BR3. All reuse is credited in [PLATFORM.md](PLATFORM.md#upstream-reuse-and-credits).
- **What changes.** No adapters on the build path. The showcase loads from `fixtures/showcase/*.json` through the normal publish API. Agent A in the verification benchmark publishes directly. The former adapter owner moves to the showcase seed and the open-experiment board.

## Non-goals for the hackathon

- Training or re-running ResNet models.
- Running ARA skills or the AutoSci runtime.
- Cross-organization sharing, billing, user accounts beyond static project tokens.
- A dashboard as the main feature. The agent's choices and their evidence stay the demo centerpiece.

## Success measures

Product: repeated failed experiments avoided, time to first useful result for a new agent, share of results with a complete reproduction bundle, open experiments claimed and closed.

Demo, pass or fail: a reworded question finds the right results; a result from different conditions is rejected; memory on runs a different, better job; correction or expiry changes the next job; another project gets nothing back; a concurrent claim is refused.
