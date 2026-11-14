# Shared research memory for the MongoDB Toronto hackathon

## Product and scope

When many AI agents run experiments, each agent should be able to build on another agent’s successes and learn from its valid negative results. A reusable result carries the conditions under which it applies and enough evidence to inspect or reproduce it. The MVP is a governed handoff between two fresh agent sessions working on a single, fast, reproducible benchmark. The plan should explain how this handoff could repeat across many agents while keeping today’s build to one loop.

- **Track.** Memory You Can Govern. Use MongoDB Atlas and Vector Search for persistent memory that changes a subsequent action. Show who can access a result, when it expires, and how it can be corrected or forgotten.
- **Agent A.** Run and publish at least one measured positive result and one valid negative result. Tie each to a hypothesis, dataset or fixture version, configuration, metric and threshold, evidence or run receipt, and source agent. Record execution status, scientific validity, and result direction independently so a crash or inconclusive run cannot be mistaken for a valid negative.
- **Agent B.** Start a fresh session with a goal phrased differently from Agent A’s notes. Retrieve scoped candidates semantically, decide which evidence applies, skip a previously failed path under matching conditions, and run a real follow-up based on the promising result. Include a plausible distractor from different experimental conditions and make the decision depend on applicability.
- **Comparison.** Hold the research request, candidate actions, and budget fixed. Run with memory disabled, enabled, and after one material correction or expiration. Compare executed job receipts, including the configuration and result, and record the exact memory versions that affected the decision. Specify how to test both correction and expiry, even if the live demo shows only one.
- **Governance.** Give the plan a trusted project identity, explicit read/write rules, and tests for cross-project semantic search and direct lookup. Consider scoped Vector Search followed by a check of the authoritative record before exposing memory to the agent or relying on it at execution. Plan for corrections and expiry to take effect even while search indexing or TTL cleanup catches up. Tie evidence access to the same scope as the result. [MongoDB Vector Search filtering](https://www.mongodb.com/docs/vector-search/query/aggregation-stages/vector-search-stage/) · [MongoDB TTL behavior](https://www.mongodb.com/docs/manual/core/index-ttl/)

## Local and upstream starting points

Use the pinned public sources from any checkout. Teammates with the BlinkTech workspace also have the optional local references below. Verify the actual input/output shape and integration point at the chosen revision.

| Reference | Where to start | What to look for |
| --- | --- | --- |
| ARA | [Pinned ARA README](https://raw.githubusercontent.com/ARA-Labs/Agent-Native-Research-Artifact/e52a925e9d03b4ada3008653e72f99b04116fca2/README.md), [pinned companion artifacts](https://github.com/AmberLJC/ara-paperbench/tree/3fe7ab4d08f68555d8c4661fa2b4fbfd4d597fd8/artifacts), and [ARA paper](https://arxiv.org/abs/2604.24658v3). Optional local copies are under `agenticse-study/.local/ara-run/`. | A concrete exploration node, its link to evidence, and the smallest mapping that preserves a failed branch and its conditions. |
| AutoSci | [Pinned release README](https://raw.githubusercontent.com/PKU-DAIR/AutoSci/6bc834a805a1744959a9983809e5d6f0263ef791/README.md), [experiment evaluation skill](https://github.com/PKU-DAIR/AutoSci/blob/6bc834a805a1744959a9983809e5d6f0263ef791/i18n/en/skills/exp-eval/SKILL.md), and [AutoSci paper](https://arxiv.org/abs/2605.31468v1). No local checkout was identified in this workspace. | SciMem’s experiment records and the run/evaluation handoff where an outcome can be published or used to choose the next job. Verify the runtime required for any direct reuse. |
| Optional BlinkTech background | `agenticse-study/baseline-comparison-plan.md`, `inner-docs/docs/05-landscape/systems/autosci-ara-requirements-comparison.md`, and Experiment Triage in `HACKATHON-IDEAS.md`. | Use prior findings to narrow the search when that workspace is available. |

**Team decision, November 14:** we build our own platform and reuse ARA concepts and the ResNet example as credited showcase data, with no ARA or AutoSci adapters on the build path. See [REQUIREMENTS.md](REQUIREMENTS.md#decision-our-own-platform-aras-ideas-and-data). The original guidance follows.

Choose between a narrow native hook and a small adapter based on verified interfaces and the time available. Say exactly which ARA and AutoSci mechanism each choice uses and what it costs to integrate. Record versions, license notices, and provenance for any proposed reuse. The event guide permits a public submission with rights-cleared material and requires that the demo clearly identify work built during the event. Confirm any material ambiguity about permitted reuse with the organizers before depending on it.

## Event constraints from the participant guide

- Build window is **10:45 a.m.–5:00 p.m. Toronto time**. Use the event-provided **MongoDB Atlas Sandbox** for the project. Sandbox access, index creation privileges, and model/embedding credentials still need team verification.
- Submission requires a public repo, an accessible one-minute demo video, and all team members listed. Teams can have at most four members. Reserve time to rehearse, record, and submit. [Submission form](https://cerebralvalley.ai/events/~/e/mongodb-toronto-hackathon/hackathon/submit)
- Live judging gives about three minutes to demo. Round one weights technical demo 35%, implementation difficulty 30%, creativity 15%, and impact 20%. The final weights all four equally. Make the agent’s experiment choices and their evidence the demo centerpiece. The guide excludes basic RAG, Streamlit, and projects where a dashboard is the main feature.

## What to settle at kickoff

Record shared decisions in [PLATFORM.md](PLATFORM.md) and owned first tasks in [TASKS.md](TASKS.md). Keep extended planning notes in `PLAN.md` if helpful.

1. **Benchmark and decision.** Choose one CPU-runnable case. Specify fixture or dataset version, metric and threshold, actual candidate jobs, known positive and negative outcomes or how to verify them early, and the expected action in each comparison run. A valid negative should only constrain a follow-up within its measured conditions. Define which decision the agent makes and which constraints code enforces.
2. **Interfaces and data.** Name the agent runner, experiment runner, exact ARA and AutoSci integration points, collection and index fields, and the publish, retrieve, correct and expire paths. Show representative inputs and outputs and who is allowed to call each path. Describe how the planner’s chosen action becomes an actual, inspectable execution.
3. **Acceptance checks.** Include a paraphrased semantic query, a relevant-looking result under mismatched conditions, no-memory versus memory job receipts, correction or expiry changing the next job, the other lifecycle check, and denial of access across projects. Include the expected behavior for a stale search hit and a selectivity check showing that the allowed identity still receives its own result.
4. **Build and demo.** Give the first task for each workstream, dependencies, timeboxes, and a minimum demo path if a native integration slips. Keep the real Atlas Vector Search path in the minimum demo. Assign early verification of sandbox and index readiness. Include a one-minute recording sequence, the three-minute live path, and a deadline for freezing the build.

Pressure-test the plan for a slow search index, an upstream hook that needs extra tooling, an unconvincing baseline, and a demo run that takes too long. Resolve implementation choices where evidence permits and give each remaining dependency an owner, a check, and a decision deadline. End with the first implementation task and its pass condition.
