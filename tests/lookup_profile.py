"""A second experiment for the Atlas contract test: searching an ordered table."""
import argparse
from datetime import timedelta
from hashlib import sha256
from platform import python_version

from platform_api.client import connect, require, save
from platform_api.config import utcnow
from demo.profile import Presentation
from platform_api.profile import Experiment

TASK = {"fixture_revision": "ordered-table-v1", "layout": "sorted", "size": 128, "phase": "holdout"}
QUESTION = "How can we find a stored customer ID with fewer comparisons?"
CATALOG = ("linear", "binary", "reverse")


def run(job, conditions):
    size = conditions["size"]
    target = size - (7 if conditions["phase"] == "holdout" else 13)
    rows = list(range(size))
    probes = 0
    found = False
    if job == "binary":
        low, high = 0, size
        while low < high:
            middle = (low + high) // 2
            probes += 1
            if rows[middle] == target:
                found = True
                break
            if rows[middle] < target:
                low = middle + 1
            else:
                high = middle
    else:
        for value in rows:
            if job == "reverse":
                value = rows[size - 1 - value]
            probes += 1
            if value == target:
                found = True
                break
    assert found
    return {"run_id": f"{job}-{conditions['layout']}-{target}",
            "fixture_revision": conditions["fixture_revision"],
            "conditions": {k: v for k, v in conditions.items() if k != "fixture_revision"},
            "configuration": {"job_id": job, "target": target},
            "execution": "completed", "validity": "valid",
            "direction": "positive" if probes <= 8 else "negative",
            "metric": {"name": "comparisons", "value": probes, "unit": "probes", "operator": "<=", "threshold": 8},
            "reproduce": {"command": f"python -m tests.lookup_profile measure {job} {conditions['layout']} {conditions['phase']}",
                          "fixture_sha256": sha256(bytes(rows)).hexdigest(),
                          "versions": {"python": python_version()}}}


def finding(receipt):
    return {"schema_version": 1, "hypothesis": "Binary search lowers probes to locate a row by identifier",
            **{k: receipt[k] for k in ("fixture_revision", "conditions", "configuration", "metric",
                                       "execution", "validity", "direction")},
            "evidence": {"kind": "job_receipt", "data": receipt},
            "source": {"system": "ordered-table-test", "source_agent": "agent-a", "record": receipt["run_id"]},
            "expires_at": (utcnow() + timedelta(hours=2)).isoformat()}


def validate_task(conditions):
    return conditions == TASK


def supports(job, result):
    return result["metric"]["name"] == "comparisons" and result["configuration"]["job_id"] == job


def replacement():
    return finding(run("binary", {**TASK, "phase": "calibration", "layout": "different-sort"}))


def produce():
    calibration = {**TASK, "phase": "calibration"}
    docs = {"support": finding(run("binary", calibration)),
            "failed": finding(run("reverse", calibration))}
    with connect() as api:
        refs = {name: require(api.post("/v1/results", json=body)) for name, body in docs.items()}
    return {"refs": refs, "receipts": {name: body["evidence"]["data"] for name, body in docs.items()}}


def agent(memory):
    with connect() as api:
        rows = (require(api.post("/v1/search", json={"question": QUESTION, "conditions": TASK}))["candidates"]
                if memory == "on" else [])
        candidates, failures, rejected, support = [], [], [], []
        for row in rows:
            result = row["result"]
            ref = {key: result[key] for key in ("result_id", "version")}
            row["evidence"] = require(api.get(f"/v1/results/{ref['result_id']}/evidence",
                                             params={"version": ref["version"]}))["evidence"]
            label = row["applicability"]
            candidates.append({"ref": ref, "score": row["score"], "applicability": label})
            if label["status"] == "mismatch":
                rejected.append({"ref": ref, "reason": "Conditions differ"})
            elif result["direction"] == "positive":
                support.append(ref)
            elif result["configuration"]["job_id"] == "reverse":
                failures.append(ref)
        selected = "binary" if support else "linear"
        proposal = {"request": QUESTION, "memory": memory, "conditions": TASK, "candidates": candidates,
                    "job_id": selected, "used_refs": support, "rejected_candidates": rejected,
                    "skipped_jobs": [{"job_id": "reverse", "refs": failures,
                                      "reason": "Matched failure" if failures else "No supporting evidence"}],
                    "reason": "Select the supported search method or the baseline", "model": "lookup-rules-v1"}
        return {**require(api.post("/v1/decisions", json=proposal)), "evidence_candidates": rows}


EXPERIMENT = Experiment("ordered-lookup-v1", CATALOG, "linear", ("fixture_revision", "layout", "size"),
                        validate_task, supports, run)
PRESENTATION = Presentation(QUESTION, TASK, "tests.lookup_producer", "tests.lookup_profile", replacement,
                            lambda: {"planner": "lookup-rules-v1"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", choices=["measure"])
    parser.add_argument("job", nargs="?", choices=CATALOG)
    parser.add_argument("layout", nargs="?")
    parser.add_argument("phase", nargs="?")
    parser.add_argument("--memory", choices=["on", "off"])
    args = parser.parse_args()
    if args.command == "measure":
        save(run(args.job, {**TASK, "layout": args.layout, "phase": args.phase}))
    else:
        save(agent(args.memory))
