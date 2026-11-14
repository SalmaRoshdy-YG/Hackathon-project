"""Project-scoped, redacted activity from PyMongo and MongoDB change streams."""
from collections import deque
from contextvars import ContextVar
from threading import Lock
from time import monotonic

from pymongo.monitoring import CommandListener

scope = ContextVar("project", default=None)
COLLECTIONS = {"results", "result_vectors", "result_versions", "decisions"}
COMMANDS = {"aggregate", "insert", "update", "delete", "find", "getMore", "findAndModify",
            "commitTransaction", "abortTransaction"}
SAFE_FIELDS = {"project_id", "_id", "version", "search_key", "expires_at", "execution", "validity",
               "purge_at", "status", "updated_at", "events", "receipt", "decided_by", "decided_at",
               "embedding_model", "applicability", "mismatches", "score"}
SAFE_VALUES = {"pending", "approved", "rejected", "running", "executed", "aborted", "completed", "valid"}


class Events:
    def __init__(self):
        self.lock = Lock()
        self.logs = {}
        self.sequence = 0

    def send(self, project, kind, body):
        with self.lock:
            self.sequence += 1
            self.logs.setdefault(project, deque(maxlen=300)).append(
                (self.sequence, kind, body, monotonic()))

    def since(self, project, after):
        with self.lock:
            return [entry[:3] for entry in self.logs.get(project, ()) if entry[0] > after]


def filter_shape(query):
    if not isinstance(query, dict):
        return "[redacted]"
    out = {}
    for key, val in query.items():
        if key in SAFE_FIELDS or key in {"$expr", "$and", "$or", "$in", "$eq", "$gt", "$lt", "$ne", "$exists"}:
            if key == "project_id":
                out[key] = "[trusted project]"
            elif isinstance(val, list):
                out[key] = [filter_shape(x) if isinstance(x, dict) else "[value]" for x in val[:16]]
            elif isinstance(val, dict):
                out[key] = filter_shape(val)
            elif isinstance(val, str) and val in SAFE_VALUES:
                out[key] = val
            else:
                out[key] = "[value]"
    return out


def command_shape(name, cmd):
    out = {}
    if name == "aggregate":
        stages = []
        for stage in cmd.get("pipeline", []):
            for operator, value in stage.items():
                if operator == "$vectorSearch":
                    stages.append({operator: {
                        "index": value["index"], "path": value["path"],
                        "filter": filter_shape(value["filter"]), "exact": value.get("exact"),
                        "limit": value["limit"], "queryVector": f'[{len(value["queryVector"])} floats]',
                    }})
                elif operator == "$lookup":
                    stages.append({operator: {"from": value["from"], "as": value["as"],
                                               "pipeline": [
                                                   {"$match": filter_shape(step["$match"])}
                                                   if "$match" in step else {next(iter(step)): "[projection]"}
                                                   for step in value["pipeline"]]}})
                else:
                    stages.append({operator: list(value) if isinstance(value, dict) else value})
        out["pipeline"] = stages
    if name in {"find", "findAndModify"}:
        out["filter"] = filter_shape(cmd.get("filter", cmd.get("query", {})))
    if name == "insert":
        out["documents"] = len(cmd.get("documents", []))
    if name in {"update", "findAndModify"}:
        changes = cmd.get("updates", [{"q": cmd.get("query"), "u": cmd.get("update")}])
        out["updates"] = []
        for change in changes:
            raw = change.get("u")
            operators = raw if isinstance(raw, list) else [raw]
            fields = set()
            status = None
            for op in operators:
                if not isinstance(op, dict):
                    continue
                for values in op.values():
                    if isinstance(values, dict):
                        fields.update(k for k in values if k in SAFE_FIELDS)
                value = op.get("$set", {}).get("status")
                if isinstance(value, str) and value in SAFE_VALUES:
                    status = value
            out["updates"].append({"filter": filter_shape(change.get("q")), "fields": sorted(fields),
                                   "status": status})
    if "autocommit" in cmd:
        out["transaction"] = True
    return out


class Activity(CommandListener):
    def __init__(self, bus, database):
        self.bus, self.database = bus, database
        self.pending = {}
        self.lock = Lock()

    def started(self, event):
        project = scope.get()
        name = event.command_name
        if not project or name not in COMMANDS or event.database_name not in {self.database, "admin"}:
            return
        collection = event.command.get(name)
        if name == "getMore":
            collection = event.command.get("collection")
        if collection not in COLLECTIONS:
            if name not in {"commitTransaction", "abortTransaction"}:
                return
            collection = None
        key = (event.connection_id, event.request_id)
        with self.lock:
            self.pending[key] = (project, name, collection, command_shape(name, event.command))

    def succeeded(self, event):
        self.finish(event, True)

    def failed(self, event):
        self.finish(event, False)

    def finish(self, event, success):
        with self.lock:
            item = self.pending.pop((event.connection_id, event.request_id), None)
        if not item:
            return
        project, name, collection, shape = item
        reply = event.reply if success else {}
        cursor = reply.get("cursor", {})
        docs = len(cursor.get("firstBatch", cursor.get("nextBatch", []))) if cursor else (
            int(bool(reply.get("value"))) if name == "findAndModify" else reply.get("n"))
        success = success and not reply.get("writeErrors") and not reply.get("writeConcernError")
        self.bus.send(project, "atlas", {"command": name, "collection": collection,
                      "ms": round(event.duration_micros/1000, 2), "docs": docs, "shape": shape, "ok": success})
