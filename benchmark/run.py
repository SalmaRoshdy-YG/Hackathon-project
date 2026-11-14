"""Deterministic, independent zlib streams on synthetic event packets."""
import argparse
import hashlib
import json
import platform
import time
import uuid
import zlib

FIXTURE = "short-events-v1"
CATALOG = ("plain-l1", "dict-a-l6", "dict-b-l6")
JOBS = {"plain-l1": (1, None), "dict-a-l1": (1, "A"), "dict-b-l1": (1, "B"),
        "dict-c-l1": (1, "C"), "dict-a-l6": (6, "A"), "dict-b-l6": (6, "B")}
TASK = {"fixture_revision": FIXTURE, "cohort": "A", "split": "holdout",
        "codec": "zlib-wrapped-deflate", "dictionary_revision": "phrases-v1"}
REQUEST = ("Can we get individually transmitted cohort A telemetry well under half its original "
           "size on unseen events? Aim for 40% or less and spend one trial.")
QUESTION = "What previously helped shrink one-at-a-time cohort A telemetry packets?"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def vocabulary(cohort):
    return [sha(f"{cohort}:{i}".encode())[:24] for i in range(32)]


def measure(job, cohort, split):
    start = time.perf_counter()
    if cohort not in ("A", "B") or split not in ("calibration", "holdout"):
        raise ValueError("unsupported fixture conditions")
    level, family = JOBS[job]
    words = vocabulary(cohort)
    offset = int(split == "holdout")
    rows = ["|".join([sha(f"{cohort}:{split}:{j}".encode())[:16],
                      *(words[(4*j+offset+k) % 32] for k in range(4))]).encode() for j in range(8)]
    dictionary = "|".join(vocabulary(family)).encode() if family in ("A", "B") else None
    complete = family != "C"
    ok, output = False, None
    if complete:
        kwargs = {"zdict": dictionary} if dictionary else {}
        ok, output = True, 0
        for row in rows:
            encoder = zlib.compressobj(level, zlib.DEFLATED, 15, **kwargs)
            wire = encoder.compress(row) + encoder.flush()
            decoder = zlib.decompressobj(15, **kwargs)
            decoded = decoder.decompress(wire) + decoder.flush()
            ok &= decoded == row and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail
            output += len(wire)
    size = sum(map(len, rows))
    ratio = output / size if output is not None else None
    return {
        "run_id": str(uuid.uuid4()), "fixture_revision": FIXTURE,
        "conditions": {**{k: v for k, v in TASK.items() if k != "fixture_revision"}, "cohort": cohort, "split": split},
        "configuration": {"job_id": job, "level": level, "dictionary_family": family},
        "metric": {"name": "wire_ratio", "value": ratio, "unit": "ratio", "operator": "<=", "threshold": 0.4},
        "execution": "completed" if complete else "crashed", "validity": "valid" if ok else "invalid",
        "direction": ("positive" if ratio <= 0.4 else "negative") if ok else "undetermined",
        "input_bytes": size, "output_bytes": output, "roundtrip_ok": ok,
        "elapsed_ms": round((time.perf_counter()-start)*1000, 3),
        "failure": None if complete else "dictionary C is not provisioned",
        "reproduce": {"command": f"python -m benchmark.run --job {job} --cohort {cohort} --split {split}",
                      "fixture_sha256": sha(b"\n".join(rows)),
                      "dictionary_sha256": sha(dictionary) if dictionary else None,
                      "zlib_version": zlib.ZLIB_RUNTIME_VERSION, "python_version": platform.python_version()},
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--job", choices=JOBS, required=True)
    p.add_argument("--cohort", choices=["A", "B"], required=True)
    p.add_argument("--split", choices=["calibration", "holdout"], required=True)
    a = p.parse_args()
    print(json.dumps(measure(a.job, a.cohort, a.split)))


if __name__ == "__main__":
    main()
