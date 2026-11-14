"""Verify the core service with only platform_api available on its import path."""
from datetime import timedelta
from hashlib import sha256
from platform import python_version
from pathlib import Path
from shutil import copytree
from tempfile import TemporaryDirectory

from demo.common import client
from demo.harness import fixture, wait_for
from platform_api.client import require
from platform_api.config import utcnow


def main():
    out = Path("receipts/standalone").resolve()
    with TemporaryDirectory() as directory:
        copytree(Path(__file__).resolve().parents[1] / "platform_api", Path(directory) / "platform_api")
        with fixture(out, "standalone", profile=None, cwd=directory), \
                client("publisher") as publisher, client("reader") as reader, client("maintainer") as maintainer:
            conditions = {"fixture_revision": "service-check-v1", "sample_size": 8}
            payload = {
                "schema_version": 1, "hypothesis": "A short range contains eight whole numbers",
                "fixture_revision": conditions["fixture_revision"], "conditions": {"sample_size": 8},
                "configuration": {"method": "count"},
                "metric": {"name": "count", "value": len(range(8)), "unit": "rows", "operator": "==", "threshold": 8},
                "execution": "completed", "validity": "valid", "direction": "positive",
                "evidence": {"kind": "job_receipt", "data": {"run_id": "standalone-count",
                    "reproduce": {"command": "python -c \"print(len(range(8)))\"",
                                  "fixture_sha256": sha256(bytes(range(8))).hexdigest(),
                                  "versions": {"python": python_version()}}}},
                "source": {"system": "platform-check", "source_agent": "agent-a", "record": "standalone-count"},
                "expires_at": (utcnow() + timedelta(minutes=10)).isoformat(),
            }
            ref = require(publisher.post("/v1/results", json=payload))

            def search():
                return require(reader.post("/v1/search", json={
                    "question": payload["hypothesis"], "conditions": conditions}))["candidates"]

            matches = wait_for(search, bool, "standalone result indexed")
            assert matches[0]["result"]["result_id"] == ref["result_id"]
            assert matches[0]["applicability"] == {"status": "applies", "mismatches": []}
            proposal = reader.post("/v1/decisions", json={
                "request": payload["hypothesis"], "memory": "off", "conditions": conditions,
                "job_id": "count", "used_refs": [], "skipped_jobs": [], "rejected_candidates": [],
                "candidates": [], "reason": "Measure the baseline", "model": "test"})
            assert proposal.status_code == 409 and proposal.json()["detail"] == "experiment_runner_not_configured"
            route = f"/v1/results/{ref['result_id']}"
            assert require(reader.get(route+"/evidence"))["evidence"] == payload["evidence"]
            require(maintainer.post(route+"/expire", json={"expected_version": 1, "reason": "Check expiry"}))
            assert search() == []
            assert reader.get(route+"/evidence").status_code == 404
            assert require(reader.get(route+"/history"))["status"] == "expired"
    print("Standalone Atlas API passed without demo or benchmark packages.")


if __name__ == "__main__":
    main()
