import unittest

import numpy as np

from voxshift.dsp import DSPSettings, VoiceDSP
from voxshift.voices import CATEGORIES, VOICE_PRESETS, get_preset


class DSPTests(unittest.TestCase):
    def setUp(self):
        self.dsp = VoiceDSP(48000, 1)
        t = np.arange(4096, dtype=np.float32) / 48000.0
        self.x = (0.25 * np.sin(2 * np.pi * 220.0 * t))[:, None].astype(np.float32)

    def test_clean_shape_and_bounds(self):
        y = self.dsp.process(self.x, DSPSettings())
        self.assertEqual(y.shape, self.x.shape)
        self.assertTrue(np.isfinite(y).all())
        self.assertLessEqual(float(np.max(np.abs(y))), 1.0)

    def test_gate_silences_tiny_signal(self):
        x = np.full((128, 1), 1e-6, dtype=np.float32)
        y = self.dsp.process(x, DSPSettings(gate_db=-50))
        self.assertTrue(np.allclose(y, 0.0))

    def test_all_presets_are_finite_and_bounded(self):
        for preset in VOICE_PRESETS:
            self.dsp.reset()
            y = self.dsp.process(self.x, DSPSettings(preset=preset.name))
            self.assertTrue(np.isfinite(y).all(), preset.name)
            self.assertEqual(y.shape, self.x.shape, preset.name)
            self.assertLessEqual(float(np.max(np.abs(y))), 1.0, preset.name)

    def test_pitch_and_formant_color_are_safe(self):
        for pitch in (-12.0, -4.0, 0.0, 4.0, 12.0):
            self.dsp.reset()
            y = self.dsp.process(
                self.x,
                DSPSettings(pitch_semitones=pitch, formant_color=0.35),
            )
            self.assertEqual(y.shape, self.x.shape)
            self.assertTrue(np.isfinite(y).all())
            self.assertLessEqual(float(np.max(np.abs(y))), 1.0)

    def test_preset_catalog_is_unique(self):
        names = [preset.name for preset in VOICE_PRESETS]
        self.assertEqual(len(names), len(set(names)))
        self.assertGreaterEqual(len(VOICE_PRESETS), 12)
        self.assertIn("All", CATEGORIES)

    def test_unknown_preset_falls_back_to_clean(self):
        self.assertEqual(get_preset("does-not-exist").name, "Clean")

    def test_gain_clips_safely(self):
        y = self.dsp.process(np.ones((128, 1), dtype=np.float32), DSPSettings(gain_db=18))
        self.assertLessEqual(float(np.max(y)), 1.0)


if __name__ == "__main__":
    unittest.main()
