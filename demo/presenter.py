"""Local browser-facing API. Auth credentials never cross this boundary."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import json
import os
from threading import Event, Lock, Thread
from time import monotonic, sleep
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pymongo.errors import PyMongoError

from demo.common import client, run_agent
from platform_api.activity import Events
from platform_api.app import frame
from platform_api.config import identities, utcnow
from platform_api.models import Approve, Body, Expire, Reject, ResultID
from platform_api.profile import experiment, presentation
from platform_api.store import Store
from typing import Literal

WEB = Path(__file__).resolve().parent / "web"
WEB_PATH = Path(os.getenv("MEMORY_WEB_DIR", str(WEB))).resolve()


def safe_api(response):
    if response.is_error:
        raise HTTPException(response.status_code, response.json().get("detail", "platform_error"))
    return response.json()


def forward(role, method, path, payload=None):
    with client(role) as api:
        return safe_api(api.request(method, path, json=payload))


def change_payload(name, operation, doc):
    status = doc.get("status")
    if name == "results":
        status = "expired" if doc["expires_at"] <= utcnow() else "current"
    return {"operation": operation, "collection": name,
            "result_id" if name == "results" else "decision_id": doc["_id"],
            "version": doc.get("version"), "status": status, "updated_at": doc["updated_at"]}


def watch(app, name):
    state = app.state
    collection = state.store.db[name]
    project = state.project
    start = state.started_at
    resume = None
    while not state.stop.is_set():
        try:
            kwargs = {"resume_after": resume} if resume else {"start_at_operation_time": start}
            with collection.watch([{"$match": {"fullDocument.project_id": project}}],
                                  full_document="updateLookup", max_await_time_ms=350, **kwargs) as stream:
                state.modes[name] = "change-stream"
                while not state.stop.is_set():
                    entry = stream.try_next()
                    resume = stream.resume_token or resume
                    if entry and entry.get("fullDocument"):
                        state.events.send(project, "change", change_payload(
                            name, entry["operationType"], entry["fullDocument"]))
        except PyMongoError as exc:
            if getattr(exc, "code", None) in {9, 13, 20, 115, 303, 40573}:
                poll(app, name)
                return
            state.modes[name] = "reconnecting"
            state.stop.wait(0.5)


def poll(app, name):
    state = app.state
    collection = state.store.db[name]
    state.modes[name] = "polling"
    checkpoint = utcnow()
    seen = {}
    while not state.stop.wait(0.5):
        try:
            for doc in collection.find({"project_id": state.project, "updated_at": {"$gte": checkpoint}},
                                       {"updated_at": 1, "version": 1, "status": 1, "expires_at": 1}):
                checkpoint = max(checkpoint, doc["updated_at"])
                stamp = (doc["updated_at"], doc.get("version"), doc.get("status"))
                if seen.get(doc["_id"]) != stamp:
                    seen[doc["_id"]] = stamp
                    state.events.send(state.project, "change", change_payload(name, "poll-update", doc))
        except PyMongoError:
            continue


async def relay(app, token_name, source):
    state = app.state
    base = os.getenv("MEMORY_API_URL", "http://127.0.0.1:8000")
    previous = None
    async with httpx.AsyncClient(base_url=base, timeout=httpx.Timeout(14), trust_env=False) as api:
        while True:
            try:
                headers = {"Authorization": "Bearer " + os.environ[token_name]}
                if previous is not None:
                    headers["Last-Event-ID"] = previous
                async with api.stream("GET", "/v1/activity", headers=headers) as response:
                    response.raise_for_status()
                    current = None
                    async for line in response.aiter_lines():
                        if line.startswith("id: "):
                            current = line[4:]
                        elif line.startswith("data: "):
                            state.events.send(state.project, "atlas", {**json.loads(line[6:]), "scope": source})
                            previous = current
            except (httpx.HTTPError, ValueError):
                await asyncio.sleep(0.5)


@asynccontextmanager
async def lifespan(app):
    state = app.state
    state.experiment = experiment()
    state.profile = presentation(state.experiment)
    configured = identities()
    who = {role: configured[os.environ[f"MEMORY_{role.upper()}_TOKEN"]]
           for role in ("publisher", "reader", "maintainer", "other")}
    state.project = who["reader"].project_id
    if (not all(who[role].project_id == state.project and who[role].role == role
                for role in ("publisher", "reader", "maintainer"))
            or who["other"].project_id == state.project or who["other"].role != "reader"):
        raise ValueError("presenter token configuration does not isolate projects and roles")
    state.store = Store(os.environ["MEMORY_ATLAS_URI"], os.environ["MEMORY_ATLAS_DB"])
    try:
        state.started_at = await asyncio.to_thread(
            lambda: state.store.client.admin.command("hello")["operationTime"])
    except (PyMongoError, KeyError):
        state.started_at = None
    state.events, state.stop, state.action = Events(), Event(), Lock()
    state.modes = {"results": "connecting", "decisions": "connecting"}
    state.memory, state.stage, state.latest, state.producer = "on", "discover", None, None
    state.proposal_snapshot = None
    state.awaiting_index = []
    state.demo_session = str(uuid4())
    workers = [Thread(target=watch, args=(app, name), daemon=True) for name in state.modes]
    for worker in workers:
        worker.start()
    tasks = [asyncio.create_task(relay(app, f"MEMORY_{role.upper()}_TOKEN", label))
             for role, label in (("reader", "current"), ("other", "isolation-check"))]
    try:
        yield
    finally:
        state.stop.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.to_thread(state.store.client.close)


app = FastAPI(title="Precedent presenter", lifespan=lifespan)


@app.middleware("http")
async def local_browser(request: Request, call_next):
    host = request.url.hostname
    if host not in ("127.0.0.1", "localhost", "::1", "testserver"):
        return JSONResponse({"detail": "local_presenter_only"}, status_code=403)
    if any(part.startswith(".") for part in request.url.path.split("/") if part):
        return JSONResponse({"detail": "not_found"}, status_code=404)
    origin = request.headers.get("origin")
    if origin and origin not in {f"http://{request.url.netloc}", f"https://{request.url.netloc}"}:
        return JSONResponse({"detail": "same_origin_required"}, status_code=403)
    return await call_next(request)


@app.exception_handler(httpx.HTTPError)
async def upstream_unavailable(_request, _exc):
    return JSONResponse({"detail": "platform_unavailable"}, status_code=503)


@app.exception_handler(RuntimeError)
async def runner_failed(_request, _exc):
    return JSONResponse({"detail": "research_runner_failed"}, status_code=502)


@app.get("/")
def home():
    if not (WEB_PATH / "index.html").is_file():
        return JSONResponse({"service": "Precedent presenter", "state": "/demo/state",
                             "events": "/demo/events", "openapi": "/openapi.json"})
    return FileResponse(WEB_PATH / "index.html")


@app.get("/demo/state")
def state():
    state = app.state
    with client("reader") as api:
        health = api.get("/v1/health").json()
        findings = safe_api(api.get("/v1/results"))["items"]
        decisions = safe_api(api.get("/v1/decisions"))["items"]
    return {"stage": state.stage, "health": health, "project": state.project,
            "memory": state.memory, "findings": findings, "latest_decision": decisions[0] if decisions else None,
            "evidence_candidates": state.proposal_snapshot, "producer": state.producer,
            "receipts": [d["receipt"] for d in reversed(decisions) if d.get("receipt")],
            "stream": dict(state.modes),
            "environment": {**state.profile.environment(), "experiment_id": state.experiment.id,
                            "embedding": health.get("embedding_model")}}


@app.get("/demo/events")
async def events(request: Request):
    last = request.headers.get("last-event-id", "")
    try:
        last_session, last_id = last.rsplit(":", 1)
        start = max(0, int(last_id)) if last_session == app.state.demo_session else 0
    except ValueError:
        start = 0

    async def feed():
        state = app.state
        n, ping = start, monotonic()
        yield ": connected\n\n"
        while not await request.is_disconnected():
            for seq, kind, payload in state.events.since(state.project, n):
                n = seq
                yield frame(kind, payload, f"{state.demo_session}:{n}")
            if monotonic()-ping >= 10:
                ping = monotonic()
                yield ": keepalive\n\n"
            await asyncio.sleep(0.075)
    return StreamingResponse(feed(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/demo/agent-a")
def producer():
    state = app.state
    with state.action:
        if state.producer:
            return state.producer
        state.producer = run_agent(state.profile.producer_module, "MEMORY_PUBLISHER_TOKEN")
        refs = state.producer["refs"]
        labels = state.producer.get("index_labels", refs)
        state.awaiting_index = [refs[label] for label in labels
                               if searchable(state.producer["receipts"][label])]
        state.stage = "published"
        return state.producer


class Memory(Body):
    memory: Literal["on", "off"]


def searchable(measurement):
    return measurement["execution"] == "completed" and measurement["validity"] == "valid"


def search_body():
    profile = app.state.profile
    return {"question": profile.question, "conditions": profile.conditions}


def propose(memory):
    state = app.state
    if memory == "on" and state.awaiting_index:
        until = monotonic() + 20
        while state.awaiting_index:
            rows = forward("reader", "POST", "/v1/search", search_body())
            current = [{k: item["result"][k] for k in ("result_id", "version")}
                       for item in rows["candidates"]]
            state.awaiting_index = [r for r in state.awaiting_index if r not in current]
            if not state.awaiting_index:
                break
            if monotonic() >= until:
                raise HTTPException(503, "search_index_catching_up")
            sleep(0.35)
    result = run_agent(state.profile.agent_module, "MEMORY_READER_TOKEN", "--memory", memory)
    state.memory = memory
    state.latest = result["decision_id"]
    state.proposal_snapshot = result["evidence_candidates"]
    state.stage = "recommendation"
    return result


@app.post("/demo/agent-b")
def agent(body: Memory):
    with app.state.action:
        return propose(body.memory)


@app.post("/demo/rerun")
def rerun():
    with app.state.action:
        return propose(app.state.memory)


@app.post("/demo/decisions/{decision_id}/approve")
def approve(decision_id: ResultID, body: Approve = Approve()):
    result = forward("maintainer", "POST", f"/v1/decisions/{decision_id}/approve", body.model_dump())
    app.state.stage = "approved"
    return result


@app.post("/demo/decisions/{decision_id}/reject")
def reject(decision_id: ResultID, body: Reject = Reject()):
    result = forward("maintainer", "POST", f"/v1/decisions/{decision_id}/reject", body.model_dump())
    app.state.stage = "rejected"
    return result


@app.post("/demo/decisions/{decision_id}/execute")
def execute(decision_id: ResultID):
    # Check before launching the helper so wrong-state errors remain 409.
    status = forward("reader", "GET", f"/v1/decisions/{decision_id}")["status"]
    if status != "approved":
        raise HTTPException(409, "decision_not_approved")
    # The platform atomically claims dispatch and measures the approved job.
    result = forward("reader", "POST", f"/v1/decisions/{decision_id}/execute")
    app.state.stage = result["status"]
    return result


class Governance(Expire):
    result_id: ResultID


@app.post("/demo/governance/correct")
def correct(body: Governance):
    with app.state.action:
        replacement = app.state.profile.replacement()
        result = forward("maintainer", "POST", f"/v1/results/{body.result_id}/correct",
                         {**body.model_dump(exclude={"result_id"}), "replacement": replacement})
        app.state.awaiting_index = [r for r in app.state.awaiting_index if r["result_id"] != body.result_id]
        if searchable(replacement):
            app.state.awaiting_index.append(result)
        app.state.stage = "corrected"
        return result


@app.post("/demo/governance/expire")
def expire(body: Governance):
    with app.state.action:
        result = forward("maintainer", "POST", f"/v1/results/{body.result_id}/expire",
                         body.model_dump(exclude={"result_id"}))
        app.state.awaiting_index = [r for r in app.state.awaiting_index if r["result_id"] != body.result_id]
        app.state.stage = "expired"
        return result


@app.get("/demo/results/{result_id}/history")
def history(result_id: ResultID):
    return forward("reader", "GET", f"/v1/results/{result_id}/history")


@app.get("/demo/results/{result_id}/evidence")
def evidence(result_id: ResultID, version: int | None = None):
    q = f"?version={version}" if version is not None else ""
    return forward("reader", "GET", f"/v1/results/{result_id}/evidence{q}")


@app.post("/demo/isolation-check")
def isolation():
    items = forward("reader", "GET", "/v1/results")["items"]
    target = items[0]["result_id"] if items else None
    if not target:
        raise HTTPException(409, "publish_findings_first")
    with client("other") as other:
        search = safe_api(other.post("/v1/search", json=search_body()))
        direct = other.get(f"/v1/results/{target}")
        evidence = other.get(f"/v1/results/{target}/evidence")
    return {"search": search, "direct_status": direct.status_code, "evidence_status": evidence.status_code,
            "isolated": not search["candidates"] and direct.status_code == evidence.status_code == 404}


if WEB_PATH.is_dir():
    app.mount("/", StaticFiles(directory=WEB_PATH, html=True), name="frontend")
