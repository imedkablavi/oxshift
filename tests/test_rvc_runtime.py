import json
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np

from voxshift.rvc_runtime import PassthroughAdapter, RVCManifest, RealtimeVoiceConverter, RuntimeConfig


class RVCRuntimeTests(unittest.TestCase):
    def test_manifest_load_and_validate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "oxshift-rvc.json"
            manifest_path.write_text(json.dumps({"name": "Demo", "sample_rate": 40000}), encoding="utf-8")
            manifest = RVCManifest.load(manifest_path)
            self.assertEqual(manifest.name, "Demo")
            self.assertEqual(set(manifest.validate_files(root)), {"synthesizer", "content_encoder", "pitch_estimator"})

    def test_manifest_rejects_invalid_rate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.json"
            path.write_text(json.dumps({"name": "Bad", "sample_rate": 12345}), encoding="utf-8")
            with self.assertRaises(ValueError):
                RVCManifest.load(path)

    def test_disabled_runtime_is_transparent(self):
        runtime = RealtimeVoiceConverter(PassthroughAdapter(), RuntimeConfig(enabled=False))
        x = np.linspace(-0.4, 0.4, 256, dtype=np.float32)[:, None]
        y = runtime.process(x)
        np.testing.assert_allclose(y, x)

    def test_worker_never_returns_invalid_audio(self):
        runtime = RealtimeVoiceConverter(PassthroughAdapter(), RuntimeConfig(enabled=True))
        x = np.linspace(-0.4, 0.4, 256, dtype=np.float32)[:, None]
        try:
            runtime.start()
            for _ in range(20):
                y = runtime.process(x)
                self.assertEqual(y.shape, x.shape)
                self.assertTrue(np.isfinite(y).all())
                self.assertLessEqual(float(np.max(np.abs(y))), 1.0)
                time.sleep(0.005)
            self.assertGreater(runtime.stats.submitted_blocks, 0)
            self.assertGreater(runtime.stats.converted_blocks, 0)
        finally:
            runtime.stop()


if __name__ == "__main__":
    unittest.main()
