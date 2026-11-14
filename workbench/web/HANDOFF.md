# W2 handoff

Branch `w2/workbench-single-screen` from `origin/main` at `5cae1bf`.

The main screen follows the terminal, experiment evidence, plan review and measured result. The Research library and Run comparison open in the details drawer. Plan references are matched by result ID and version. The only workbench API addition is a source and timestamp on existing search events, so a library search cannot replace the agent's evidence and a fresh search can supersede a previous plan's highlights.

## Verification

- Started `python -m uvicorn platform_api.app:app --host 127.0.0.1 --port 8131` and `python -m uvicorn workbench.app:app --host 127.0.0.1 --port 8133` with `MEMORY_EXPERIMENT_MODULE=experiments.resnet`, the documented local environment, and `MEMORY_BASELINE_RECEIPT=receipts/resnet-baseline.json` on the workbench. The workbench used `MEMORY_API_URL=http://127.0.0.1:8131`.
- `python -m platform_api.preflight` passed on event Atlas with a ready index and a 1536-dimensional BGE embedding round trip. `python -m unittest discover -s tests`, `node --check workbench/web/app.js`, and `git diff --check` passed.
- In Chrome, Codex in the embedded terminal used MCP to search and submit a plan. The workspace showed Using, Avoiding, and `image_px 32 ≠ 64` from Atlas data. Reject recorded a conditional `pending → rejected` update, left no receipt, and left the findings count at five.
- Repeated the agent request and used Run plan. Atlas recorded one conditional `pending → approved` update and one execution claim. The event strip showed checkpoint chunks streaming from GridFS. The output GridFS chunk insert failed, and the decision ended as `aborted / runner_failed` without a receipt. MongoDB reported about 483 MB allocated for the database after the attempt, and a checkpoint is about 94 MB. The runner's public status gives no underlying write error.
- Replayed an earlier successful Atlas event stream and its stored receipt in Chrome. The result inserted into the experiment list without a reload, the callout reported the observed GridFS read and insert, and the card showed 29.2% baseline and 90.4% guided against the 80% target. Checked Never offered (crashed) using a recorded rehearsal crash, since the live ResNet project had no crash row.
- At a 390 px viewport the workspace stacked with the terminal open and no horizontal overflow. Opening an experiment with Enter showed its reproduction and checkpoint details. Escape closed the drawer and restored the visible focus outline to the originating row.
- Checked the web sources and the live HTML, JavaScript, state and event-batch responses for the configured bearer tokens and Atlas URI. None were present.

## Pending

- W1 and W3 can repeat the successful live publish and result flow when the Sandbox has room for another output checkpoint. W1 owns the live crash seed. The prior successful run and recorded crash covered those UI paths for W2.
