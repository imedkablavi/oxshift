import unittest

import numpy as np

from voxshift.waveform import envelope_from_samples


class WaveformTests(unittest.TestCase):
    def test_envelope_shape_and_bounds(self):
        t = np.arange(48000, dtype=np.float32) / 48000.0
        x = 0.5 * np.sin(2 * np.pi * 440.0 * t)
        env = envelope_from_samples(x, points=600, sample_rate=48000)
        self.assertEqual(env.points, 600)
        self.assertEqual(env.minimum.shape, (600,))
        self.assertEqual(env.maximum.shape, (600,))
        self.assertAlmostEqual(env.duration_seconds, 1.0, places=3)
        self.assertTrue(np.all(env.minimum <= env.maximum))
        self.assertLessEqual(float(np.max(env.maximum)), 0.51)
        self.assertGreaterEqual(float(np.min(env.minimum)), -0.51)

    def test_empty_input_is_safe(self):
        env = envelope_from_samples(np.empty(0, dtype=np.float32), points=64, sample_rate=48000)
        self.assertEqual(env.points, 64)
        self.assertTrue(np.allclose(env.minimum, 0.0))
        self.assertTrue(np.allclose(env.maximum, 0.0))

    def test_stereo_is_collapsed(self):
        mono = np.linspace(-1.0, 1.0, 1024, dtype=np.float32)
        stereo = np.column_stack([mono, mono])
        env = envelope_from_samples(stereo, points=128, sample_rate=48000)
        self.assertEqual(env.points, 128)
        self.assertTrue(np.isfinite(env.minimum).all())
        self.assertTrue(np.isfinite(env.maximum).all())


if __name__ == "__main__":
    unittest.main()
