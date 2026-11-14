# Hackathon-project

We’re building a shared research memory on MongoDB Atlas where AI agents save what worked and what failed, and other agents use that evidence to choose their next experiment. Humans inspect the evidence, approve the agent’s choice, and correct or expire findings. [Requirements in plain words](REQUIREMENTS.md#in-plain-words)

> Memory isn’t just information an agent can retrieve. It’s evidence that can change what an agent does next.

## Live application

The Precedent workspace connects an embedded Codex terminal to shared research memory over MCP. Browse experiments, inspect what Codex cites, review its proposed job, and compare measured results. The ResNet-50 example uses handwritten digits and stores its checkpoints in Atlas GridFS. The workspace can use another registered experiment profile.

- [Start the workspace and run ResNet-50](BACKEND.md#live-workspace)
- [Open the original interface mockup](docs/demo/index.html)
- [Read the pitch deck](docs/deck/precedent-deck.pptx)

## Start here

For the live Atlas backend, setup commands, and frontend API, see [BACKEND.md](BACKEND.md).

Reviewing the project? Use the [human review guide](HUMANS.md) to find the relevant files, checks, and evidence.

Put these Markdown files at the root of the team’s hackathon repository so each teammate and their assistant can use the same instructions. Open that checkout, claim a task on the [team board](TASKS.md), substitute your task ID, and paste this into your assistant.

> Read AGENTS.md, REQUIREMENTS.md, PLATFORM.md, and TASKS.md. I own TASK_ID. Implement its acceptance check through the real platform interface, verify the result, and add a handoff to TASKS.md with the command and observed outcome. Coordinate shared interface changes with the affected owners.

Use the same prompt to resume a task in a fresh session. [HARNESS.md](HARNESS.md) covers kickoff, integration, and demo. [GOAL-PROMPT.md](GOAL-PROMPT.md) is for the kickoff planner. [BRIEF.md](BRIEF.md) contains the track rules and upstream references.
