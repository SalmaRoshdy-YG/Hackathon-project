# Human review guide

Start with one question. **Did Codex use another agent's measured result and stored weights to choose a different experiment, which a person confirmed, which then really trained and did better?** Follow the plan back to the exact version of each result it cited. Check that the conditions match and that the platform, not the agent, enforces who can read what.

## Where to read

| File | What to look for |
| --- | --- |
| [README.md](README.md) | The project, the demo, and what is built. |
| [REQUIREMENTS.md](REQUIREMENTS.md) | The MVP requirements R1–R11, the interface, scope and the decisions log. |
| [PLATFORM.md](PLATFORM.md) | The experiment, API, search pipeline, agent integration, interface and credits. |
| [BACKEND.md](BACKEND.md) | How to run the Atlas backend and its checks. |
| [TASKS.md](TASKS.md) | Owners, gates and their status, and the latest commands and observed results. |
| [HARNESS.md](HARNESS.md) | Integration order and demo evidence. |
| [BRIEF.md](BRIEF.md) | Event rules and judging criteria. |

## What you can verify today

- **Read:** the backend code in `platform_api/`, especially the single search aggregation in `store.py` and the atomic approval in `decisions.py`.
- **Run offline:** `python -m unittest discover -s tests`. It does not touch Atlas.
- **Look:** [docs/demo/index.html](docs/demo/index.html), the design mockup (being updated to the real task). The live app is `workbench/`.
- **Reported by a teammate, not re-run by the reviewer:** the live Atlas round trip, the ResNet run (29.2% then 90.4%), the MCP tools and the embedded terminal. Treat a gate as passed only when [TASKS.md](TASKS.md) has a commit, an exact command and an observed result for it.

## How to review a finished build

```sh
python -m pip install -r requirements.txt
python -m platform_api.preflight
python -m tests.check_standalone
python -m experiments.resnet train scratch holdout receipts/baseline.safetensors
```

The preflight and the standalone check need the event Atlas Sandbox and local credentials. Ask the platform owner for the environment setup. Keep credentials and private receipts local.

| Claim | What to inspect |
| --- | --- |
| Experiments are stored with evidence | The positive, the valid negative, the 32 px mismatch and the crashed run (the crash is not seeded yet), each with conditions, a receipt and a rerun command. The crash is `crashed / invalid / undetermined` and never appears in search. |
| Codex finds them by meaning | A differently worded question returns the ResNet-50 digit experiments after the seeding agents have exited. The platform labels the 32 px experiment as not fitting, naming `image_px`. |
| Memory changes a real job | Compare Codex on its own (`scratch`, measured once at 29.2%) with Codex and Precedent (`reuse`, measured once at 90.4%). Request, catalog and one-run budget are identical. The receipt records the exact versions cited and who approved. |
| Humans stay in control | Reject leaves no run. Run plan runs once, even if triggered twice. |
| Access works | A second project's search returns nothing and its direct reads return 404. |
| MongoDB visibly does the work | The Atlas strip shows the real `aggregate`, the conditional approval update and the new insert. Nothing in it is hardcoded. |

Governance (correct, expire, history) exists in the backend and is exercised by the backend checks. It is not part of the live demo yet.

## Record what you saw

Add the task ID, commit, exact command or browser steps, observed outcome and any missing dependency to the task board. For a failed claim, include the smallest reproducible example, the expected behavior and what actually happened.
