"""Exercise presenter and SSE contracts through HTTP against the event Atlas Sandbox."""
import argparse
import json
from pathlib import Path
from threading import Event, Thread
from time import monotonic

import httpx

from platform_api.client import require, save
from demo.harness import fixture, free_port, subprocess_service, wait_for


def smoke(out):
    with fixture(out, "presenter"):
        port = free_port()
        base = f"http://127.0.0.1:{port}"
        with subprocess_service("demo.presenter:app", port, out/"presenter.log") as proc, \
                httpx.Client(base_url=base, timeout=50, trust_env=False) as web:
            def state():
                if proc.poll() is not None:
                    raise RuntimeError("presenter exited; see presenter.log")
                try:
                    return require(web.get("/demo/state"))
                except httpx.TransportError:
                    return {}
            initial = wait_for(state, lambda row: row.get("stream") ==
                {"results": "change-stream", "decisions": "change-stream"}, "both change streams")
            assert not initial["findings"]
            received, ready, stop = [], Event(), Event()

            def collect():
                try:
                    with httpx.Client(base_url=base, timeout=httpx.Timeout(12), trust_env=False) as stream:
                        with stream.stream("GET", "/demo/events") as response:
                            response.raise_for_status()
                            kind = ""
                            for line in response.iter_lines():
                                if stop.is_set():
                                    return
                                if line.startswith(": connected"):
                                    ready.set()
                                elif line.startswith("event: "):
                                    kind = line[7:]
                                elif line.startswith("data: "):
                                    received.append((kind, json.loads(line[6:]), monotonic()))
                except httpx.TransportError:
                    if not stop.is_set():
                        stop.set()


            consumer = Thread(target=collect, daemon=True)
            consumer.start()
            assert ready.wait(5)
            timings = {}

            def event(kind, predicate, label, start=0):
                return wait_for(lambda: next((row for event_kind, row, ts in list(received)
                    if event_kind == kind and ts >= start and predicate(row)), None), bool, label, seconds=8)

            def changed(body, start, collection, key, **match):
                elapsed = wait_for(lambda: next((max(0, t-start) for k,row,t in list(received)
                    if k == "change" and row["collection"] == collection and row.get(key) == body[key]
                    and all(row.get(f) == v for f,v in match.items())), None),
                    lambda t: t is not None, "change after write", seconds=7)
                assert elapsed < 1, f"change latency: {elapsed:.3f}s"
                return round(elapsed*1000)

            def post(url, payload=None):
                return require(web.post("/demo"+url, json=payload))

            try:
                flow_started = monotonic()
                assert web.post("/demo/agent-a", headers={"Origin": "https://other.invalid"}).status_code == 403
                producer = post("/agent-a")
                producer_done = monotonic()
                timings["four_publications"] = max(
                    changed(result, producer_done, "results", "result_id", operation="insert")
                    for result in producer["refs"].values())
                promised, negative = (producer["refs"][k] for k in ("promising", "negative"))
                initial_job = post("/agent-b", {"memory": "off"})
                rid = f"/decisions/{initial_job['decision_id']}"
                assert web.post("/demo"+rid+"/execute").status_code == 409
                start = monotonic()
                post(rid+"/approve")
                timings["approval"] = changed(initial_job, start, "decisions", "decision_id", status="approved")
                baseline = post(rid+"/execute")["receipt"]
                on = post("/agent-b", {"memory": "on"})
                assert len(on["evidence_candidates"]) == 3 and on["job_id"] == "dict-a-l6"
                reject_path = f"/decisions/{on['decision_id']}"
                assert post(reject_path+"/reject")["status"] == "rejected"
                assert web.post("/demo"+reject_path+"/execute").status_code == 409
                on = post("/rerun")
                rid = f"/decisions/{on['decision_id']}"
                post(rid+"/approve")
                live = post(rid+"/execute")["receipt"]
                assert live["output_bytes"] < baseline["output_bytes"]

                start = monotonic()
                v2 = post("/governance/correct", {"result_id": promised["result_id"], "expected_version": 1,
                    "reason": "Receipt belongs to cohort B"})
                timings["correction"] = changed(v2, start, "results", "result_id",
                                               operation="update", version=2)
                corrected = post("/rerun")
                assert corrected["job_id"] == "plain-l1" and v2 in [
                    row["ref"] for row in corrected["rejected_candidates"]]
                rid = f"/decisions/{corrected['decision_id']}"
                post(rid+"/approve")
                post(rid+"/execute")

                start = monotonic()
                expired = post("/governance/expire", {"result_id": negative["result_id"], "expected_version": 1,
                    "reason": "Retired for rehearsal"})
                timings["expiry"] = changed(expired, start, "results", "result_id",
                                            operation="update", status="expired")
                rerun = post("/rerun")
                assert rerun["job_id"] == "plain-l1" and negative not in [r["ref"] for r in rerun["candidates"]]
                rid = f"/decisions/{rerun['decision_id']}"
                post(rid+"/approve")
                post(rid+"/execute")
                assert len(state()["receipts"]) == 4
                assert len(require(web.get(f"/demo/results/{promised['result_id']}/history"))["versions"]) == 2
                assert post("/isolation-check")["isolated"]
                event("atlas", lambda d: d["scope"] == "isolation-check" and d["command"] == "aggregate"
                      and d["docs"] == 0, "redacted isolated search")
                event("atlas", lambda d: d["command"] == "commitTransaction" and d["ok"], "correction transaction")
                event("atlas", lambda d: d["command"] == "findAndModify" and d["collection"] == "decisions"
                      and d["shape"]["updates"][0]["status"] == "approved", "conditional approval")
                event("atlas", lambda d: d["command"] == "findAndModify" and d["collection"] == "results"
                      and "expires_at" in d["shape"]["updates"][0]["fields"], "expiry command")
                pipeline = event("atlas", lambda d: d["collection"] == "result_vectors"
                                 and d["command"] == "aggregate" and d["docs"] == 3, "real Atlas search")["shape"]["pipeline"]
                assert pipeline[0]["$vectorSearch"]["queryVector"] == "[1536 floats]"
                assert pipeline[0]["$vectorSearch"]["filter"]["project_id"] == "[trusted project]"
                assert sum("$lookup" in stage for stage in pipeline) == 1
                assert any("applicability" in stage.get("$set", []) for stage in pipeline)
                browser_outputs = json.dumps([row for _, row, _ in list(received)] + [state()])
                import os
                assert all(os.environ[k] not in browser_outputs for k in
                           ("MEMORY_PUBLISHER_TOKEN", "MEMORY_READER_TOKEN", "MEMORY_MAINTAINER_TOKEN",
                            "MEMORY_OTHER_TOKEN", "MEMORY_ATLAS_URI"))
                duration = monotonic() - flow_started
                assert duration < 180
                return {"receipts": 4, "duration_seconds": round(duration, 2), "atlas_events": sum(k == "atlas" for k, _, _ in received),
                        "change_events": sum(k == "change" for k, _, _ in received),
                        "change_delivery_ms": timings, "redaction": True, "isolation": True}
            finally:
                stop.set()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=Path("receipts/presenter"))
    args = p.parse_args()
    save(smoke(args.out), args.out/"summary.json")


if __name__ == "__main__":
    main()
