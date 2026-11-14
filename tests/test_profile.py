import os
import unittest
from unittest.mock import patch

from platform_api.profile import experiment
from tests.lookup_profile import EXPERIMENT


class ProfileTests(unittest.TestCase):
    def test_core_does_not_load_a_default_experiment(self):
        with patch.dict(os.environ, {"MEMORY_EXPERIMENT_MODULE": ""}):
            self.assertIsNone(experiment())

    def test_explicit_runner_is_loaded(self):
        with patch.dict(os.environ, {"MEMORY_EXPERIMENT_MODULE": "tests.lookup_profile"}):
            self.assertIs(experiment(), EXPERIMENT)
