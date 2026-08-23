import os
from pathlib import Path
import tempfile
import unittest

from voxshift.playlists import PlaylistController
from voxshift.soundboard import SoundboardEngine


class PlaylistTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_xdg = os.environ.get("XDG_CONFIG_HOME")
        os.environ["XDG_CONFIG_HOME"] = self.temp.name
        self.audio = Path(self.temp.name) / "effect.wav"
        self.audio.write_bytes(b"catalog-only")
        self.board = SoundboardEngine(48000)
        self.item = self.board.add_files([str(self.audio)])[0]

    def tearDown(self):
        if self.old_xdg is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = self.old_xdg
        self.temp.cleanup()

    def test_create_add_move_and_persist(self):
        playlists = PlaylistController(self.board)
        playlists.create("Stream")
        self.assertTrue(playlists.add(self.item.id))
        self.assertFalse(playlists.add(self.item.id))

        reloaded = PlaylistController(self.board)
        reloaded.select("Stream")
        self.assertEqual(reloaded.active.item_ids, [self.item.id])

    def test_prune_removed_sounds(self):
        playlists = PlaylistController(self.board)
        playlists.add(self.item.id)
        self.board.remove(self.item.id)
        playlists.prune_missing()
        self.assertEqual(playlists.active.item_ids, [])

    def test_duplicate_playlist_names_are_rejected_case_insensitively(self):
        playlists = PlaylistController(self.board)
        playlists.create("Gaming")
        with self.assertRaises(ValueError):
            playlists.create("gaming")


if __name__ == "__main__":
    unittest.main()
