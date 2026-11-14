# Precedent: shared research memory for AI agents

AI agents save what worked and what failed on MongoDB Atlas, along with the model weights they trained. A fresh agent finds that evidence by meaning, uses it to choose its next experiment, and runs it after you confirm. Built for the MongoDB Toronto hackathon, track **Memory You Can Govern**.

> Memory isn't just information an agent can retrieve. It's evidence that can change what an agent does next.

## The demo in one minute

Task: fine-tune a ResNet-18 to 90% on CIFAR-10 in one run of about two GPU-minutes, on our own GPU.

1. **Past experiments.** Other agents tried things: fine-tuning from ImageNet weights worked, a high learning rate from scratch diverged, a Fashion-MNIST result doesn't fit, one run crashed.
2. **Ask Claude Code**, in a terminal embedded in the page. It searches the memory through MCP tools. The experiments it uses, avoids and sets aside light up.
3. **You decide.** It proposes a plan citing exact versions. You say "Run it" or "Not now".
4. **Result.** It loads the stored weights, trains, and beats Claude Code on its own (about 93% against about 71%). The result is saved back as a new experiment.

MongoDB does the work and shows it: one aggregate for search, atomic approval, GridFS for weights, change streams to the screen.

## What is built and what is not

| | State |
| --- | --- |
| Atlas platform: search, versions, expiry, decisions, command listener (`platform_api/`) | Built, live Atlas verification pending. See [BACKEND.md](BACKEND.md). |
| Presenter service (`demo/presenter.py`) | Built for a scripted agent path. Embedded terminal not yet. |
| ResNet benchmark, MCP server, weights routes | Not started. |
| Web UI | Mockup only. |
| Governance (correct, expire, history) | Built in the backend. Not on the demo path yet (Phase 2). |

Current status and owners: [TASKS.md](TASKS.md).

## Look at it

- **Clickable mockup:** open [docs/demo/index.html](docs/demo/index.html) in a browser. One screen, four stages, simulated terminal and numbers. All numbers are illustrative until measured on the GPU PC.
- **Pitch deck:** [docs/deck/precedent-deck.pptx](docs/deck/precedent-deck.pptx), 12 slides with speaker notes. Statistics on slide 2 are cited on the slide. Numbers elsewhere are illustrative.

## Read in this order

| File | What it is |
| --- | --- |
| [REQUIREMENTS.md](REQUIREMENTS.md) | The agreed MVP in plain words, requirements, interface, scope and decisions. |
| [PLATFORM.md](PLATFORM.md) | The contract: results, routes, Atlas storage, benchmark, Claude Code integration, UI, credits. |
| [BACKEND.md](BACKEND.md) | How to run and verify the Atlas backend and the presenter. |
| [TASKS.md](TASKS.md) | Owners, gates, time plan and demo script. |
| [HARNESS.md](HARNESS.md) | The order of integration and the evidence the demo must show. |
| [HUMANS.md](HUMANS.md) | How a reviewer checks the claims. |
| [BRIEF.md](BRIEF.md) | The event rules, judging criteria and upstream references. |
| [AGENTS.md](AGENTS.md) | Rules for teammates and their coding assistants. |

## Start a task

Open the checkout, claim a task on the [team board](TASKS.md), substitute your task ID, and paste this into your assistant.

> Read AGENTS.md, REQUIREMENTS.md, PLATFORM.md, and TASKS.md. I own TASK_ID. Implement its acceptance check through the real platform interface, verify the result, and add a handoff to TASKS.md with the command and observed outcome. Coordinate shared interface changes with the affected owners.

## Credits

Ideas from ARA and AutoSci (no code used), PyTorch and torchvision as libraries. See [NOTICE.md](NOTICE.md).
