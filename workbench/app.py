"""Local live workspace with a shared MCP endpoint for coding agents."""
import asyncio
from contextlib import asynccontextmanager
from hmac import compare_digest
from importlib import import_module
import json
import os
from pathlib import Path
from threading import Event, Thread
from time import monotonic
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.fastmcp import FastMCP
from pymongo.errors import PyMongoError
from starlette.routing import Route

from demo.common import client
from demo.presenter import relay, safe_api, watch
from platform_api.activity import Events
from platform_api.app import frame
from platform_api.config import identities
from platform_api.models import Body, Candidate, Conditions, Plan, Publish, ResultID, Search, Tag, Text
from platform_api.profile import experiment
from platform_api.store import Store
from workbench.terminal import access, access_cookie, executable, terminal

ROOT = Path(__file__).resolve().parents[1]
mcp = FastMCP("Precedent", stateless_http=True, json_response=True, streamable_http_path="/mcp",
              instructions="Search shared experiments, cite exact result versions and submit a plan. "
                           "The operator approves it in the workspace before any job can run.")


def api(role, method, path, body=None, timeout=40):
    with client(role) as connection:
        return safe_api(connection.request(method, path, json=body, timeout=timeout))


@asynccontextmanager
async def lifespan(app):
    state = app.state
    configured = identities()
    roles = {role: configured[os.environ[f"MEMORY_{role.upper()}_TOKEN"]]
             for role in ("reader", "maintainer", "publisher")}
    state.project = roles["reader"].project_id
    if any(who.project_id != state.project or who.role != role for role, who in roles.items()):
        raise ValueError("workbench identities must share a project and match their configured roles")
    state.experiment = experiment()
    profile = os.getenv("MEMORY_EXPERIMENT_MODULE")
    state.defaults = getattr(import_module(profile), "DEFAULTS", {}) if profile else {}
    state.events, state.stop = Events(), Event()
    state.modes = {"results": "connecting", "decisions": "connecting"}
    state.session = str(uuid4())
    state.store = Store(os.environ["MEMORY_ATLAS_URI"], os.environ["MEMORY_ATLAS_DB"])
    try:
        state.started_at = await asyncio.to_thread(
            lambda: state.store.client.admin.command("hello")["operationTime"])
    except (PyMongoError, KeyError):
        state.started_at = None
    workers = [Thread(target=watch, args=(app, name), daemon=True) for name in state.modes]
    for worker in workers:
        worker.start()
    activity = asyncio.create_task(relay(app, "MEMORY_READER_TOKEN", "current"))
    try:
        async with mcp.session_manager.run():
            yield
    finally:
        state.stop.set()
        activity.cancel()
        await asyncio.gather(activity, return_exceptions=True)
        await asyncio.to_thread(state.store.client.close)


mcp_app = mcp.streamable_http_app()
app = FastAPI(title="Precedent workbench", lifespan=lifespan)


@app.middleware("http")
async def local_only(request: Request, call_next):
    local, authorized, origin_ok = access(request)
    if not local and (not os.getenv("MEMORY_REMOTE_PASSWORD") or request.url.path == "/mcp"):
        return JSONResponse({"detail": "local_workbench_only"}, 403)
    if not origin_ok:
        return JSONResponse({"detail": "same_origin_required"}, 403)
    if not authorized and request.url.path != "/login":
        return RedirectResponse("/login", 303) if request.url.path == "/" else JSONResponse(
            {"detail": "sign_in_required"}, 401)
    return await call_next(request)


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return """<!doctype html><html lang="en"><title>Precedent sign in</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <main style="font:16px system-ui;max-width:30rem;margin:12vh auto;padding:1rem">
    <h1>Precedent</h1><form method="post">
    <label>Workspace password <input type="password" name="password" required autofocus></label>
    <button>Open workspace</button></form></main></html>"""


@app.post("/login")
async def login(request: Request):
    expected = os.getenv("MEMORY_REMOTE_PASSWORD")
    supplied = (await request.form()).get("password")
    if not expected or not isinstance(supplied, str) or not compare_digest(supplied.encode(), expected.encode()):
        return HTMLResponse("Invalid workspace password. <a href='/login'>Try again</a>", 401)
    response = RedirectResponse("/", 303)
    response.set_cookie("precedent_access", access_cookie(expected), secure=True, httponly=True, samesite="strict")
    return response


@app.exception_handler(httpx.HTTPError)
async def platform_unavailable(_request, _error):
    return JSONResponse({"detail": "platform_unavailable"}, 503)


@app.get("/api/state")
def state():
    current = app.state
    with client("reader") as connection:
        health = connection.get("/v1/health").json()
        findings = safe_api(connection.get("/v1/results"))["items"]
        decisions = safe_api(connection.get("/v1/decisions"))["items"]
    selected = current.experiment
    baseline_path = os.getenv("MEMORY_BASELINE_RECEIPT")
    baseline = json.loads(Path(baseline_path).read_text(encoding="utf-8-sig")) if baseline_path else None
    return {"project": current.project, "health": health, "streams": current.modes,
            "defaults": current.defaults, "jobs": list(selected.catalog) if selected else [],
            "codex_available": bool(executable()),
            "findings": findings, "decisions": decisions, "baseline": baseline}


@app.get("/api/events")
async def events(request: Request):
    current = app.state
    last = request.headers.get("last-event-id", "")
    session, _, after = last.rpartition(":")
    start = int(after) if session == current.session and after.isdigit() else 0

    async def stream():
        sequence, heartbeat = start, monotonic()
        yield ": connected\n\n"
        while not await request.is_disconnected():
            for sequence, kind, payload in current.events.since(current.project, sequence):
                yield frame(kind, payload, f"{current.session}:{sequence}")
            if monotonic() - heartbeat > 10:
                yield ": keepalive\n\n"
                heartbeat = monotonic()
            await asyncio.sleep(.1)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/event-batch")
def event_batch(after: int = 0):
    current = app.state
    return {"session": current.session, "events": current.events.since(current.project, after)}


def discover(body):
    rows = api("reader", "POST", "/v1/search", body.model_dump())["candidates"]
    app.state.events.send(app.state.project, "search", {"candidates": rows})
    return rows


@app.post("/api/search")
def browser_search(body: Search):
    return {"candidates": discover(body)}


@app.get("/api/results/{result_id}/history")
def history(result_id: ResultID):
    return api("reader", "GET", f"/v1/results/{result_id}/history")


@app.get("/api/results/{result_id}/artifact")
def artifact(result_id: ResultID, version: int):
    connection = client("reader")
    try:
        response = connection.send(connection.build_request("GET", f"/v1/results/{result_id}/artifact",
                                   params={"version": version}), stream=True)
        if response.is_error:
            response.read()
            safe_api(response)
    except BaseException:
        connection.close()
        raise

    def stream():
        try:
            yield from response.iter_bytes()
        finally:
            connection.close()

    return StreamingResponse(stream(), media_type="application/octet-stream",
                             headers={key: response.headers[key] for key in
                                      ("content-length", "content-disposition", "x-artifact-sha256")})


@app.post("/api/decisions/{decision_id}/reject")
def reject(decision_id: ResultID):
    return api("maintainer", "POST", f"/v1/decisions/{decision_id}/reject", {})


def execute(decision_id):
    return api("reader", "POST", f"/v1/decisions/{decision_id}/execute", timeout=None)


@app.post("/api/decisions/{decision_id}/run")
async def approve_and_run(decision_id: ResultID):
    path = f"/v1/decisions/{decision_id}"
    current = await asyncio.to_thread(api, "reader", "GET", path)
    if current["status"] == "pending":
        await asyncio.to_thread(api, "maintainer", "POST", path + "/approve",
                                {"note": "Run confirmed in Precedent workspace"})
    return await asyncio.to_thread(execute, decision_id)


@app.websocket("/terminal/codex")
async def connect_terminal(socket: WebSocket):
    await terminal(socket)


@mcp.tool()
def experiment_profile() -> dict:
    """Get the active experiment's task conditions, suggested prompt, baseline and allowed jobs."""
    selected = app.state.experiment
    return {"defaults": app.state.defaults, "jobs": list(selected.catalog) if selected else []}


@mcp.tool()
def search_experiments(question: str, conditions: dict | None = None) -> list[dict]:
    """Use Atlas semantic search. Pass profile task conditions for authoritative fit labels."""
    return discover(Search(question=question, conditions=conditions))


@mcp.tool()
def get_experiment(result_id: ResultID, version: int) -> dict:
    """Read a current finding and measured evidence from an exact version."""
    result = api("reader", "GET", f"/v1/results/{result_id}?version={version}")
    result.update(api("reader", "GET", f"/v1/results/{result_id}/evidence?version={version}"))
    return result


@mcp.tool()
def load_weights(result_id: ResultID, version: int) -> dict:
    """Inspect checkpoint metadata. The trusted runner streams and verifies the cited weights on execution."""
    result = get_experiment(result_id, version)
    return {"artifact": result["artifact"], "result_id": result_id, "version": version,
            "workspace_download": f"/api/results/{result_id}/artifact?version={version}" if result["artifact"] else None}


class Recommendation(Body):
    plan: Plan
    candidates: list[Candidate]
    conditions: Conditions
    request: Text


@mcp.tool()
def propose_plan(recommendation: Recommendation, agent: Tag) -> dict:
    """Submit one job. For each candidate send ref, score and applicability from search. Cite exact versions."""
    body = recommendation.model_dump()
    plan = body.pop("plan")
    return api("reader", "POST", "/v1/decisions", {**body, **plan, "memory": "on", "model": agent})


@mcp.tool()
def run_plan(decision_id: ResultID) -> dict:
    """Return the plan or receipt. Dispatch only if the plan has already been approved by the workspace operator."""
    current = api("reader", "GET", f"/v1/decisions/{decision_id}")
    return execute(decision_id) if current["status"] == "approved" else current


@mcp.tool()
def publish_result(finding: Publish) -> dict:
    """Publish a measured finding with provenance. The trusted training runner publishes its own output."""
    return api("publisher", "POST", "/v1/results", finding.model_dump(mode="json"))


# Keep MCP on the same loopback origin as the browser and terminal.
app.router.routes.append(Route("/mcp", mcp_app, methods=["GET", "POST", "DELETE"]))
vendor = ROOT / "node_modules" / "@xterm"
if vendor.is_dir():
    app.mount("/vendor", StaticFiles(directory=vendor), name="terminal-assets")
app.mount("/", StaticFiles(directory=Path(__file__).with_name("web"), html=True), name="workbench")
