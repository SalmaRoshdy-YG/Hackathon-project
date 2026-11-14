"""Prepare a fresh Atlas project and serve its real ResNet workbench."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import httpx

from demo.common import client
from demo.harness import fixture, free_port, subprocess_service, wait_for
from experiments.resnet import REQUEST, TASK


def prepare(output):
    output = output.resolve()
    with fixture(output, "demo-w3", profile="experiments.resnet") as (_, project):
        baseline = output / "baseline.json"
        with baseline.open("w", encoding="utf-8") as log:
            subprocess.run([sys.executable, "-m", "experiments.resnet", "train", "scratch",
                            "holdout", str(output / "baseline.safetensors")], stdout=log, check=True)
        json.loads(baseline.read_text(encoding="utf-8"))
        with (output / "seed.log").open("w", encoding="utf-8") as log:
            subprocess.run([sys.executable, "-m", "experiments.resnet", "seed"], stdout=log, check=True)
        with client("reader") as api:
            listed = api.get("/v1/results")
            listed.raise_for_status()
            findings = listed.json()["items"]
            if len(findings) != 4 or sum(row["execution"] == "crashed" for row in findings) != 1:
                raise RuntimeError("Expected four calibration records including one crash.")
            expected = {row["result_id"] for row in findings if row["execution"] == "completed"}

            def indexed():
                response = api.post("/v1/search", json={"question": REQUEST, "conditions": TASK})
                response.raise_for_status()
                return {row["result"]["result_id"] for row in response.json()["candidates"]}

            wait_for(indexed, lambda ids: ids == expected, "three indexed calibration results", seconds=95)

        port = free_port()
        url = f"http://127.0.0.1:{port}"
        os.environ["MEMORY_BASELINE_RECEIPT"] = str(baseline)
        with subprocess_service("workbench.app:app", port, output / "workbench.log") as process:
            def health():
                if process.poll() is not None:
                    raise RuntimeError("Workbench exited. See workbench.log.")
                try:
                    response = httpx.get(f"{url}/api/state", timeout=5, trust_env=False)
                    return response.json() if response.is_success else {}
                except httpx.TransportError:
                    return {}

            wait_for(health, lambda state: state.get("project") == project
                     and state.get("health", {}).get("index") == "READY"
                     and state.get("codex_available"), "workbench with Codex and Atlas")
            (output / "url.txt").write_text(url, encoding="utf-8")
            print(f"Fresh project {project} ready at {url}. Ctrl+C stops both services.", flush=True)
            process.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    try:
        prepare(parser.parse_args().out)
    except KeyboardInterrupt:
        pass
