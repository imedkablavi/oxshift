import unittest

from voxshift.hotkey_syntax import normalize_hotkey


class HotkeySyntaxTests(unittest.TestCase):
    def test_accepts_expected_pynput_shapes(self):
        self.assertEqual(normalize_hotkey("<F8>"), "<f8>")
        self.assertEqual(normalize_hotkey("<CTRL>+<ALT>+1"), "<ctrl>+<alt>+1")
        self.assertEqual(normalize_hotkey("<shift>+a"), "<shift>+a")

    def test_empty_disables_hotkey(self):
        self.assertEqual(normalize_hotkey("  "), "")

    def test_rejects_spaces_and_duplicate_tokens(self):
        with self.assertRaises(ValueError):
            normalize_hotkey("<ctrl> + 1")
        with self.assertRaises(ValueError):
            normalize_hotkey("<ctrl>+<ctrl>+1")

    def test_rejects_broken_separator(self):
        with self.assertRaises(ValueError):
            normalize_hotkey("<ctrl>++1")


if __name__ == "__main__":
    unittest.main()
