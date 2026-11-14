# Improve handwritten-digit recognition

You have one training run. Choose the configuration you expect to correctly label the most unseen handwritten digits. Both configurations use the same data, network width and depth, optimizer, and 15-epoch budget.

- `plain` sends each block's output directly to the next block.
- `shortcut` adds each block's input back to its output before passing it to the next block. This adds no trainable parameters.

Use retrieved experiments as evidence when they apply. Explain why your choice could help on this task. Cite only IDs from the evidence supplied for this decision. If no evidence applies, use your judgment and return an empty citation list.
