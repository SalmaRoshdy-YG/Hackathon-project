# Hackathon-project

We’re building a shared research memory where AI agents publish what worked and what didn’t, find related experiments by meaning, skip known failures, and pick experiments nobody has run yet. The platform controls who can use each result, which version is current, and when it expires. [Requirements in plain words](REQUIREMENTS.md#in-plain-words)

## Two demos

- **Research hub.** The ResNet study from ARA’s open-source examples, seeded through our API: negative results, ruled-out explanations, reproduction gaps and open experiments to claim. [Hub design](PLATFORM.md#research-hub-ui) · [Mockup](docs/mockup/index.html)
- **Platform verification.** One fast CPU benchmark proves the memory changes the job a fresh agent actually runs, and that corrections, expiry and project isolation take effect. [Benchmark](PLATFORM.md#first-benchmark-and-agent-decision)

## Start here

Reviewing the project? Use the [human review guide](HUMANS.md) to find the relevant files, checks, and evidence.

Put these Markdown files at the root of the team’s hackathon repository so each teammate and their assistant can use the same instructions. Open that checkout, claim a task on the [team board](TASKS.md), substitute your task ID, and paste this into your assistant.

> Read AGENTS.md, REQUIREMENTS.md, PLATFORM.md, and TASKS.md. I own TASK_ID. Implement its acceptance check through the real platform interface, verify the result, and add a handoff to TASKS.md with the command and observed outcome. Coordinate shared interface changes with the affected owners.

Use the same prompt to resume a task in a fresh session. [HARNESS.md](HARNESS.md) covers kickoff, integration, and demo. [GOAL-PROMPT.md](GOAL-PROMPT.md) is for the kickoff planner. [BRIEF.md](BRIEF.md) contains the track rules and upstream references.
