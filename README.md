# Precedent: shared research memory for AI agents

AI agents save what worked and what failed on MongoDB Atlas, along with the model weights they trained. A fresh agent finds that evidence by meaning, uses it to choose its next experiment, and runs it after you confirm. Built for the MongoDB Toronto hackathon, track **Memory You Can Govern**.

> Memory isn't just information an agent can retrieve. It's evidence that can change what an agent does next.

## The demo in one minute

Task: train a ResNet-50 to at least 80% accuracy on a handwritten-digit holdout in one four-epoch run, on our own machine.

1. **Past experiments.** Other agents tried things: reusing an ImageNet-initialised checkpoint worked, a very high learning rate failed, a result at a different image size doesn't fit, and one run crashed.
2. **The agent searches.** Codex, in a terminal embedded in the page, searches the memory through MCP tools. The experiments it uses, avoids and sets aside light up.
3. **You decide.** It proposes a plan citing exact versions. You press **Run plan** or **Reject**.
4. **Result.** It loads the stored checkpoint, trains, and beats the same agent on its own (measured once: 90.4% against 29.2%). The result and new checkpoint are saved back as a new experiment.

MongoDB does the work and shows it: one aggregate for search, atomic approval, GridFS for checkpoints, change streams to the screen.

## What is built and what is not

| | State |
| --- | --- |
| Atlas platform: search, versions, expiry, decisions, GridFS artifacts (`platform_api/`) | Built. A teammate reports it verified live on the event Sandbox. |
| ResNet-50 digits experiment (`experiments/resnet.py`) | Built. Crashed-run seed missing. |
| Workbench: embedded Codex terminal, `/mcp`, research library, run comparison (`workbench/`) | Built. Not yet the single-screen design. |
| Pitch mockup and deck | Out of date: still show ResNet-18 on CIFAR-10. |
| Governance (correct, expire, history) | Backend only. Phase 2. |

Status, open work and owners: [TASKS.md](TASKS.md). Ready-to-paste prompts for parallel agents: [PROMPTS.md](PROMPTS.md).

## Run it

[BACKEND.md](BACKEND.md#live-workspace) has the exact steps: install, start the platform and workbench, record the baseline, seed the memory, open the workspace.

## Look at it

- **Clickable mockup:** open [docs/demo/index.html](docs/demo/index.html) in a browser. One screen, four stages, simulated terminal and numbers. It is the design target for the workbench UI. Its task and numbers are being updated to match the real build.
- **Pitch deck:** [docs/deck/precedent-deck.pptx](docs/deck/precedent-deck.pptx), 12 slides with speaker notes. Statistics on slide 2 are cited on the slide. Numbers elsewhere are illustrative and being updated.

## Read in this order

| File | What it is |
| --- | --- |
| [REQUIREMENTS.md](REQUIREMENTS.md) | The agreed MVP in plain words, requirements, interface, scope and decisions. |
| [PLATFORM.md](PLATFORM.md) | The contract: results, routes, Atlas storage, benchmark, agent integration, UI, credits. |
| [BACKEND.md](BACKEND.md) | How to run and verify the Atlas backend and the live workspace. |
| [PROMPTS.md](PROMPTS.md) | Prompts to start the open work in parallel. |
| [TASKS.md](TASKS.md) | Owners, gates, time plan and demo script. |
| [HARNESS.md](HARNESS.md) | The order of integration and the evidence the demo must show. |
| [HUMANS.md](HUMANS.md) | How a reviewer checks the claims. |
| [BRIEF.md](BRIEF.md) | The event rules, judging criteria and upstream references. |
| [AGENTS.md](AGENTS.md) | Rules for teammates and their coding assistants. |

## Start a task

Open the checkout, claim a task on the [team board](TASKS.md), substitute your task ID, and paste this into your assistant.

> Read AGENTS.md, REQUIREMENTS.md, PLATFORM.md, and TASKS.md. I own TASK_ID. Implement its acceptance check through the real platform interface, verify the result, and add a handoff to TASKS.md with the command and observed outcome. Coordinate shared interface changes with the affected owners.

## Credits

Ideas from ARA and AutoSci (no code used), PyTorch, torchvision and scikit-learn as libraries. See [NOTICE.md](NOTICE.md).
