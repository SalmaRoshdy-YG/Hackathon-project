"""Trusted experiment contract. Profile modules are selected by the operator at startup."""
from dataclasses import dataclass
from importlib import import_module
import os
import re
from typing import Callable

from pydantic import TypeAdapter

from platform_api.models import Conditions, JobID, Tag

CONDITION_KEY = re.compile(r"[a-zA-Z_][a-zA-Z0-9_-]{0,79}")


@dataclass(frozen=True)
class Experiment:
    id: str
    catalog: tuple[str, ...]
    baseline: str
    match_fields: tuple[str, ...]
    validate_task: Callable[[dict], bool]
    supports: Callable[[str, dict], bool]
    measure: Callable[[str, dict], dict]

    def __post_init__(self):
        if TypeAdapter(Tag).validate_python(self.id) != self.id:
            raise ValueError("experiment id must not have surrounding whitespace")
        job = TypeAdapter(JobID)
        if not self.catalog or len(self.catalog) > 33 or len(set(self.catalog)) != len(self.catalog):
            raise ValueError("invalid experiment catalog")
        for entry in self.catalog:
            job.validate_python(entry)
        if self.baseline not in self.catalog:
            raise ValueError("experiment baseline must be a registered job")
        fields = self.match_fields
        if ("fixture_revision" not in fields or len(fields) > 32 or len(set(fields)) != len(fields)
                or any(not CONDITION_KEY.fullmatch(name) for name in fields)):
            raise ValueError("invalid experiment match fields")

    def missing_conditions(self, conditions: Conditions):
        return set(self.match_fields).difference(conditions.root)


def experiment():
    module = os.getenv("MEMORY_EXPERIMENT_MODULE")
    if not module:
        return None
    selected = import_module(module).EXPERIMENT
    if not isinstance(selected, Experiment):
        raise TypeError("configured EXPERIMENT must be an Experiment")
    return selected
