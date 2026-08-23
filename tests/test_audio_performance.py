import unittest

from voxshift.audio_performance import PERFORMANCE_PRESETS, latency_ms, validate_audio_format


class AudioPerformanceTests(unittest.TestCase):
    def test_balanced_preset_matches_default_engine_format(self):
        self.assertEqual(PERFORMANCE_PRESETS["Balanced"], (48000, 256))

    def test_latency_math(self):
        self.assertAlmostEqual(latency_ms(48000, 256), 5.3333333333, places=5)
        self.assertAlmostEqual(latency_ms(48000, 128), 2.6666666666, places=5)

    def test_supported_formats_validate(self):
        self.assertEqual(validate_audio_format(44100, 512), (44100, 512))
        self.assertEqual(validate_audio_format(96000, 1024), (96000, 1024))

    def test_unsupported_formats_fail(self):
        with self.assertRaises(ValueError):
            validate_audio_format(22050, 256)
        with self.assertRaises(ValueError):
            validate_audio_format(48000, 64)


if __name__ == "__main__":
    unittest.main()
