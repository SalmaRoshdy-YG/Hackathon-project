import json
from datetime import timedelta
from uuid import uuid4

from fastapi import HTTPException
from pymongo import MongoClient, ReturnDocument, ASCENDING
from pymongo.errors import OperationFailure
from pymongo.operations import SearchIndexModel

from platform_api.activity import Activity
from platform_api.artifacts import Artifacts
from platform_api.config import utcnow
from platform_api.embedding import DIMENSIONS, embed, index_name, model

KEEP = timedelta(days=1)
PUBLIC = ("schema_version", "hypothesis", "fixture_revision", "conditions", "configuration", "metric",
          "execution", "validity", "direction", "source", "expires_at", "author_id", "version")


def error(code, detail):
    raise HTTPException(code, detail)


def literal(x):
    return {"$literal": x}


def active():
    return {"$gt": ["$expires_at", "$$NOW"]}


def public(doc):
    return {**{k: doc[k] for k in PUBLIC}, "result_id": doc.get("result_id", doc["_id"]),
            "artifact": doc.get("artifact"),
            "status": doc.get("status", "current")}


def conditions_pairs(conditions, match_fields, prefix="$"):
    for field in match_fields:
        path = field if field == "fixture_revision" else "conditions."+field
        yield field, conditions.root[field], prefix+path


def live_filter(project, result_id, version=None, *, usable=False, conditions=None, match_fields=()):
    query = {"_id": result_id, "project_id": project, "$expr": active()}
    if version is not None:
        query["version"] = version
    if usable:
        query.update(execution="completed", validity="valid")
    if conditions is not None:
        query["$expr"] = {"$and": [active(), *(
            {"$and": [{"$ne": [{"$type": path}, "missing"]}, {"$eq": [path, literal(value)]}]}
            for _, value, path in conditions_pairs(conditions, match_fields))]}
    return query


def applicability_stages(conditions, match_fields, prefix="$"):
    fields = [{"field": name, "wanted": literal(wanted), "found": {"$ifNull": [path, None]},
               "missing": {"$eq": [{"$type": path}, "missing"]}}
              for name, wanted, path in conditions_pairs(conditions, match_fields, prefix)]
    return [{"$set": {"mismatches": {"$map": {
        "input": {"$filter": {"input": fields, "as": "entry", "cond": {"$or": [
            "$$entry.missing", {"$ne": ["$$entry.wanted", "$$entry.found"]}]}}},
        "as": "entry", "in": {"field": "$$entry.field", "wanted": "$$entry.wanted", "found": "$$entry.found"},
        }}}}, {"$set": {"applicability": {"status": {"$cond": [
            {"$eq": [{"$size": "$mismatches"}, 0]}, "applies", "mismatch"]}, "mismatches": "$mismatches"}}}]


class Store:
    def __init__(self, uri, database, bus=None):
        kwargs = {"event_listeners": [Activity(bus, database)]} if bus else {}
        self.client = MongoClient(uri, tz_aware=True, timeoutMS=15000, serverSelectionTimeoutMS=7500, **kwargs)
        self.db = self.client[database]
        self.artifacts = Artifacts(self.db)

    def setup(self):
        for name in ("results", "result_versions", "result_vectors"):
            self.db[name].create_index("purge_at", expireAfterSeconds=0)
        for name in ("results", "decisions"):
            self.db[name].create_index([("project_id", ASCENDING), ("updated_at", ASCENDING)])
        self.db.result_versions.create_index([("project_id", ASCENDING), ("result_id", ASCENDING),
                                               ("version", ASCENDING)], unique=True)
        self.db.result_vectors.create_index("project_id")
        self.ensure_search()

    def ensure_search(self):
        name = index_name()
        definition = {"fields": [{"type": "vector", "path": "embedding", "numDimensions": DIMENSIONS,
                                   "similarity": "cosine"}, {"type": "filter", "path": "project_id"}, {"type": "filter", "path": "embedding_model"}]}
        if not list(self.db.result_vectors.list_search_indexes(name)):
            try:
                self.db.result_vectors.create_search_index(SearchIndexModel(
                    definition=definition, name=name, type="vectorSearch"))
            except OperationFailure:
                if not list(self.db.result_vectors.list_search_indexes(name)):
                    raise

    def index_state(self):
        info = next(iter(self.db.result_vectors.list_search_indexes(index_name())), {})
        return "READY" if info.get("queryable") and info.get("status") == "READY" else info.get("status", "MISSING")

    def head(self, identity, result_id):
        doc = self.db.results.find_one({"_id": result_id, "project_id": identity.project_id})
        if not doc:
            error(404, "result_not_found")
        return doc

    def visible(self, identity, result_id, version=None):
        result = self.db.results.find_one(live_filter(identity.project_id, result_id, version))
        if not result:
            error(404, "result_not_found")
        return result

    def all_heads(self, identity):
        return list(self.db.results.aggregate([
            {"$match": {"project_id": identity.project_id}},
            {"$set": {"status": {"$cond": [active(), "current", "expired"]}}},
            {"$project": {"evidence": 0}}, {"$sort": {"updated_at": -1, "_id": 1}},
        ]))

    def history(self, identity, result_id):
        # A single snapshot also makes history consistent during concurrent correction.
        with self.client.start_session(snapshot=True) as session:
            docs = self.db.results.aggregate([
                {"$match": {"_id": result_id, "project_id": identity.project_id}},
                {"$set": {"status": {"$cond": [active(), "current", "expired"]}}},
                {"$lookup": {"from": "result_versions", "as": "history",
                             "localField": "_id", "foreignField": "result_id",
                             "pipeline": [{"$match": {"project_id": identity.project_id}},
                                          {"$sort": {"version": 1}}]}},
            ], session=session)
            head = next(iter(docs), None)
        if not head:
            error(404, "result_not_found")
        versions = [{"version": old["version"], "state": "superseded", "result": public(old),
                     "evidence": old["evidence"], "replaced_at": old["replaced_at"],
                     "replaced_by": old["replaced_by"], "reason": old["reason"]} for old in head["history"]]
        versions.append({"version": head["version"], "state": head["status"],
                         "result": public(head), "evidence": head["evidence"]})
        return {"result_id": result_id, "current_version": head["version"],
                "status": head["status"], "versions": versions, "events": head["events"]}

    def stage(self, identity, payload, result_id, version):
        purge = payload["expires_at"] + KEEP
        if (payload["execution"], payload["validity"]) != ("completed", "valid"):
            return None
        key = str(uuid4())
        context = json.dumps({"measurement": payload["metric"], "fixture": payload["fixture_revision"],
                              "conditions": payload["conditions"]}, sort_keys=True)
        vector = embed(payload["hypothesis"] + "\n" + context)
        self.db.result_vectors.insert_one({"_id": key, "project_id": identity.project_id,
            "result_id": result_id, "version": version, "embedding": vector,
            "embedding_model": model(), "purge_at": purge})
        return key

    def publish(self, identity, body):
        if identity.role not in {"maintainer", "publisher"}:
            error(403, "publish_denied")
        payload = body.model_dump()
        if body.artifact:
            self.artifacts.check(identity, body.artifact)
        result_id = str(uuid4())
        search_key = self.stage(identity, payload, result_id, 1)
        now = utcnow()
        self.db.results.insert_one({**payload, "_id": result_id, "project_id": identity.project_id,
            "author_id": identity.agent_id, "version": 1, "search_key": search_key,
            "purge_at": payload["expires_at"] + KEEP, "updated_at": now,
            "events": [{"at": now, "action": "publish", "actor": identity.agent_id, "version": 1,
                        "reason": "Initial publication"}]})
        return {"result_id": result_id, "version": 1}

    def writable(self, identity, result_id, version):
        doc = self.head(identity, result_id)
        if identity.role != "maintainer" and not (
            identity.role == "publisher" and doc["author_id"] == identity.agent_id
        ):
            error(403, "governance_denied")
        if doc["version"] != version or doc["expires_at"] <= utcnow():
            error(409, "result_changed_or_expired")
        return doc

    def correct(self, identity, result_id, body):
        self.writable(identity, result_id, body.expected_version)
        version = body.expected_version + 1
        payload = body.replacement.model_dump()
        key = self.stage(identity, payload, result_id, version)
        query = live_filter(identity.project_id, result_id, body.expected_version)
        def write(session):
            now = utcnow()
            old = self.db.results.find_one(query, session=session)
            if not old:
                error(409, "result_changed_or_expired")
            event = {"at": now, "action": "correct", "actor": identity.agent_id,
                     "version": version, "reason": body.reason}
            archived = {**old, "_id": f"{result_id}:{old['version']}", "result_id": result_id,
                        "replaced_at": now, "replaced_by": identity.agent_id, "reason": body.reason}
            self.db.result_versions.insert_one(archived, session=session)
            changed = self.db.results.update_one(query, {"$set": {**payload,
                "version": version, "search_key": key, "updated_at": now,
                "purge_at": payload["expires_at"] + KEEP}, "$push": {"events": event}}, session=session)
            if changed.modified_count != 1:
                error(409, "result_changed_or_expired")
        with self.client.start_session() as session:
            session.with_transaction(write)
        return {"result_id": result_id, "version": version}

    def expire(self, identity, result_id, body):
        self.writable(identity, result_id, body.expected_version)
        doc = self.db.results.find_one_and_update(live_filter(identity.project_id, result_id, body.expected_version), [
            {"$set": {"expires_at": "$$NOW", "updated_at": "$$NOW",
                      "purge_at": {"$dateAdd": {"startDate": "$$NOW", "unit": "hour", "amount": 24}},
                      "events": {"$concatArrays": ["$events", [{"at": "$$NOW", "action": "expire",
                          "actor": literal(identity.agent_id), "version": body.expected_version,
                          "reason": literal(body.reason)}]]}}},
        ], return_document=ReturnDocument.AFTER)
        if not doc:
            error(409, "result_changed_or_expired")
        return {"result_id": result_id, "version": body.expected_version, "expired": True}

    def search_pipeline(self, project, vector, conditions, match_fields=()):
        joins = [{"$eq": ["$_id", "$$id"]}, {"$eq": ["$project_id", literal(project)]},
                 {"$eq": ["$version", "$$version"]}, {"$eq": ["$search_key", "$$key"]}, active(),
                 {"$eq": ["$execution", "completed"]}, {"$eq": ["$validity", "valid"]}]
        vector_stage = {"index": index_name(), "path": "embedding", "queryVector": vector,
                        "filter": {"project_id": project, "embedding_model": model()}, "exact": True, "limit": 12}
        pipeline = [
            {"$vectorSearch": vector_stage},
            {"$set": {"score": {"$meta": "vectorSearchScore"}}},
            {"$lookup": {"from": "results", "let": {"id": "$result_id", "version": "$version", "key": "$_id"},
                         "as": "head", "pipeline": [{"$match": {"$expr": {"$and": joins}}},
                                                    {"$project": {**dict.fromkeys(PUBLIC, 1), "_id": 1, "artifact": 1}}]}},
            {"$unwind": "$head"},
        ]
        if conditions is None:
            pipeline.append({"$set": {"applicability": literal(None)}})
        else:
            pipeline += applicability_stages(conditions, match_fields, "$head.")
        return pipeline + [{"$limit": 8}, {"$project": {"_id": 0, "head": 1, "score": 1, "applicability": 1}}]

    def search(self, identity, body, match_fields):
        vector = embed(body.question, query=True)
        pipeline = self.search_pipeline(identity.project_id, vector, body.conditions, match_fields)
        return [{"result": public(d["head"]), "score": d["score"], "applicability": d["applicability"]}
                for d in self.db.result_vectors.aggregate(pipeline)]

    def candidates_for(self, identity, refs, conditions, match_fields):
        if not refs:
            return []
        branches = [live_filter(identity.project_id, ref.result_id, ref.version, usable=True)
                    for ref in refs]
        cursor = self.db.results.aggregate([{"$match": {"$or": branches}},
            {"$project": {"evidence": 0, "events": 0}}, *applicability_stages(conditions, match_fields)])
        return self.order(cursor, refs)

    @staticmethod
    def order(cursor, refs):
        docs = {(d["_id"], d["version"]): d for d in cursor}
        if any((ref.result_id, ref.version) not in docs for ref in refs):
            error(404, "unusable_reference")
        return [docs[ref.result_id, ref.version] for ref in refs]

    def resolve(self, identity, refs, conditions=None, match_fields=()):
        if not refs:
            return []
        # Use one database read and one time base for every cited version.
        branches = [live_filter(identity.project_id, ref.result_id, ref.version, usable=True,
                                conditions=conditions, match_fields=match_fields) for ref in refs]
        cursor = self.db.results.find({"$or": branches}, {"evidence": 0})
        return [public(doc) for doc in self.order(cursor, refs)]
