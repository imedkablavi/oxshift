import unittest

import numpy as np

from voxshift.cleanup import CleanupSettings, MicCleanup


class MicCleanupTests(unittest.TestCase):
    def test_silence_stays_finite_and_bounded(self):
        cleanup = MicCleanup(48000)
        y = cleanup.process(np.zeros((256, 1), dtype=np.float32), CleanupSettings())
        self.assertEqual(y.shape, (256, 1))
        self.assertTrue(np.isfinite(y).all())
        self.assertLessEqual(float(np.max(np.abs(y))), 1.0)

    def test_quiet_noise_is_reduced(self):
        cleanup = MicCleanup(48000)
        settings = CleanupSettings(noise_suppression=1.0, agc_enabled=False)
        x = np.full((256, 1), 0.002, dtype=np.float32)
        for _ in range(30):
            y = cleanup.process(x, settings)
        self.assertLess(float(np.sqrt(np.mean(y * y))), 0.001)

    def test_agc_lifts_soft_speech_without_clipping(self):
        cleanup = MicCleanup(48000)
        settings = CleanupSettings(noise_suppression=0.0, agc_enabled=True, agc_target_dbfs=-18.0, agc_max_gain_db=12.0)
        t = np.arange(256, dtype=np.float32) / 48000.0
        x = (0.03 * np.sin(2 * np.pi * 220 * t))[:, None].astype(np.float32)
        original = float(np.sqrt(np.mean(x * x)))
        y = x
        for _ in range(50):
            y = cleanup.process(x, settings)
        final = float(np.sqrt(np.mean(y * y)))
        self.assertGreater(final, original)
        self.assertLessEqual(float(np.max(np.abs(y))), 1.0)

    def test_settings_are_clamped(self):
        settings = CleanupSettings(noise_suppression=5, agc_target_dbfs=-100, agc_max_gain_db=50)
        settings.sanitize()
        self.assertEqual(settings.noise_suppression, 1.0)
        self.assertEqual(settings.agc_target_dbfs, -30.0)
        self.assertEqual(settings.agc_max_gain_db, 24.0)


if __name__ == "__main__":
    unittest.main()
