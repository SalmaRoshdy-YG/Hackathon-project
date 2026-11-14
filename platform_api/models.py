import math
import operator
import re
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, StringConstraints, field_validator, model_validator

from platform_api.config import utcnow

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1500)]
Tag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
ResultID = Annotated[str, StringConstraints(pattern=r"^[0-9a-f-]{36}$")]
Scalar = str | int | float | bool | None


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Conditions(Body):
    fixture_revision: Tag
    cohort: Tag
    codec: Tag
    dictionary_revision: Tag
    split: Tag | None = None


class Ref(Body):
    result_id: ResultID
    version: Annotated[int, Field(gt=0)]


class Metric(Body):
    name: Tag
    value: float | None
    unit: Tag
    operator: Literal["<=", ">=", "<", ">", "=="]
    threshold: float


class Evidence(Body):
    kind: Literal["job_receipt"]
    data: dict[str, JsonValue]

    @field_validator("data")
    @classmethod
    def keys_are_safe(cls, value):
        def inspect(obj, depth):
            if depth > 12:
                raise ValueError("evidence too deeply nested")
            if isinstance(obj, dict):
                for key, item in obj.items():
                    if not re.fullmatch(r"[a-zA-Z_][\w-]{0,79}", key):
                        raise ValueError("invalid evidence key")
                    inspect(item, depth + 1)
            if isinstance(obj, list):
                for item in obj:
                    inspect(item, depth + 1)
            if isinstance(obj, float) and not math.isfinite(obj):
                raise ValueError("invalid measurement")
        inspect(value, 0)
        return value


class Source(Body):
    system: Tag
    source_agent: Tag
    record: Tag


class Publish(Body):
    schema_version: Literal[1]
    hypothesis: Text
    fixture_revision: Tag
    conditions: dict[str, Scalar]
    configuration: dict[str, Scalar]
    metric: Metric
    execution: Literal["completed", "crashed", "timed_out"]
    validity: Literal["valid", "invalid", "inconclusive"]
    direction: Literal["positive", "negative", "undetermined"]
    evidence: Evidence
    source: Source
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def measured_direction(self):
        if self.expires_at <= utcnow():
            raise ValueError("new results must expire in the future")
        for mapping in (self.conditions, self.configuration):
            if len(mapping) > 32 or any(not re.fullmatch(r"[a-zA-Z_][\w-]{0,79}", k) for k in mapping):
                raise ValueError("invalid fields")
        if any(not isinstance(self.conditions.get(k), str) or not self.conditions[k].strip()
               for k in ["cohort", "codec", "dictionary_revision"]):
            raise ValueError("missing conditions")
        data = self.evidence.data
        if self.execution == "completed":
            reproduce = data.get("reproduce")
            if not isinstance(reproduce, dict) or not all(
                isinstance(reproduce.get(k), str) and reproduce[k] for k in
                ("command", "fixture_sha256", "zlib_version", "python_version")
            ) or "dictionary_sha256" not in reproduce:
                raise ValueError("missing reproduction metadata")
        if self.execution == "completed" and self.validity == "valid":
            if self.metric.value is None or not data.get("run_id"):
                raise ValueError("missing valid measurement")
            compare = {"<=": operator.le, ">=": operator.ge, "<": operator.lt, ">": operator.gt, "==": operator.eq}
            expected = "positive" if compare[self.metric.operator](self.metric.value, self.metric.threshold) else "negative"
        else:
            expected = "undetermined"
        if self.direction != expected:
            raise ValueError("invalid result direction")
        return self


class Search(Body):
    question: Text
    conditions: Conditions | None = None


class Resolve(Body):
    refs: list[Ref] = Field(max_length=32)


class Expire(Body):
    expected_version: Annotated[int, Field(gt=0)]
    reason: Text


class Correct(Expire):
    replacement: Publish


class Mismatch(Body):
    field: Tag
    wanted: Scalar
    found: Scalar


class Applicability(Body):
    status: Literal["applies", "mismatch"]
    mismatches: list[Mismatch] = Field(max_length=4)


class Candidate(Body):
    ref: Ref
    score: float = Field(ge=0, le=1)
    applicability: Applicability


class Skip(Body):
    job_id: Literal["plain-l1", "dict-a-l6", "dict-b-l6"]
    reason: Text
    refs: list[Ref] = Field(max_length=8)


class Rejected(Body):
    ref: Ref
    reason: Text


class Plan(Body):
    job_id: Literal["plain-l1", "dict-a-l6", "dict-b-l6"]
    used_refs: list[Ref] = Field(max_length=8)
    skipped_jobs: list[Skip] = Field(max_length=3)
    rejected_candidates: list[Rejected] = Field(max_length=8)
    reason: Text


class Proposal(Plan):
    request: Text
    memory: Literal["on", "off"]
    conditions: Conditions
    candidates: list[Candidate] = Field(max_length=8)
    model: Tag


class Approve(Body):
    note: Text = "Approved by presenter"


class Reject(Body):
    reason: Text = "Rejected by presenter"
