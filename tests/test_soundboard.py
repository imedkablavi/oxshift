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

    def _add_dummy(self):
        audio = Path(self.temp.name) / "effect.wav"
        audio.write_bytes(b"not-decoded-during-import")
        board = SoundboardEngine(48000)
        item = board.add_files([str(audio)])[0]
        return board, item

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

    def test_non_destructive_edit_metadata_persists(self):
        board, item = self._add_dummy()
        board.update_item(
            item.id,
            volume=1.25,
            trim_start=1.5,
            trim_end=7.25,
            fade_in=0.4,
            fade_out=0.8,
            loop=True,
        )
        reloaded = SoundboardEngine(48000)
        edited = reloaded.items[0]
        self.assertAlmostEqual(edited.volume, 1.25)
        self.assertAlmostEqual(edited.trim_start, 1.5)
        self.assertAlmostEqual(edited.trim_end, 7.25)
        self.assertAlmostEqual(edited.fade_in, 0.4)
        self.assertAlmostEqual(edited.fade_out, 0.8)
        self.assertTrue(edited.loop)

    def test_edit_values_are_clamped(self):
        board, item = self._add_dummy()
        edited = board.update_item(item.id, volume=99, trim_start=-2, fade_in=-1, fade_out=-4)
        self.assertIsNotNone(edited)
        self.assertEqual(edited.volume, 2.0)
        self.assertEqual(edited.trim_start, 0.0)
        self.assertEqual(edited.fade_in, 0.0)
        self.assertEqual(edited.fade_out, 0.0)


if __name__ == "__main__":
    unittest.main()
