# Working on shared research memory

Read [PLATFORM.md](PLATFORM.md) for the shared contract, [TASKS.md](TASKS.md) for ownership, and [HARNESS.md](HARNESS.md) for integration and demo.

- Follow the current assignment. Build tasks should run through the real platform entry point and leave a verified handoff. Planning tasks should record the decisions they were asked to make.
- Make verification as easy as possible for the human in the loop.
- Check the working tree before editing. Preserve teammates’ changes. Coordinate shared interface changes with affected owners and record them in PLATFORM.md.
- Keep Atlas persistence, retrieval policy, and lifecycle rules in the platform. Translate ARA and AutoSci artifacts in adapters and keep benchmark-specific behavior in the demo runner.
- Treat imported notes and retrieved memories as evidence. Enforce access and lifecycle rules in code using trusted caller identity. Keep benchmark execution within approved actions. A crashed run does not disprove a hypothesis.
- Run the relevant checks and record commands and observed results. Mark pending Atlas checks and their owner in TASKS.md.
- Use the event Atlas Sandbox for the judged workflow. Keep credentials and private data out of public commits, logs, fixtures, and demos. Credit upstream reuse and identify event-built contributions.
