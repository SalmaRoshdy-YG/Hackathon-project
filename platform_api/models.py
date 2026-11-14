import math
import operator
import re
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, RootModel, StringConstraints, field_validator, model_validator

from platform_api.config import utcnow

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1500)]
Tag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
ResultID = Annotated[str, StringConstraints(pattern=r"^[0-9a-f-]{36}$")]
Scalar = str | int | float | bool | None
JobID = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$")]


def flat_fields(mapping):
    if len(mapping) > 32 or any(not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_-]{0,79}", key)
                                for key in mapping):
        raise ValueError("invalid field names")
    if any(type(value) is float and not math.isfinite(value) for value in mapping.values()):
        raise ValueError("invalid numeric condition")
    return mapping


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Conditions(RootModel[dict[str, Scalar]]):
    @field_validator("root")
    @classmethod
    def validate_conditions(cls, values):
        flat_fields(values)
        if not isinstance(values.get("fixture_revision"), str) or not values["fixture_revision"].strip():
            raise ValueError("missing fixture revision")
        return values


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
        flat_fields(self.conditions)
        flat_fields(self.configuration)
        data = self.evidence.data
        if self.execution == "completed":
            reproduce = data.get("reproduce")
            if not isinstance(reproduce, dict) or not all(
                isinstance(reproduce.get(k), str) and reproduce[k] for k in ("command", "fixture_sha256")
            ):
                raise ValueError("missing reproduction command or fixture hash")
            versions = reproduce.get("versions")
            if versions is None:
                versions = {k: v for k, v in reproduce.items() if k.endswith("_version")}
            if not isinstance(versions, dict) or not versions or any(
                    not isinstance(v, str) or not v.strip() for v in versions.values()):
                raise ValueError("missing runtime or library versions")
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
    mismatches: list[Mismatch] = Field(max_length=32)


class Candidate(Body):
    ref: Ref
    score: float = Field(ge=0, le=1)
    applicability: Applicability


class Skip(Body):
    job_id: JobID
    reason: Text
    refs: list[Ref] = Field(max_length=8)


class Rejected(Body):
    ref: Ref
    reason: Text


class Plan(Body):
    job_id: JobID
    used_refs: list[Ref] = Field(max_length=8)
    skipped_jobs: list[Skip] = Field(max_length=32)
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
