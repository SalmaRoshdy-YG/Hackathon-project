import argparse
import json
import os
import sys
from pathlib import Path

from train import train_digits


TASK = Path(__file__).with_name("AGENT-TASK.md")
DEFAULT_MODEL = "gpt-4.1-mini-2025-04-14"
DECISION_FORMAT = {
    "type": "json_schema",
    "name": "training_decision",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "job": {"type": "string", "enum": ["plain", "shortcut"]},
            "reason": {"type": "string"},
            "citations": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["job", "reason", "citations"],
        "additionalProperties": False,
    },
}


def run_agent(client, model, evidence, seed):
    prompt = {
        "task": TASK.read_text(encoding="utf-8"),
        "retrieved_evidence": evidence,
    }
    response = client.responses.create(
        model=model,
        input=json.dumps(prompt),
        tools=[],
        store=False,
        temperature=0,
        max_output_tokens=400,
        text={"format": DECISION_FORMAT},
    )
    if response.status != "completed" or not response.output_text:
        raise RuntimeError("The model did not return a complete decision.")
    decision = json.loads(response.output_text)
    if set(decision["citations"]) - {record["id"] for record in evidence}:
        raise RuntimeError("The model cited evidence it was not given.")
    return {
        "model": response.model,
        "agent_input": prompt,
        "decision": decision,
        "measurement": train_digits(decision["job"], seed),
    }


def main():
    parser = argparse.ArgumentParser(description="Run the handwritten-digit experiment.")
    parser.add_argument("command", choices=["probe", "seed", "off", "on"])
    parser.add_argument("--seed", type=int, default=1, help="Training random seed")
    parser.add_argument("--out", type=Path, help="Save the JSON receipt")
    args = parser.parse_args()

    if args.command == "probe":
        result = [train_digits(job, args.seed) for job in ("plain", "shortcut")]
    else:
        required = ["OPENAI_API_KEY"]
        if args.command in ("on", "seed"):
            required.extend(["MEMORY_ATLAS_URI", "MEMORY_ATLAS_DB"])
        missing = [name for name in required if not os.environ.get(name)]
        if missing:
            parser.error("Set " + ", ".join(missing) + " before running " + args.command)

        from openai import OpenAI

        with OpenAI(timeout=30) as client:
            if args.command in ("on", "seed"):
                from memory_store import retrieve, seed_memory
            if args.command == "seed":
                result = seed_memory(client)
            else:
                evidence = retrieve(client) if args.command == "on" else []
                result = run_agent(
                    client, os.environ.get("DEMO_MODEL", DEFAULT_MODEL), evidence, args.seed
                )
                result["memory"] = args.command

    output = json.dumps(result, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as error:
        sys.exit(str(error))
