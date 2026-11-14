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

Set `OPENAI_API_KEY`, `MEMORY_ATLAS_URI`, and `MEMORY_ATLAS_DB` in your shell. Point Atlas at the event Sandbox using a demo database where you can create a collection and a Vector Search index. The default planner is `gpt-4.1-mini-2025-04-14`. Leave the model and training seed fixed across the pair.

```powershell
python demo.py seed
python demo.py off --out receipts/off.json
python demo.py on --out receipts/on.json
```

Run `seed` once before judging. Atlas may take a few minutes to make the index queryable. If `on` reports that the index is still building or returns no evidence, retry once the index has caught up.

Each agent call sees only [the task](AGENT-TASK.md) and a list of retrieved experiment records. It starts without conversation history and has no filesystem, shell, or browsing tools. In `off` the evidence list is empty. In `on` it contains the results of Atlas Vector Search. The runner executes exactly the selected job on CPU. Each receipt includes the exact agent input, decision, evidence IDs, and measured score.

For judges, put the two decisions and scores side by side. If the agent chooses the same job twice, report that result and show whether the Atlas evidence informed its reasoning. A difference in measured accuracy between the two training configurations alone establishes only the training effect. A change in the chosen job is the additional behavior the paired run checks.

The seed summarizes Table 2 of the ResNet paper as extracted in the pinned ARA example. The old experiment used ImageNet. The new experiment checks whether its idea helps on handwritten digits under a small training budget. [Pinned ARA evidence](https://github.com/ARA-Labs/Agent-Native-Research-Artifact/blob/e52a925e9d03b4ada3008653e72f99b04116fca2/examples/resnet-ara-example/evidence/tables/table2_imagenet_plain_vs_residual.md)
