import argparse
import json
import os
import sys
from pathlib import Path

from train import train_digits


TASK = Path(__file__).with_name("AGENT-TASK.md")


def read_decision(evidence):
    decision = json.loads(input("Paste the agent's one-line JSON decision and press Enter: "))
    if not isinstance(decision, dict) or decision.keys() != {"job", "reason", "citations"}:
        raise ValueError("Expected a JSON object with job, reason, and citations.")
    if decision["job"] not in ("plain", "shortcut"):
        raise ValueError("The job must be plain or shortcut.")
    if not isinstance(decision["reason"], str) or not decision["reason"].strip():
        raise ValueError("The decision must include a reason.")
    citations = decision["citations"]
    if not isinstance(citations, list) or any(not isinstance(item, str) for item in citations):
        raise ValueError("Citations must be a JSON array of evidence IDs.")
    if set(citations) - {record["id"] for record in evidence}:
        raise ValueError("The agent cited evidence it was not given.")
    return decision


def main():
    parser = argparse.ArgumentParser(description="Run the handwritten-digit experiment.")
    parser.add_argument("command", choices=["probe", "seed", "off", "on"])
    parser.add_argument("--seed", type=int, default=1, help="Training random seed")
    parser.add_argument("--seed-file", type=Path, help="Private operator JSON for the seed command")
    parser.add_argument("--out", type=Path, help="Save the JSON receipt")
    args = parser.parse_args()
    if (args.command == "seed") != (args.seed_file is not None):
        parser.error("Use --seed-file only with the seed command. The seed command requires it.")

    if args.command in ("on", "seed"):
        required = ["MEMORY_ATLAS_URI", "MEMORY_ATLAS_DB"]
        missing = [name for name in required if not os.environ.get(name)]
        if missing:
            parser.error("Set " + ", ".join(missing) + " before running " + args.command)
        from memory_store import retrieve, seed_memory

    if args.command == "probe":
        result = [train_digits(job, args.seed) for job in ("plain", "shortcut")]
    elif args.command == "seed":
        result = seed_memory(args.seed_file)
    else:
        evidence = retrieve() if args.command == "on" else []
        prompt = (
            TASK.read_text(encoding="utf-8").rstrip()
            + "\n\nRetrieved experiment records\n\n"
            + json.dumps(evidence, indent=2)
        )
        print("\nPaste the text between the lines into a fresh Codex or Claude Code session.\n")
        print(f"-----\n{prompt}\n-----\n")
        decision = read_decision(evidence)
        result = {
            "memory": args.command,
            "agent_input": prompt,
            "decision": decision,
            "measurement": train_digits(decision["job"], args.seed),
        }

    output = json.dumps(result, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    try:
        main()
    except (EOFError, OSError, RuntimeError, ValueError) as error:
        sys.exit(str(error) or "No decision received.")
