"""Guided browser configuration for the optional compression example."""
from zlib import ZLIB_RUNTIME_VERSION

from benchmark.agent import planner_name
from benchmark.publish import replacement
from benchmark.run import QUESTION, TASK
from demo.profile import Presentation


PRESENTATION = Presentation(QUESTION, TASK, "benchmark.publish", "benchmark.agent",
    replacement, lambda: {"planner": planner_name(), "zlib_version": ZLIB_RUNTIME_VERSION})
