"""Configuration for the optional guided browser workflow."""
from dataclasses import dataclass
from importlib import import_module
import os
from typing import Callable

from platform_api.models import Conditions


@dataclass(frozen=True)
class Presentation:
    question: str
    conditions: dict
    producer_module: str
    agent_module: str
    replacement: Callable[[], dict]
    environment: Callable[[], dict]


def presentation(experiment):
    if experiment is None:
        raise ValueError("set MEMORY_EXPERIMENT_MODULE before starting the presenter")
    module = os.getenv("MEMORY_PRESENTATION_MODULE") or os.environ["MEMORY_EXPERIMENT_MODULE"]
    selected = import_module(module).PRESENTATION
    if not isinstance(selected, Presentation) or not selected.question.strip():
        raise ValueError("invalid presenter profile")
    conditions = Conditions.model_validate(selected.conditions)
    if experiment.missing_conditions(conditions) or not experiment.validate_task(conditions.root):
        raise ValueError("presenter task does not match the experiment profile")
    return selected
