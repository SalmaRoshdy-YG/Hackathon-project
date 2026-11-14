# W3 rehearsal

Use the prerequisites and CUDA setup in [BACKEND.md](../BACKEND.md). From the repository root with the event Sandbox configured in the ignored .env, run the following. The capture uses installed Microsoft Edge.

```powershell
npm ci
python -m pip install playwright
python -m playwright install ffmpeg
python -u -m rehearsal.prepare --out receipts/w3/fresh
```

The helper creates a unique project with fresh role identities, records the four-epoch scratch baseline, seeds four records through the same API the demo uses, checks that Atlas indexes exactly the three completed records, and opens the workbench. It prints the loopback URL after verifying health. A new output directory gives the next fresh rehearsal. Each fresh project needs room for two roughly 94 MB input checkpoints and an output checkpoint. Stop both services with Ctrl+C. Use a new namespace to reset the experiment state without deleting another operator's data.

In the browser, check all four past experiments, open the terminal, insert the suggested prompt, and press Enter. Start the timer when you open the terminal. Review the new plan before clicking **Run plan**. Confirm that it cites a 64 px calibration checkpoint and avoids high-lr and the 32 px candidate. Wait for the measured comparison and verify the new experiment appears. Review the Atlas event strip. To rehearse Reject, use **Reject** on a separate proposal and confirm that it ends without a run receipt or new finding.

For a dedicated rehearsal session, Playwright can operate the same UI. Keep other agents off this workbench URL so the capture can attribute the new decision to the session it opened.

```powershell
$url = Get-Content receipts/w3/fresh/url.txt
python -m rehearsal.capture --url $url --out receipts/w3/trial-1
# Add --reject for a separate rejection rehearsal.
```

A passing trial completes within three minutes after prep, proposes reuse, clears 80%, and publishes its finding. Capture footage and receipts remain local under receipts/.

| Trial | Project | Seconds | Codex proposal | Result and new finding |
| --- | --- | ---: | --- | --- |
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

## Fallbacks

- Wrong or unsuitable job. Reject it, verify the decision has no receipt, and start a fresh Codex session. Ask explicitly for applicable 64 px calibration evidence, not prior holdout weights. If needed, use the prior verified W1 run with the label **scripted planner**. W1 timing came from API-driven approvals.
- Embedded terminal unavailable. Leave the browser open and use Codex from an empty directory with the same loopback MCP URL. The W3 rehearsal verified that this produced a pending reuse plan. Review and approve from the browser.

```powershell
$agentDir = New-Item -ItemType Directory (Join-Path $env:TEMP ('precedent-agent-' + [guid]::NewGuid()))
$prompt = 'Use only Precedent MCP. Read experiment_profile, search with its conditions, cite a compatible calibration checkpoint by exact version, explain skipped and mismatched evidence, and submit one plan for browser review.'
$mcpConfig = 'mcp_servers.precedent.url="' + $url + '/mcp"'
codex exec --skip-git-repo-check --sandbox read-only -C $agentDir.FullName -c $mcpConfig -c 'mcp_servers.precedent.default_tools_approval_mode="approve"' $prompt
```

- Atlas unavailable or artifact publication fails. Use the recorded W3 rehearsal and say the browser execution aborted. The local comparison uses the exact SHA-256-verified checkpoint selected by Codex. If the checkpoint can still be downloaded, open the cited experiment in the browser, download that version, and compare its SHA-256 to its metadata before replaying the approved job via `python -m experiments.resnet train reuse holdout receipts/replay.safetensors --checkpoint <downloaded-file>`. Keep the replay separate from the browser receipt. If search is down too, use the archived W1 receipts or the W3 video with the date and run type visible.
