from io import BytesIO
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from experiments import resnet
from platform_api.config import Identity


class CheckpointTests(unittest.TestCase):
    def test_corrupt_gridfs_stream_is_rejected_before_training(self):
        data = b"corrupt checkpoint"
        artifacts = Mock()
        artifacts.open.return_value = BytesIO(data)
        store = SimpleNamespace(artifacts=artifacts)
        identity = Identity("verification", "reader", "reader")
        source = {"configuration": {"job_id": "reuse"}, "direction": "positive", "conditions": {"split": "calibration"},
                  "artifact": {"filename": "input.safetensors", "bytes": len(data), "sha256": "0" * 64}}
        with patch.object(resnet, "train") as train:
            with self.assertRaisesRegex(ValueError, "checkpoint hash mismatch"):
                resnet.measure("reuse", {}, store, identity, [source])
            train.assert_not_called()
        artifacts.open.assert_called_once()
        artifacts.put.assert_not_called()
