import math
import unittest

from voxshift.audio_probe import rms_to_dbfs


class AudioProbeTests(unittest.TestCase):
    def test_full_scale_is_zero_dbfs(self):
        self.assertAlmostEqual(rms_to_dbfs(1.0), 0.0, places=6)

    def test_half_scale_matches_expected_dbfs(self):
        self.assertAlmostEqual(rms_to_dbfs(0.5), 20.0 * math.log10(0.5), places=6)

    def test_zero_is_finite_and_very_quiet(self):
        value = rms_to_dbfs(0.0)
        self.assertTrue(math.isfinite(value))
        self.assertLess(value, -100.0)


if __name__ == "__main__":
    unittest.main()
