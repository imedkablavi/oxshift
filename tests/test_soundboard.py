import os
from pathlib import Path
import tempfile
import unittest

import numpy as np

from voxshift.soundboard import SoundboardEngine


class SoundboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_xdg = os.environ.get("XDG_CONFIG_HOME")
        os.environ["XDG_CONFIG_HOME"] = self.temp.name

    def tearDown(self):
        if self.old_xdg is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = self.old_xdg
        self.temp.cleanup()

    def test_empty_mix_is_silent_and_bounded(self):
        board = SoundboardEngine(48000)
        mixed = board.mix(256)
        self.assertEqual(mixed.shape, (256, 1))
        self.assertEqual(mixed.dtype, np.float32)
        self.assertTrue(np.allclose(mixed, 0.0))

    def test_import_is_persistent_and_deduplicated(self):
        audio = Path(self.temp.name) / "effect.wav"
        audio.write_bytes(b"not-decoded-during-import")
        board = SoundboardEngine(48000)
        added = board.add_files([str(audio), str(audio)])
        self.assertEqual(len(added), 1)
        self.assertEqual(len(board.items), 1)

        reloaded = SoundboardEngine(48000)
        self.assertEqual(len(reloaded.items), 1)
        self.assertEqual(reloaded.items[0].name, "effect")

    def test_rejects_unsupported_files(self):
        text = Path(self.temp.name) / "notes.txt"
        text.write_text("no audio")
        board = SoundboardEngine(48000)
        self.assertEqual(board.add_files([str(text)]), [])

    def test_settings_are_persistent(self):
        board = SoundboardEngine(48000)
        board.settings.master_volume = 0.42
        board.settings.ducking_db = 8.0
        board.settings.allow_overlap = False
        board.save()

        reloaded = SoundboardEngine(48000)
        self.assertAlmostEqual(reloaded.settings.master_volume, 0.42)
        self.assertAlmostEqual(reloaded.settings.ducking_db, 8.0)
        self.assertFalse(reloaded.settings.allow_overlap)


if __name__ == "__main__":
    unittest.main()
