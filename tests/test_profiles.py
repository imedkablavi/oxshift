from pathlib import Path
import tempfile
import unittest

from voxshift.profiles import ProfileStore


class ProfileStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "profiles.json"

    def tearDown(self):
        self.temp.cleanup()

    def test_default_profile_created(self):
        store = ProfileStore(self.path)
        self.assertEqual(len(store.items), 1)
        self.assertEqual(store.active.name, "Default")

    def test_clone_and_reload(self):
        store = ProfileStore(self.path)
        store.update_active(
            voice="Robot",
            pitch_semitones=5.0,
            soundboard_duck_db=8.0,
            noise_suppression=0.72,
            agc_enabled=False,
            input_device_name="USB Mic",
            output_device_name="OxShift Virtual Sink",
        )
        clone = store.create("Gaming")
        self.assertEqual(clone.voice, "Robot")
        self.assertEqual(clone.pitch_semitones, 5.0)

        reloaded = ProfileStore(self.path)
        self.assertEqual(len(reloaded.items), 2)
        self.assertEqual(reloaded.active.name, "Gaming")
        self.assertEqual(reloaded.active.voice, "Robot")
        self.assertAlmostEqual(reloaded.active.noise_suppression, 0.72)
        self.assertFalse(reloaded.active.agc_enabled)
        self.assertEqual(reloaded.active.input_device_name, "USB Mic")
        self.assertEqual(reloaded.active.output_device_name, "OxShift Virtual Sink")

    def test_values_are_clamped(self):
        store = ProfileStore(self.path)
        profile = store.update_active(
            gain_db=500,
            wet=-10,
            pitch_semitones=99,
            formant_color=-3,
            noise_suppression=9,
            agc_target_dbfs=-100,
            agc_max_gain_db=100,
            soundboard_master=9,
            soundboard_duck_db=100,
            sample_rate=12345,
            blocksize=7,
        )
        self.assertEqual(profile.gain_db, 24.0)
        self.assertEqual(profile.wet, 0.0)
        self.assertEqual(profile.pitch_semitones, 12.0)
        self.assertEqual(profile.formant_color, -1.0)
        self.assertEqual(profile.noise_suppression, 1.0)
        self.assertEqual(profile.agc_target_dbfs, -30.0)
        self.assertEqual(profile.agc_max_gain_db, 24.0)
        self.assertEqual(profile.soundboard_master, 1.5)
        self.assertEqual(profile.soundboard_duck_db, 36.0)
        self.assertEqual(profile.sample_rate, 48000)
        self.assertEqual(profile.blocksize, 256)

    def test_cannot_delete_last_profile(self):
        store = ProfileStore(self.path)
        self.assertFalse(store.delete(store.active.id))


if __name__ == "__main__":
    unittest.main()
