import unittest

import numpy as np

from voxshift.dsp import DSPSettings, VoiceDSP


class DSPTests(unittest.TestCase):
    def setUp(self):
        self.dsp = VoiceDSP(48000, 1)
        self.x = np.linspace(-0.4, 0.4, 512, dtype=np.float32)[:, None]

    def test_clean_shape_and_bounds(self):
        y = self.dsp.process(self.x, DSPSettings())
        self.assertEqual(y.shape, self.x.shape)
        self.assertTrue(np.isfinite(y).all())
        self.assertLessEqual(float(np.max(np.abs(y))), 1.0)

    def test_gate_silences_tiny_signal(self):
        x = np.full((128, 1), 1e-6, dtype=np.float32)
        y = self.dsp.process(x, DSPSettings(gate_db=-50))
        self.assertTrue(np.allclose(y, 0.0))

    def test_presets_are_finite(self):
        for preset in ("Radio", "Robot", "Anonymous"):
            y = self.dsp.process(self.x, DSPSettings(preset=preset))
            self.assertTrue(np.isfinite(y).all(), preset)
            self.assertEqual(y.shape, self.x.shape)

    def test_gain_clips_safely(self):
        y = self.dsp.process(np.ones((128, 1), dtype=np.float32), DSPSettings(gain_db=18))
        self.assertLessEqual(float(np.max(y)), 1.0)


if __name__ == "__main__":
    unittest.main()
