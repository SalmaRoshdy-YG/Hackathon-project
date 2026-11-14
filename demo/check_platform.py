"""Check the live Atlas API, search isolation, lifecycle, and stale index candidates."""
import argparse
from datetime import timedelta
from pathlib import Path
from time import monotonic

from platform_api.client import require, save
from tests.lookup_profile import QUESTION, TASK, finding, replacement, run
from demo.common import client, run_agent
from demo.harness import fixture, wait_for
from platform_api.config import utcnow
from platform_api.embedding import DIMENSIONS, embed, index_name, model


def path(ref_, suffix=""):
    return f"/v1/results/{ref_['result_id']}{suffix}"


def search(api):
    return require(api.post("/v1/search", json={"question": QUESTION, "conditions": TASK}))["candidates"]


def ref(row):
    result = row["result"]
    return {"result_id": result["result_id"], "version": result["version"]}


def has(rows, target):
    return any(ref(r) == target for r in rows)


def audit(store, project):
    checks = {}
    assert store.client.admin.command("ping")["ok"] == 1
    vector = embed(QUESTION, query=True)
    assert len(vector) == DIMENSIONS
    checks["ping_and_embedding"] = {"model": model(), "dimensions": len(vector), "index": index_name()}
    for coll in ("results", "result_vectors", "result_versions"):
        assert store.db[coll].index_information()["purge_at_1"]["expireAfterSeconds"] == 0
    checks["ttl_indexes"] = True

    def raw_index_has(target):
        # Test-only probe bypasses the head join to prove the old vector is really searchable.
        stage = store.search_pipeline(project, vector, None)[0]
        return any(row["result_id"] == target["result_id"] and row["version"] == target["version"]
                   for row in store.db.result_vectors.aggregate([stage, {"$project": {
                       "result_id": 1, "version": 1}}]))
    payload = finding(run("binary", {**TASK, "phase": "calibration"}))
    with client("publisher") as a, client("reader") as b, client("maintainer") as human, \
            client("other") as other, client("other_publisher") as other_a:
        assert require(b.get("/v1/health"))["index"] == "READY"
        started = monotonic()
        with store.db.results.watch([{"$match": {"fullDocument.project_id": project}}],
                                    full_document="updateLookup", max_await_time_ms=350) as stream:
            own = require(a.post("/v1/results", json=payload))
            hit = wait_for(stream.try_next, lambda e: bool(e), "own publish change stream")
            assert hit["fullDocument"]["_id"] == own["result_id"]
        checks["change_stream"] = {"operation": hit["operationType"],
                                   "publish_round_trip_ms": round((monotonic()-started)*1000)}
        foreign = require(other_a.post("/v1/results", json=payload))
        own_rows = wait_for(lambda: search(b), lambda rows: has(rows, own), "own sentinel")
        foreign_rows = wait_for(lambda: search(other), lambda rows: has(rows, foreign), "other sentinel")
        assert not has(own_rows, foreign) and not has(foreign_rows, own)
        checks["filtered_vector_search"] = {"own_hits": len(own_rows), "other_hits": len(foreign_rows)}

        for end in ("", "/evidence", "/history"):
            assert other.get(path(own, end)).status_code == 404
            assert b.get(path(foreign, end)).status_code == 404
        edit = {"expected_version": 1, "reason": "Receipt used different sort order", "replacement": replacement()}
        assert other_a.post(path(own, "/correct"), json=edit).status_code == 404
        assert b.post(path(own, "/correct"), json=edit).status_code == 403
        assert b.post("/v1/results", json=payload).status_code == 403
        assert b.post("/v1/results", json={**payload, "project_id": project}).status_code == 422
        assert other.post("/v1/resolve", json={"refs": [own]}).status_code == 404
        decision = run_agent("tests.lookup_profile", "MEMORY_READER_TOKEN", "--memory", "on")
        did = f"/v1/decisions/{decision['decision_id']}"
        assert other.get(did).status_code == 404
        assert other.post(did+"/approve", json={}).status_code == 404
        assert b.post(did+"/approve", json={}).status_code == 403
        assert b.post(did+"/receipt", json={}).status_code == 409
        require(human.post(did+"/approve", json={"note": "Preflight approval"}))
        assert human.post(did+"/approve", json={}).status_code == 409
        checks["access_controls_and_approval"] = True

        v2 = require(human.post(path(own, "/correct"), json=edit))
        assert v2["version"] == 2 and human.post(path(own, "/correct"), json=edit).status_code == 409
        assert b.get(path(own), params={"version": 1}).status_code == 404
        assert b.get(path(own, "/evidence"), params={"version": 1}).status_code == 404
        assert b.post("/v1/resolve", json={"refs": [own]}).status_code == 404
        assert require(b.post("/v1/resolve", json={"refs": [v2]}))["results"][0]["version"] == 2
        history = require(b.get(path(own, "/history")))
        assert [v["state"] for v in history["versions"]] == ["superseded", "current"]
        assert history["events"][-1]["reason"] == edit["reason"]
        assert history["versions"][0]["replaced_by"] == "presenter"
        assert store.db.result_vectors.count_documents({"project_id": project, "result_id": own["result_id"],
                                                       "version": 1}) == 1
        fresh = wait_for(lambda: search(b), lambda rows: has(rows, v2), "corrected version indexed")
        assert raw_index_has(own) and not has(fresh, own)
        assert next(x["applicability"]["mismatches"] for x in fresh if ref(x) == v2) == [
            {"field": "layout", "wanted": "sorted", "found": "different-sort"}]
        empty = []
        mismatched = next(row for row in fresh if ref(row) == v2)
        invalid = {"request": "Prove mismatched evidence cannot authorize a job", "memory": "on",
                   "conditions": TASK, "job_id": "linear", "used_refs": [v2],
                   "candidates": [{"ref": v2, "score": mismatched["score"],
                                   "applicability": mismatched["applicability"]}],
                   "skipped_jobs": empty, "rejected_candidates": empty, "reason": "Negative check", "model": "test"}
        assert b.post("/v1/decisions", json=invalid).status_code == 422
        aborted = require(b.post(did+"/execute"))
        assert aborted["status"] == "aborted" and "receipt" not in aborted
        assert b.post(did+"/execute").status_code == 409
        checks["transaction_corrects_and_revokes_approved_decision"] = True
        checks["stale_hit_present_in_index_rejected_by_authoritative_lookup"] = True

        def expired_checks(target):
            assert raw_index_has(target) and not has(search(b), target)
            assert b.get(path(target)).status_code == 404
            assert b.get(path(target, "/evidence")).status_code == 404
            assert b.post("/v1/resolve", json={"refs": [target]}).status_code == 404
            assert require(b.get(path(target, "/history")))["status"] == "expired"
            assert any(item["result_id"] == target["result_id"] and item["status"] == "expired"
                       for item in require(b.get("/v1/results"))["items"])
            head = store.db.results.find_one({"_id": target["result_id"], "project_id": project})
            assert head["purge_at"] > utcnow()
            assert store.db.result_vectors.count_documents({"project_id": project,
                "result_id": target["result_id"], "version": target["version"]}) == 1

        require(human.post(path(v2, "/expire"), json={"expected_version": 2, "reason": "Retired by owner"}))
        expired_checks(v2)
        scheduled = require(a.post("/v1/results", json={**payload,
            "expires_at": (utcnow()+timedelta(seconds=7)).isoformat()}))
        wait_for(lambda: search(b), lambda rows: has(rows, scheduled), "scheduled finding indexed", seconds=6)
        wait_for(lambda: b.get(path(scheduled)).status_code, lambda code: code == 404, "scheduled expiry", seconds=12)
        expired_checks(scheduled)
        checks["manual_and_scheduled_expiry_before_ttl"] = True
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="receipts/preflight")
    args = parser.parse_args()
    with fixture(args.out, "preflight", profile="tests.lookup_profile") as (store, project):
        save(audit(store, project), Path(args.out)/"summary.json")


if __name__ == "__main__":
    main()
