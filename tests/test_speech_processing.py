import unittest
from unittest import mock

import numpy as np

from voxshift.speech_processing import SpeechProcessingSettings, SpeechProcessor


class SpeechProcessingTests(unittest.TestCase):
    def setUp(self):
        t = np.arange(480, dtype=np.float32) / 48000.0
        self.block = (0.12 * np.sin(2 * np.pi * 220.0 * t))[:, None]

    def test_builtin_backend_is_safe(self):
        p = SpeechProcessor(48000)
        y = p.process(self.block, SpeechProcessingSettings(backend="builtin"))
        self.assertEqual(y.shape, self.block.shape)
        self.assertTrue(np.isfinite(y).all())
        self.assertLessEqual(float(np.max(np.abs(y))), 1.0)
        self.assertEqual(p.backend, "builtin")

    def test_invalid_backend_sanitizes_to_auto(self):
        s = SpeechProcessingSettings(backend="bad")
        s.sanitize()
        self.assertEqual(s.backend, "auto")

    def test_aec_without_far_reference_falls_back(self):
        p = SpeechProcessor(48000)
        with mock.patch.object(SpeechProcessor, "webrtc_available", return_value=True):
            y = p.process(
                self.block,
                SpeechProcessingSettings(backend="webrtc", echo_cancellation=True),
                far_reference=None,
            )
        self.assertEqual(y.shape, self.block.shape)
        self.assertEqual(p.backend, "builtin")
        self.assertIn("far-end reference", p.last_error)

    def test_webrtc_unavailable_falls_back_cleanly(self):
        p = SpeechProcessor(48000)
        with mock.patch.object(SpeechProcessor, "webrtc_available", return_value=False):
            y = p.process(self.block, SpeechProcessingSettings(backend="auto"))
        self.assertEqual(p.backend, "builtin")
        self.assertTrue(np.isfinite(y).all())

    def test_settings_are_clamped(self):
        s = SpeechProcessingSettings(noise_suppression=9, agc_target_dbfs=-100, agc_max_gain_db=100, stream_delay_ms=900)
        s.sanitize()
        self.assertEqual(s.noise_suppression, 1.0)
        self.assertEqual(s.agc_target_dbfs, -30.0)
        self.assertEqual(s.agc_max_gain_db, 50.0)
        self.assertEqual(s.stream_delay_ms, 500)


if __name__ == "__main__":
    unittest.main()
