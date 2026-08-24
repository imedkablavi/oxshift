import tempfile
import unittest
from pathlib import Path

import numpy as np

from voxshift.dsp import DSPSettings, VoiceDSP
from voxshift.mixer_ui import EQ_PRESETS
from voxshift.profiles import ProfileStore, StudioProfile


class MixerEQTests(unittest.TestCase):
    def test_eq_catalog_has_safe_five_band_values(self):
        self.assertIn("Flat", EQ_PRESETS)
        self.assertIn("Deep", EQ_PRESETS)
        self.assertIn("Broadcast", EQ_PRESETS)
        for values in EQ_PRESETS.values():
            self.assertEqual(len(values), 5)
            self.assertTrue(all(-12.0 <= value <= 12.0 for value in values))

    def test_eq_is_finite_bounded_and_changes_tone(self):
        dsp = VoiceDSP(48000, 1)
        if dsp.eq_backend == "disabled":
            self.skipTest("pedalboard EQ backend unavailable")
        t = np.arange(8192, dtype=np.float32) / 48000.0
        low_tone = (0.08 * np.sin(2 * np.pi * 80.0 * t))[:, None].astype(np.float32)

        flat = dsp.process(low_tone, DSPSettings(eq_enabled=True, eq_bands_db=(0, 0, 0, 0, 0)))
        dsp.reset()
        boosted = dsp.process(low_tone, DSPSettings(eq_enabled=True, eq_bands_db=(10, 0, 0, 0, 0)))

        self.assertEqual(flat.shape, boosted.shape)
        self.assertTrue(np.isfinite(boosted).all())
        self.assertLessEqual(float(np.max(np.abs(boosted))), 1.0)
        self.assertGreater(float(np.sqrt(np.mean(np.square(boosted)))), float(np.sqrt(np.mean(np.square(flat)))) * 1.2)

    def test_extreme_eq_values_are_clamped_by_dsp(self):
        dsp = VoiceDSP(48000, 1)
        x = np.full((512, 1), 0.1, dtype=np.float32)
        y = dsp.process(x, DSPSettings(eq_bands_db=(100, -100, 80, -80, 50)))
        self.assertTrue(np.isfinite(y).all())
        self.assertLessEqual(float(np.max(np.abs(y))), 1.0)

    def test_profile_sanitizes_equalizer(self):
        profile = StudioProfile(
            id="one",
            name="Test",
            eq_enabled=1,
            eq_80_db=99,
            eq_250_db=-99,
            eq_1000_db=7,
            eq_4000_db=-7,
            eq_12000_db=22,
        )
        profile.sanitize()
        self.assertTrue(profile.eq_enabled)
        self.assertEqual(profile.eq_80_db, 12.0)
        self.assertEqual(profile.eq_250_db, -12.0)
        self.assertEqual(profile.eq_12000_db, 12.0)

    def test_profile_store_round_trips_equalizer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profiles.json"
            store = ProfileStore(path=path)
            store.update_active(
                eq_enabled=True,
                eq_80_db=4.0,
                eq_250_db=2.0,
                eq_1000_db=-1.0,
                eq_4000_db=3.5,
                eq_12000_db=1.5,
            )
            loaded = ProfileStore(path=path).active
            self.assertTrue(loaded.eq_enabled)
            self.assertEqual(
                (loaded.eq_80_db, loaded.eq_250_db, loaded.eq_1000_db, loaded.eq_4000_db, loaded.eq_12000_db),
                (4.0, 2.0, -1.0, 3.5, 1.5),
            )


if __name__ == "__main__":
    unittest.main()
