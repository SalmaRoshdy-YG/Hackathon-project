"""Atomic approval and one dispatch for each decision."""
from uuid import uuid4

from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import PyMongoError

from platform_api.models import Proposal
from platform_api.config import utcnow
from platform_api.store import error


def outward(doc):
    return {**{key: value for key, value in doc.items() if key not in {"_id", "claim_id"}},
            "decision_id": doc["_id"]}


def key(ref):
    return (ref.result_id, ref.version)


def citations(plan):
    return list({key(ref): ref for ref in [*plan.used_refs, *(r for s in plan.skipped_jobs for r in s.refs)]}.values())


class Decisions:
    def __init__(self, store, experiment):
        self.experiment = experiment
        self.store = store
        self.collection = store.db.decisions

    def lookup(self, identity, decision_id):
        return {"_id": decision_id, "project_id": identity.project_id}

    def get(self, identity, decision_id):
        record = self.collection.find_one(self.lookup(identity, decision_id))
        if not record:
            error(404, "decision_not_found")
        return record

    def latest(self, identity):
        q = {"project_id": identity.project_id}
        return [outward(doc) for doc in self.collection.find(q).sort("created_at", -1).limit(40)]

    def execution_profile(self):
        if self.experiment is None:
            error(409, "experiment_runner_not_configured")
        return self.experiment

    def propose(self, identity, body):
        experiment = self.execution_profile()
        if (body.job_id not in experiment.catalog
                or any(skip.job_id not in experiment.catalog for skip in body.skipped_jobs)):
            error(422, "unknown_experiment_job")
        refs = citations(body)
        seen = {key(c.ref) for c in body.candidates}
        if (len(seen) != len(body.candidates) or len({key(r) for r in body.used_refs}) != len(body.used_refs)
                or len({s.job_id for s in body.skipped_jobs}) != len(body.skipped_jobs)
                or body.job_id in {s.job_id for s in body.skipped_jobs}
                or any(key(r.ref) not in seen for r in body.rejected_candidates)
                or any(key(r) not in seen for r in refs)
                or (body.memory == "off" and (refs or seen or body.job_id != experiment.baseline))
                or (body.job_id != experiment.baseline and not body.used_refs)):
            error(422, "invalid_decision_evidence")
        c = body.conditions
        if experiment.missing_conditions(c) or not experiment.validate_task(c.root):
            error(422, "unsupported_task_conditions")
        try:
            # Recompute applicability in MongoDB, including candidates that will only be shown in the trace.
            candidate_docs = self.store.candidates_for(identity, [row.ref for row in body.candidates], c,
                                                       experiment.match_fields)
        except HTTPException as exc:
            if exc.status_code == 404:
                error(422, "invalid_decision_evidence")
            raise
        by_ref = {key(candidate.ref): doc for candidate, doc in zip(body.candidates, candidate_docs)}
        if any(by_ref[key(ref)]["applicability"]["status"] != "applies" for ref in refs):
            error(422, "invalid_decision_evidence")
        if body.job_id != experiment.baseline:
            if not any(by_ref[key(ref)]["direction"] == "positive" and
                       experiment.supports(body.job_id, by_ref[key(ref)])
                       for ref in body.used_refs):
                error(422, "selected_job_lacks_support")
        for candidate, doc in zip(body.candidates, candidate_docs):
            if candidate.applicability.model_dump() != doc["applicability"]:
                error(422, "invalid_applicability")
        now = utcnow()
        record = {**body.model_dump(), "_id": str(uuid4()), "project_id": identity.project_id,
                  "proposed_by": identity.agent_id, "status": "pending", "created_at": now,
                  "updated_at": now, "catalog": list(experiment.catalog), "budget": 1, "experiment_id": experiment.id}
        self.collection.insert_one(record)
        return outward(record)

    def review(self, identity, decision_id, status, body):
        self.get(identity, decision_id)
        if identity.role != "maintainer":
            error(403, "approval_denied")
        fields = {"note": body.note} if status == "approved" else {"rejection_reason": body.reason}
        changed = self.collection.find_one_and_update(
            {**self.lookup(identity, decision_id), "status": "pending"},
            {"$set": {"status": status, "decided_by": identity.agent_id, "decided_at": utcnow(),
                      "updated_at": utcnow(), **fields}}, return_document=ReturnDocument.AFTER)
        if not changed:
            error(409, "decision_not_pending")
        return outward(changed)

    def can_dispatch(self, identity, decision_id):
        doc = self.get(identity, decision_id)
        if doc["proposed_by"] != identity.agent_id and identity.role != "maintainer":
            error(403, "execution_denied")
        if doc["status"] != "approved":
            error(409, "decision_not_approved")
        return doc

    def dispatch(self, identity, decision_id):
        existing = self.can_dispatch(identity, decision_id)
        experiment = self.execution_profile()
        if (existing.get("experiment_id") != experiment.id
                or existing["catalog"] != list(experiment.catalog)):
            error(409, "decision_experiment_changed")
        plan = Proposal.model_validate({field: existing[field] for field in Proposal.model_fields})
        if experiment.missing_conditions(plan.conditions) or not experiment.validate_task(plan.conditions.root):
            error(409, "decision_experiment_changed")
        claim = str(uuid4())
        query = self.lookup(identity, decision_id)
        claimed = self.collection.find_one_and_update({**query, "status": "approved"},
            {"$set": {"status": "running", "claim_id": claim, "updated_at": utcnow()}},
            return_document=ReturnDocument.AFTER)
        if not claimed:
            error(409, "decision_not_approved")

        try:
            # No intervening caller round trip between the authoritative read and job dispatch.
            self.store.resolve(identity, citations(plan), plan.conditions, experiment.match_fields)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            return self.finish(query, claim, "aborted", {"abort_reason": "cited_evidence_no_longer_usable"})
        except PyMongoError:
            self.finish(query, claim, "aborted", {"abort_reason": "evidence_recheck_unavailable"})
            raise

        try:
            measured = experiment.measure(plan.job_id, plan.conditions.root)
        except Exception:
            return self.finish(query, claim, "aborted", {"abort_reason": "runner_failed"})
        receipt = {**measured, "decision_id": decision_id, "request": plan.request,
                   "memory": plan.memory, "model": plan.model, "catalog": claimed["catalog"],
                   "experiment_id": experiment.id,
                   "budget": claimed["budget"], "used_refs": claimed["used_refs"],
                   "skipped_jobs": claimed["skipped_jobs"], "candidates": claimed["candidates"],
                   "rejected_candidates": claimed["rejected_candidates"], "reason": plan.reason,
                   "approval": {"by": claimed["decided_by"], "at": claimed["decided_at"],
                                "note": claimed.get("note")}}
        return self.finish(query, claim, "executed", {"receipt": receipt})

    def finish(self, query, claim, status, payload):
        changed = self.collection.find_one_and_update({**query, "status": "running", "claim_id": claim},
            {"$set": {"status": status, "updated_at": utcnow(), **payload}, "$unset": {"claim_id": ""}},
            return_document=ReturnDocument.AFTER)
        if not changed:
            error(409, "execution_claim_lost")
        return outward(changed)
