# Can an AI agent learn from an old experiment?

Give the agent one chance to improve handwritten-digit recognition. Run it twice on the same task and show how many of the same 450 unseen images each chosen model gets right.

## Rehearse locally

From this folder, install the dependencies in a virtual environment, then run the CPU probe.

```powershell
python -m pip install -r requirements.txt
python demo.py probe
```

The probe trains both configurations directly and needs no Atlas or OpenAI credentials. Training uses the digit images bundled with scikit-learn. The models differ only in whether information can skip layers. Compare `correct` out of `total`.

## Run the agent with memory off and on

Use your normal Codex or Claude Code sign-in. The demo requires no model API key. Set `MEMORY_ATLAS_URI` and `MEMORY_ATLAS_DB` in the terminal for the seed and memory-on commands. Point Atlas at the event Sandbox using a demo database where you can create a collection and a Vector Search index.

Before judging, the operator prepares a private JSON file with four string fields `id`, `source`, `dataset`, and `finding`. Keep it outside the checkout and the agents' workspace. Give write credentials only to the operator. Run this once from the operator's terminal.

```powershell
python demo.py seed --seed-file "$env:LOCALAPPDATA/HackathonJudgeDemo/seed.json"
```

The first run downloads a public embedding model and computes vectors locally on CPU. Atlas may take a few minutes to make the index queryable.

```powershell
python demo.py off --out receipts/off.json
python demo.py on --out receipts/on.json
```

Run those commands in the operator's terminal. For each run, paste only the printed prompt into a fresh Codex or Claude Code session in an empty folder. Use the same app and model for both runs. Keep the repo, Atlas credentials, seed file, and receipts out of those sessions. The manual handoff does not disable the app's tools, so discard the run if the agent uses tools. Paste its one-line JSON answer back into the waiting terminal. The runner validates the answer and trains only the selected configuration on CPU.

The prompt contains [the same task](AGENT-TASK.md) both times. In `off` the evidence list is empty. In `on` it contains the results of Atlas Vector Search. Each receipt records the exact prompt, decision, evidence IDs, and measured score.

For judges, put the two decisions and scores side by side. If the agent chooses the same job twice, report that result and show whether the Atlas evidence informed its reasoning. A difference in measured accuracy between the two training configurations alone establishes only the training effect. A change in the chosen job is the additional behavior the paired run checks.
