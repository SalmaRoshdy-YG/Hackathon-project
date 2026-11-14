import argparse
from datetime import datetime, timedelta, timezone

from benchmark.client import connect, require, save
from benchmark.run import measure

HYPOTHESES = {
    "promising": "A shared phrase dictionary A keeps independent DEFLATE event payloads within forty percent of their raw length.",
    "negative": "A shared phrase dictionary B might shorten independent DEFLATE event payloads for the A vocabulary.",
    "distractor": "A shared phrase dictionary B reduces compressed size for independent DEFLATE event payloads in cohort B.",
    "crash": "A third shared phrase dictionary might reduce the wire size of independent DEFLATE event payloads.",
    "replacement": "Repeating the shared phrase dictionary A measurement shows it did not reduce independent DEFLATE event payloads enough on cohort B.",
}


def document(receipt, label, expiry=None):
    return {"schema_version": 1, "hypothesis": HYPOTHESES[label],
            **{k: receipt[k] for k in ("fixture_revision", "conditions", "configuration", "metric",
                                       "execution", "validity", "direction")},
            "evidence": {"kind": "job_receipt", "data": receipt},
            "source": {"system": "benchmark", "source_agent": "agent-a", "record": receipt["run_id"]},
            "expires_at": expiry or (datetime.now(timezone.utc)+timedelta(hours=8)).isoformat()}


def replacement():
    return document(measure("dict-a-l1", "B", "calibration"), "replacement")


def produce(client, promising_expires_at=None):
    measurements = {"promising": ("dict-a-l1", "A"), "negative": ("dict-b-l1", "A"),
                    "distractor": ("dict-b-l1", "B"), "crash": ("dict-c-l1", "A")}
    output = {"refs": {}, "receipts": {}}
    for label, (job, cohort) in measurements.items():
        receipt = measure(job, cohort, "calibration")
        expiry = promising_expires_at if label == "promising" else None
        output["refs"][label] = require(client.post("/v1/results", json=document(receipt, label, expiry)))
        output["receipts"][label] = receipt
    return output


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out")
    p.add_argument("--base-url")
    p.add_argument("--promising-expires-at")
    p.add_argument("--project-token-env", default="MEMORY_TOKEN")
    args = p.parse_args()
    with connect(args.base_url, args.project_token_env) as client:
        save(produce(client, args.promising_expires_at), args.out)


if __name__ == "__main__":
    main()
