"""Verify W5 governance against fresh projects on the configured Atlas Sandbox."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from demo.common import client
from demo.harness import fixture, wait_for
from platform_api.client import require
from platform_api.embedding import embed
from tests.lookup_profile import QUESTION, TASK, finding, replacement, run


def expect(response, code, detail):
    assert (response.status_code, response.json().get("detail")) == (code, detail), response.status_code


def race(role, path, body):
    start = Barrier(2)

    def post():
        with client(role) as connection:
            start.wait(timeout=10)
            return connection.post(path, json=body)

    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(lambda _: post(), range(2)))


def verify(store, project, publisher, reader, maintainer, other):
    calibration = finding(run("binary", {**TASK, "phase": "calibration"}))
    contents = b"w5-artifact-control"
    artifact = require(publisher.post("/v1/artifacts", files={"upload": ("check.bin", contents)}))
    support = require(publisher.post("/v1/results", json={**calibration, "artifact": artifact}))
    expires = require(publisher.post("/v1/results", json=calibration))
    mismatch = require(publisher.post("/v1/results", json=replacement()))
    other_ref = require(other.post("/v1/results", json=calibration))
    crash = require(publisher.post("/v1/results", json={
        **calibration, "execution": "crashed", "validity": "invalid", "direction": "undetermined",
        "metric": {**calibration["metric"], "value": None},
        "evidence": {"kind": "job_receipt", "data": {"message": "Synthetic worker crash"}},
    }))
    search = {"question": QUESTION, "conditions": TASK}

    def indexed(connection):
        return require(connection.post("/v1/search", json=search))["candidates"]

    def refs(rows):
        return {(row["result"]["result_id"], row["result"]["version"]) for row in rows}

    def pair(ref):
        return (ref["result_id"], ref["version"])

    # Keep even a crash with a physically indexed vector out of semantic search.
    head = store.db.results.find_one({"_id": crash["result_id"], "project_id": project})
    donor = store.db.result_vectors.find_one({"result_id": support["result_id"], "version": 1})
    crash_key = f"w5-crash-{crash['result_id']}"
    store.db.results.update_one({"_id": head["_id"], "project_id": project}, {"$set": {"search_key": crash_key}})
    store.db.result_vectors.insert_one({**donor, "_id": crash_key, "result_id": head["_id"]})

    def raw_hits():
        stage = store.search_pipeline(project, embed(QUESTION, query=True), None)[0]
        return {row["_id"] for row in store.db.result_vectors.aggregate([stage, {"$project": {"_id": 1}}])}

    controls = {pair(support), pair(expires), pair(mismatch)}
    wait_for(raw_hits, lambda keys: {donor["_id"], crash_key} <= keys, "retained and crash vectors indexed")
    wait_for(lambda: indexed(reader), lambda rows: controls <= refs(rows), "owner search controls")
    assert refs(indexed(reader)) == controls
    assert refs(wait_for(lambda: indexed(other), bool, "other project's own control")) == {pair(other_ref)}

    route = f"/v1/results/{support['result_id']}"
    queries = (route, route + "/evidence?version=1", route + "/artifact?version=1", route + "/history")
    for path in queries:
        assert reader.get(path).status_code == 200
        assert other.get(path).status_code == 404
    assert reader.get(queries[2]).content == contents
    assert other.post("/v1/resolve", json={"refs": [support]}).status_code == 404
    crash_doc = require(reader.get(f"/v1/results/{crash['result_id']}"))
    assert crash_doc["execution"] == "crashed"

    def proposal(ref, row=None):
        return {"request": QUESTION, "memory": "on", "conditions": TASK, "job_id": "binary",
                "used_refs": [ref], "skipped_jobs": [], "rejected_candidates": [],
                "candidates": [{"ref": ref, "score": row["score"] if row else 1,
                                "applicability": row["applicability"] if row else
                                {"status": "applies", "mismatches": []}}],
                "reason": "Test the supported job", "model": "w5-test"}

    matching = {pair(row["result"]): row for row in indexed(reader)}
    for ref in (mismatch, crash):
        response = reader.post("/v1/decisions", json=proposal(ref, matching.get(pair(ref))))
        expect(response, 422, "invalid_decision_evidence")

    good = proposal(support, matching[pair(support)])
    decision = require(reader.post("/v1/decisions", json=good))
    dispatch = f"/v1/decisions/{decision['decision_id']}"
    assert reader.get(dispatch).status_code == 200
    assert other.get(dispatch).status_code == 404
    assert require(other.get("/v1/decisions"))["items"] == []
    expect(reader.post(dispatch + "/execute"), 409, "decision_not_approved")
    approval = race("maintainer", dispatch + "/approve", {"note": "W5 concurrence check"})
    assert sorted(r.status_code for r in approval) == [200, 409]
    executions = race("reader", dispatch + "/execute", None)
    assert sorted(r.status_code for r in executions) == [201, 409]
    executed = next(require(r) for r in executions if r.status_code == 201)
    assert executed["receipt"]["metric"]["value"] == 7

    rejected = require(reader.post("/v1/decisions", json=good))
    rejected_path = f"/v1/decisions/{rejected['decision_id']}"
    assert require(maintainer.post(rejected_path + "/reject", json={"reason": "W5 rejection check"}))["status"] == "rejected"
    expect(reader.post(rejected_path + "/execute"), 409, "decision_not_approved")
    assert "receipt" not in require(reader.get(rejected_path))

    pending = require(reader.post("/v1/decisions", json=good))
    pending_path = f"/v1/decisions/{pending['decision_id']}"
    require(maintainer.post(pending_path + "/approve", json={"note": "Check dispatch revalidation"}))
    expired_key = store.db.result_vectors.find_one({"result_id": expires["result_id"], "version": 1})["_id"]
    corrected = require(maintainer.post(route + "/correct", json={
        "expected_version": 1, "reason": "Check supersession", "replacement": calibration}))
    require(maintainer.post(f"/v1/results/{expires['result_id']}/expire", json={
        "expected_version": 1, "reason": "Check expiry before cleanup"}))
    assert {donor["_id"], expired_key, crash_key} <= raw_hits()
    expected = {pair(corrected), pair(mismatch)}
    rows = wait_for(lambda: indexed(reader), lambda rows: pair(corrected) in refs(rows), "corrected version")
    assert refs(rows) == expected
    for ref in (support, expires, crash):
        assert reader.post("/v1/resolve", json={"refs": [ref]}).status_code == 404
        expect(reader.post("/v1/decisions", json=proposal(ref)), 422, "invalid_decision_evidence")
    assert require(reader.post("/v1/resolve", json={"refs": [corrected]}))["results"][0]["version"] == 2
    aborted = require(reader.post(pending_path + "/execute"))
    assert aborted["status"] == "aborted" and aborted["abort_reason"] == "cited_evidence_no_longer_usable"


def main():
    with fixture(Path("receipts/w5/governance"), "w5", profile="tests.lookup_profile") as (store, project):
        try:
            with client("publisher") as publisher, client("reader") as reader, \
                    client("maintainer") as maintainer, client("other_publisher") as other:
                verify(store, project, publisher, reader, maintainer, other)
        finally:
            scope = {"project_id": {"$in": [project, project + "-other"]}}
            for name in ("results", "result_vectors", "result_versions", "decisions"):
                store.db[name].delete_many(scope)
            for row in store.artifacts.files.find({"metadata.project_id": project}, {"_id": 1}):
                store.artifacts.bucket.delete(row["_id"])
    print("Atlas isolation, retained-vector governance, plan validation and concurrent approval/dispatch passed.")


if __name__ == "__main__":
    main()
