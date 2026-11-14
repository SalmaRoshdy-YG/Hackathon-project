import os
from contextlib import contextmanager
from pathlib import Path
import socket
import subprocess
import sys
from time import monotonic, sleep
from uuid import uuid4

import httpx

from demo.common import client
from platform_api.setup import roles
from platform_api.store import Store


def wait_for(get, check, label, seconds=30):
    end = monotonic()+seconds
    while True:
        value = get()
        if check(value):
            return value
        if monotonic() >= end:
            raise AssertionError(f"did not observe {label}")
        sleep(0.35)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextmanager
def subprocess_service(target, port, logfile, *, cwd=None):
    with Path(logfile).open("w", encoding="utf-8") as log:
        proc = subprocess.Popen([sys.executable, "-m", "uvicorn", target, "--host", "127.0.0.1",
                                 "--port", str(port), "--no-access-log"], stdout=log, stderr=log, cwd=cwd)
        try:
            yield proc
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


@contextmanager
def fixture(out, prefix="check", *, profile=None, cwd=None):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    project = f"{prefix}-{uuid4().hex[:12]}"
    env = roles(project)
    # Preflight also has an authorized publisher in the other fixture project.
    import json
    from secrets import token_urlsafe
    mapping = json.loads(env["MEMORY_TOKENS_JSON"])
    other = token_urlsafe(32)
    mapping[other] = {"project_id": project+"-other", "agent_id": "other-producer", "role": "publisher"}
    env["MEMORY_OTHER_PUBLISHER_TOKEN"] = other
    env["MEMORY_TOKENS_JSON"] = json.dumps(mapping)
    port = free_port()
    env["MEMORY_EXPERIMENT_MODULE"] = profile or ""
    env["MEMORY_PRESENTATION_MODULE"] = ""
    env["MEMORY_API_URL"] = f"http://127.0.0.1:{port}"
    prior = {key: os.environ.get(key) for key in env}
    os.environ.update(env)
    store = Store(os.environ["MEMORY_ATLAS_URI"], os.environ["MEMORY_ATLAS_DB"])
    try:
        store.setup()
        wait_for(store.index_state, lambda s: s == "READY", "queryable Atlas index", seconds=95)
        with subprocess_service("platform_api.app:app", port, out/"platform.log", cwd=cwd) as proc:
            with client("reader") as api:
                def health():
                    if proc.poll() is not None:
                        raise RuntimeError("platform service exited; see platform.log")
                    try:
                        return api.get("/v1/health").status_code
                    except httpx.TransportError:
                        return 0
                wait_for(health, lambda code: code == 200, "platform and Atlas ready")
            yield store, project
    finally:
        store.client.close()
        for key, value in prior.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
