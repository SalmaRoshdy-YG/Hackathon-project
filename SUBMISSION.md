# Precedent demo and submission

## One-minute voice-over for the W3 recording

| Time | On screen | Voice-over |
| --- | --- | --- |
| 0–13s | Real workbench, past experiments, Codex terminal | “Precedent gives research agents access to experiments other agents have already run. Here, Codex has one four-epoch attempt to get ResNet-50 above eighty percent on unseen handwritten digits.” |
| 13–21s | Pending plan and Reject | “Codex found a checkpoint for sixty-four-pixel images and skipped a learning rate that had already missed the target. A person reviews the plan. Rejecting it leaves no run.” |
| 21–35s | Approved plan and aborted browser run | “We approved a separate proposal. Atlas recorded the approval, but this rehearsal's browser run aborted before it could publish a new finding.” |
| 35–60s | Measured comparison from the rehearsal receipts | “We downloaded the exact checkpoint Codex selected, verified its hash, and replayed the job locally. On the same two hundred forty images, training from scratch got nineteen right. Using the retrieved checkpoint got two hundred sixteen right. That's seven point nine percent versus ninety percent, on the same four-epoch budget.” |

For a clean live recording, keep the same opening. Show **Run plan** at 25–35 seconds, measured scores at 35–50 seconds, then the new finding, checkpoint and repository at 50–60 seconds. Read the scores from that recording's receipts.

## Three-minute live script

| Time | Show | Say |
| --- | --- | --- |
| 0–25s | Past experiments and checkpoint details | “We get one four-epoch run to reach eighty percent. In MongoDB, past findings are stored with their conditions and measurements. The calibration weights are in GridFS.” |
| 25–80s | Codex search and applicability labels | “In MongoDB, Vector Search filters by project, and the lookup checks which result versions are current and usable. The sixty-four-pixel weights fit, the high learning rate missed the target, and the thirty-two-pixel result belongs to a different task.” |
| 80–110s | Reject one plan, then approve a fresh proposal | “In MongoDB, a conditional update records the decision. Reject leaves no run. Run plan authorizes one dispatch.” |
| 110–160s | Training, comparison, new finding | “In MongoDB, GridFS streams the cited checkpoint. After training, the platform saves the new weights and publishes the measured result for the next agent.” Read the measured scores and show the new row. |
| 160–180s | Second project search | “The same question from a second, unseeded project returns none of the first project's results.” Show the live query or identify the prior isolation check. |

Use the [rehearsal fallbacks](rehearsal/README.md#fallbacks) if the live gates fail.

## Submission checklist

- [ ] The repository opens signed out. W5 confirmed the repository is private, and an anonymous Git fetch failed on November 14.
- [x] W5 scanned 224 reachable blobs and 59 tracked paths for secret patterns and exact local credential values. Only example Atlas URIs matched. Recheck after further changes before making the repository public.
- [x] Rehearsal used the configured event Atlas Sandbox. Search index reported READY and Codex retrieved live results over MCP.
- [ ] Complete three clean live rehearsals, with each successful run under three minutes.
- [ ] Upload the final voice-over cut and open it signed out.
- [ ] List all team members on the submission and verify the final links.
- [ ] Confirm the public README distinguishes event-built work from upstream credits in NOTICE.md.
