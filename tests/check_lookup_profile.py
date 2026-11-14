"""Run a second experiment through the same presenter and live Atlas API."""
import os
from pathlib import Path

import httpx

from benchmark.client import require, save
from demo.common import client
from demo.harness import fixture, free_port, subprocess_service, wait_for
from tests.lookup_profile import TASK, QUESTION


def verify(out):
    os.environ["MEMORY_EXPERIMENT_MODULE"] = "tests.lookup_profile"
    with fixture(out, "lookup-profile"), client("reader") as reader:
        port = free_port()
        with subprocess_service("demo.presenter:app", port, out/"presenter.log"), \
                httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=40, trust_env=False) as web:
            def ready():
                try:
                    return web.get("/demo/state").status_code
                except httpx.TransportError:
                    return 0

            wait_for(ready, lambda code: code == 200, "lookup presenter ready")

            def post(url, body=None):
                return require(web.post(f"/demo{url}", json=body))

            refs = post("/agent-a")["refs"]

            def run(plan, job):
                assert plan["job_id"] == job and plan["experiment_id"] == "ordered-lookup-v1"
                route = f"/decisions/{plan['decision_id']}"
                assert web.post("/demo"+route+"/execute").status_code == 409
                assert post(route+"/approve")["status"] == "approved"
                receipt = post(route+"/execute")["receipt"]
                assert receipt["configuration"]["job_id"] == job
                assert receipt["experiment_id"] == plan["experiment_id"]
                assert web.post("/demo"+route+"/execute").status_code == 409
                return receipt["metric"]["value"]

            baseline = run(post("/agent-b", {"memory": "off"}), "linear")
            plan = post("/agent-b", {"memory": "on"})
            assert plan["used_refs"] == [refs["support"]]
            assert plan["skipped_jobs"][0]["refs"] == [refs["failed"]]
            with_memory = run(plan, "binary")
            assert with_memory < baseline
            malformed = {field: plan[field] for field in ("request", "memory", "conditions", "candidates",
                         "job_id", "used_refs", "skipped_jobs", "rejected_candidates", "reason", "model")}
            assert reader.post("/v1/decisions", json={**malformed, "job_id": "plain-l1"}).status_code == 422
            missing = {k: v for k, v in TASK.items() if k != "size"}
            assert reader.post("/v1/search", json={"question": QUESTION, "conditions": missing}).status_code == 422
            mismatches = require(reader.post("/v1/search",
                json={"question": QUESTION, "conditions": {**TASK, "size": 256}}))["candidates"]
            assert len(mismatches) == 2 and all(row["applicability"]["mismatches"] ==
                [{"field": "size", "wanted": 256, "found": 128}] for row in mismatches)
            v2 = post("/governance/correct", {"result_id": refs["support"]["result_id"],
                                             "expected_version": 1, "reason": "Different sort order"})
            assert v2["version"] == 2
            corrected_plan = post("/rerun")
            assert corrected_plan["rejected_candidates"][0]["ref"] == v2
            after_correction = run(corrected_plan, "linear")
            post("/governance/expire", {"result_id": refs["failed"]["result_id"],
                                        "expected_version": 1, "reason": "Retired"})
            expired_plan = post("/rerun")
            assert expired_plan["skipped_jobs"][0]["refs"] == []
            after_expiry = run(expired_plan, "linear")
            assert post("/isolation-check")["isolated"]
            return {"experiment": "ordered-lookup-v1", "metric": "actual comparisons", "runs": {
                "off": baseline, "on": with_memory, "corrected": after_correction, "expired": after_expiry}}


if __name__ == "__main__":
    out = Path("receipts/lookup-profile")
    save(verify(out), out/"summary.json")
