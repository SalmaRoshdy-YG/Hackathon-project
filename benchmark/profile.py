"""Compression experiment and presenter entry points."""
import zlib

from benchmark.agent import planner_name
from benchmark.publish import replacement
from benchmark.run import CATALOG, FIXTURE, TASK, measure, QUESTION
from platform_api.profile import Experiment, Presentation


def valid_task(conditions):
    return (conditions.get("fixture_revision") == FIXTURE and conditions.get("codec") == TASK["codec"]
            and conditions.get("cohort") in ("A", "B")
            and conditions.get("dictionary_revision") == TASK["dictionary_revision"]
            and conditions.get("split") == "holdout")


FAMILIES = {"dict-a-l6": "A", "dict-b-l6": "B"}


def supports(job, finding):
    return finding["configuration"].get("dictionary_family") == FAMILIES[job]


def run_job(job, conditions):
    return measure(job, conditions["cohort"], conditions["split"])


EXPERIMENT = Experiment("compression-v1", CATALOG, "plain-l1",
    ("fixture_revision", "cohort", "codec", "dictionary_revision"), valid_task, supports, run_job)

PRESENTATION = Presentation(QUESTION, TASK, "benchmark.publish", "benchmark.agent",
    replacement, lambda: {"planner": planner_name(), "zlib_version": zlib.ZLIB_RUNTIME_VERSION})
