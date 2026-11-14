# Human review guide

Start with one question. **Did Claude Code use another agent's measured result and stored weights to choose a different experiment, which a person confirmed, which then really trained and did better?** Follow the plan back to the exact version of each result it cited. Check that the conditions match and that the platform, not the agent, enforces who can read what.

## Where to read

| File | What to look for |
| --- | --- |
| [README.md](README.md) | The project, the demo, and what is built. |
| [REQUIREMENTS.md](REQUIREMENTS.md) | The MVP requirements R1–R11, the interface, scope and the decisions log. |
| [PLATFORM.md](PLATFORM.md) | The benchmark, API, search pipeline, Claude Code integration, interface and credits. |
| [BACKEND.md](BACKEND.md) | How to run the Atlas backend and its checks. |
| [TASKS.md](TASKS.md) | Owners, gates and their status, and the latest commands and observed results. |
| [HARNESS.md](HARNESS.md) | Integration order and demo evidence. |
| [BRIEF.md](BRIEF.md) | Event rules and judging criteria. |

## What you can verify today

- **Read:** the backend code in `platform_api/`, especially the single search aggregation in `store.py` and the atomic approval in `decisions.py`.
- **Run offline:** `python -m unittest discover -s tests`. It does not touch Atlas.
- **Look:** [docs/demo/index.html](docs/demo/index.html). It is a mockup with simulated numbers and a simulated terminal.
- **Not yet verified:** the live Atlas round trip, the ResNet benchmark, the MCP tools, the embedded terminal and the web UI. Treat a gate as passed only when [TASKS.md](TASKS.md) has a commit, an exact command and an observed result for it.

## How to review a finished build

```sh
python -m pip install -r requirements.txt
python -m platform_api.preflight
python -m demo.check_platform
python -m demo.check_presenter
python -m benchmark.run --job finetune-lr0.01     # needs the GPU PC (target)
```

The first three need the event Atlas Sandbox and local credentials. Ask the platform owner for the environment setup. Keep credentials and private receipts local.

| Claim | What to inspect |
| --- | --- |
| Experiments are stored with evidence | The positive, the valid negative, the Fashion-MNIST mismatch and the crashed run, each with conditions, a receipt and a rerun command. The crash is `crashed / invalid / undetermined` and never appears in search. |
| Claude Code finds them by meaning | A differently worded question returns the ResNet-18 experiments after the seeding agents have exited. The platform labels Fashion-MNIST as not fitting, naming `dataset` and `input_size`. |
| Memory changes a real job | Compare Claude Code on its own (`scratch-lr0.1`, about 71%) with Claude Code and Precedent (`finetune-lr0.01`, about 93%). Request, catalog and one-run budget are identical. The receipt records the exact versions cited and who approved. |
| Humans stay in control | "Not now" leaves no run. "Run it" runs once, even if triggered twice. |
| Access works | A second project's search returns nothing and its direct reads return 404. |
| MongoDB visibly does the work | The Atlas strip shows the real `aggregate`, the conditional approval update and the new insert. Nothing in it is hardcoded. |

Governance (correct, expire, history) exists in the backend and is checked by `demo.check_platform`. It is not part of the live demo yet.

## Record what you saw

Add the task ID, commit, exact command or browser steps, observed outcome and any missing dependency to the task board. For a failed claim, include the smallest reproducible example, the expected behavior and what actually happened.
