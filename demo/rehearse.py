"""Run the four measured comparisons against a fresh project in real Atlas."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

from platform_api.client import require, save
from benchmark.publish import document, replacement
from benchmark.run import CATALOG, QUESTION, REQUEST, TASK, measure
from demo.common import client, run_agent
from demo.harness import fixture, wait_for
from demo.check_platform import has, path, search


def write(directory, name, value):
    (directory / f"{name}.json").write_text(json.dumps(value, indent=2)+"\n", encoding="utf-8")


def refs(group):
    return [(x["result_id"], x["version"]) for x in group]


def run(out):
    with fixture(out, "rehearsal") as (_, project), client("publisher") as publisher, \
            client("reader") as reader, client("maintainer") as human:
        producer = run_agent("benchmark.publish", "MEMORY_PUBLISHER_TOKEN")
        write(out, "producer", producer)
        promising, negative, distractor, crash = (producer["refs"][k]
            for k in ("promising", "negative", "distractor", "crash"))
        p = producer["receipts"]
        assert [(p[k]["execution"], p[k]["validity"], p[k]["direction"]) for k in p] == [
            ("completed", "valid", "positive"), ("completed", "valid", "negative"),
            ("completed", "valid", "positive"), ("crashed", "invalid", "undetermined")]
        unrelated = []
        payload = document(measure("plain-l1", "A", "calibration"), "promising")
        for title in ["Irrigation schedules in rooftop gardens", "Copper patina under humid exposure",
                      "Migration patterns of spruce grouse", "Earthenware glaze at kiln temperatures",
                      "String tension and harmonics on violins"]:
            # The taxonomy is deliberately distinct, as is the measured scope.
            unrelated.append(require(publisher.post("/v1/results", json={
                **payload, "hypothesis": title, "fixture_revision": "unrelated-control-v1",
                "conditions": {**payload["conditions"], "codec": "unrelated-control"},
            })))
        indexed = wait_for(lambda: search(reader),
            lambda rows: all(has(rows, r) for r in [promising, negative, distractor, *unrelated]),
            "producer and unrelated relevance controls", seconds=35)
        scores = {(d["result"]["result_id"], d["result"]["version"]): d["score"] for d in indexed}
        assert max(scores[k] for k in refs([promising, negative])) > max(scores[k] for k in refs(unrelated))
        assert not has(indexed, crash)
        write(out, "semantic-search", indexed)

        def decision(memory):
            plan = run_agent("benchmark.agent", "MEMORY_READER_TOKEN", "--memory", memory)
            assert plan["conditions"] == TASK and plan["request"] == REQUEST
            assert plan["budget"] == 1 and plan["catalog"] == list(CATALOG)
            assert plan["search_question"] == (QUESTION if memory == "on" else None)
            return plan

        rejected = decision("on")
        reject_path = f"/v1/decisions/{rejected['decision_id']}"
        assert reader.post(reject_path+"/execute").status_code == 409
        refused = require(human.post(reject_path+"/reject", json={"reason": "Rehearsal rejection check"}))
        assert refused["status"] == "rejected" and reader.post(reject_path+"/execute").status_code == 409
        assert "receipt" not in require(reader.get(reject_path))
        write(out, "rejected", refused)

        def approved(label, plan, job, race=False):
            route = f"/v1/decisions/{plan['decision_id']}"
            assert plan["job_id"] == job
            if race:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    statuses = list(pool.map(lambda _: human.post(route+"/approve",
                        json={"note": "rehearsal-auto"}).status_code, range(2)))
                assert sorted(statuses) == [200, 409]
                with ThreadPoolExecutor(max_workers=2) as pool:
                    responses = list(pool.map(lambda _: reader.post(route+"/execute"), range(2)))
                assert sorted(r.status_code for r in responses) == [201, 409]
                done = require(next(r for r in responses if r.status_code == 201))
            else:
                require(human.post(route+"/approve", json={"note": "rehearsal-auto"}))
                done = run_agent("benchmark.execute", "MEMORY_READER_TOKEN", "--decision", plan["decision_id"])
            receipt = done["receipt"]
            assert receipt["roundtrip_ok"] and receipt["approval"]["note"] == "rehearsal-auto"
            assert receipt["configuration"]["job_id"] == job and receipt["input_bytes"] == 928
            assert receipt["conditions"] == {k: v for k, v in TASK.items() if k != "fixture_revision"}
            write(out, label, done)
            return receipt

        off = approved("off", decision("off"), "plain-l1", race=True)
        on_plan = decision("on")
        assert set(refs(on_plan["used_refs"])) == set(refs([promising, negative]))
        assert has(on_plan["evidence_candidates"], distractor)
        assert distractor in [row["ref"] for row in on_plan["rejected_candidates"]]
        assert next(s["refs"] for s in on_plan["skipped_jobs"] if s["job_id"] == "dict-b-l6") == [negative]
        on = approved("on", on_plan, "dict-a-l6")
        assert on["metric"]["value"] < 0.4 < off["metric"]["value"]
        correction = replacement()
        write(out, "replacement-cohort-b", correction["evidence"]["data"])
        v2 = require(human.post(path(promising, "/correct"), json={
            "expected_version": 1, "reason": "Receipt belongs to cohort B", "replacement": correction}))
        wait_for(lambda: search(reader), lambda rows: has(rows, v2), "corrected v2 indexed")
        after = decision("on")
        assert v2 in [row["ref"] for row in after["rejected_candidates"]]
        assert not has(after["evidence_candidates"], promising)
        assert next(s["refs"] for s in after["skipped_jobs"] if s["job_id"] == "dict-b-l6") == [negative]
        corrected = approved("corrected", after, "plain-l1")

        require(human.post(path(negative, "/expire"), json={
            "expected_version": 1, "reason": "Superseded by newer measurements"}))
        after = decision("on")
        assert not has(after["evidence_candidates"], negative)
        assert next(s["refs"] for s in after["skipped_jobs"] if s["job_id"] == "dict-b-l6") == []
        expired = approved("corrected-and-expired", after, "plain-l1")
        assert corrected["output_bytes"] == expired["output_bytes"] == off["output_bytes"]
        return {"project": project, "semantic_ranking": "passed", "atomic_approval_and_execution": "passed",
                "rejected_receipt": None, "input_bytes": 928, "model": on["model"],
                "runs": [{"memory": r["memory"], "job_id": r["configuration"]["job_id"],
                          "output_bytes": r["output_bytes"], "used_refs": r["used_refs"]}
                         for r in (off, on, corrected, expired)]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=Path("receipts/rehearsal"))
    args = p.parse_args()
    save(run(args.out), args.out/"assertions.json")


if __name__ == "__main__":
    main()
