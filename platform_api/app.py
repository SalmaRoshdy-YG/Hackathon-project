from contextlib import asynccontextmanager
import json
import os
from time import monotonic
import asyncio

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pymongo.errors import PyMongoError
import httpx

from platform_api.activity import Events, scope
from platform_api.config import identities
from platform_api.decisions import Decisions, outward
from platform_api.embedding import model
from platform_api.models import Approve, Correct, Expire, Proposal, Publish, Reject, Resolve, ResultID, Search
from platform_api.store import Store, error, public


@asynccontextmanager
async def lifespan(app):
    app.state.identities = identities()
    bus = Events()
    store = Store(os.environ["MEMORY_ATLAS_URI"], os.environ["MEMORY_ATLAS_DB"], bus)
    app.state.store = store
    app.state.decisions = Decisions(store)
    app.state.bus = bus
    try:
        yield
    finally:
        store.client.close()


app = FastAPI(title="Precedent memory API", version="1.0", lifespan=lifespan)
bearer = HTTPBearer(auto_error=False)


async def identity(request: Request, auth: HTTPAuthorizationCredentials | None = Depends(bearer)):
    principal = request.app.state.identities.get(auth.credentials) if auth else None
    if not principal:
        error(401, "authentication_required")
    token = scope.set(principal.project_id)
    try:
        yield principal
    finally:
        scope.reset(token)


Principal = Depends(identity)


@app.exception_handler(RequestValidationError)
async def invalid(_request, _exc):
    return JSONResponse({"detail": "invalid_request"}, status_code=422)


@app.exception_handler(PyMongoError)
async def unavailable(_request, _exc):
    return JSONResponse({"detail": "database_unavailable"}, status_code=503)


@app.get("/v1/health")
def health(request: Request, who=Principal):
    store = request.app.state.store
    body = {"atlas": "ok", "index": "UNKNOWN", "database": store.db.name,
            "project_id": who.project_id, "embedding_model": model()}
    try:
        store.client.admin.command("ping")
    except PyMongoError:
        body["atlas"] = "unavailable"
        return JSONResponse(body, status_code=503)
    try:
        body["index"] = store.index_state()
    except PyMongoError:
        body["index"] = "unavailable"
    return JSONResponse(body, status_code=200 if body["index"] == "READY" else 503)


@app.post("/v1/results", status_code=201)
def publish(request: Request, body: Publish, who=Principal):
    try:
        return request.app.state.store.publish(who, body)
    except (httpx.HTTPError, KeyError, ValueError):
        error(503, "embedding_unavailable")


@app.get("/v1/results")
def results(request: Request, who=Principal):
    return {"items": [public(d) for d in request.app.state.store.all_heads(who)]}


@app.post("/v1/search")
def search(request: Request, body: Search, who=Principal):
    try:
        return {"candidates": request.app.state.store.search(who, body)}
    except (PyMongoError, httpx.HTTPError, KeyError, ValueError):
        error(503, "search_unavailable")


@app.get("/v1/results/{result_id}")
def read(request: Request, result_id: ResultID, version: int | None = Query(None, gt=0), who=Principal):
    return public(request.app.state.store.visible(who, result_id, version))


@app.get("/v1/results/{result_id}/evidence")
def evidence(request: Request, result_id: ResultID, version: int | None = Query(None, gt=0), who=Principal):
    doc = request.app.state.store.visible(who, result_id, version)
    return {"result_id": result_id, "version": doc["version"], "evidence": doc["evidence"]}


@app.get("/v1/results/{result_id}/history")
def history(request: Request, result_id: ResultID, who=Principal):
    return request.app.state.store.history(who, result_id)


@app.post("/v1/results/{result_id}/correct")
def correct(request: Request, result_id: ResultID, body: Correct, who=Principal):
    try:
        return request.app.state.store.correct(who, result_id, body)
    except (httpx.HTTPError, KeyError, ValueError):
        error(503, "embedding_unavailable")


@app.post("/v1/results/{result_id}/expire")
def expire(request: Request, result_id: ResultID, body: Expire, who=Principal):
    return request.app.state.store.expire(who, result_id, body)


@app.post("/v1/resolve")
def resolve(request: Request, body: Resolve, who=Principal):
    return {"results": request.app.state.store.resolve(who, body.refs)}


@app.get("/v1/decisions")
def latest(request: Request, who=Principal):
    return {"items": request.app.state.decisions.latest(who)}


@app.post("/v1/decisions", status_code=201)
def propose(request: Request, body: Proposal, who=Principal):
    return request.app.state.decisions.propose(who, body)


@app.get("/v1/decisions/{decision_id}")
def decision(request: Request, decision_id: ResultID, who=Principal):
    return outward(request.app.state.decisions.get(who, decision_id))


@app.post("/v1/decisions/{decision_id}/approve")
def approve(request: Request, decision_id: ResultID, body: Approve, who=Principal):
    return request.app.state.decisions.review(who, decision_id, "approved", body)


@app.post("/v1/decisions/{decision_id}/reject")
def reject(request: Request, decision_id: ResultID, body: Reject, who=Principal):
    return request.app.state.decisions.review(who, decision_id, "rejected", body)


@app.post("/v1/decisions/{decision_id}/execute", status_code=201)
def execute(request: Request, decision_id: ResultID, who=Principal):
    return request.app.state.decisions.dispatch(who, decision_id)


@app.post("/v1/decisions/{decision_id}/receipt", status_code=201)
def receipt(request: Request, decision_id: ResultID, who=Principal):
    # Same trusted runner path: never persist a caller-provided measurement.
    return request.app.state.decisions.dispatch(who, decision_id)


def frame(kind, payload, event_id=None):
    return (f"id: {event_id}\n" if event_id is not None else "") + (
        f"event: {kind}\ndata: {json.dumps(jsonable_encoder(payload), separators=(',', ':'))}\n\n")


@app.get("/v1/activity")
async def activity(request: Request, who=Principal):
    last = request.headers.get("last-event-id", "0")
    try:
        start = max(0, int(last))
    except ValueError:
        start = 0
    bus = request.app.state.bus

    async def stream():
        after, heartbeat = start, monotonic()
        yield ": connected\n\n"
        while not await request.is_disconnected():
            for n, kind, payload in bus.since(who.project_id, after):
                after = n
                yield frame(kind, payload, n)
            if monotonic() - heartbeat >= 10:
                heartbeat = monotonic()
                yield ": keepalive\n\n"
            await asyncio.sleep(0.08)
    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
