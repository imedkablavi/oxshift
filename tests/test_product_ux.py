from pathlib import Path
import tempfile
import unittest

from voxshift.app_prefs import AppPreferencesStore
from voxshift.product_ui import looks_like_virtual_output, route_readiness


class ProductUxTests(unittest.TestCase):
    def test_virtual_output_detection_covers_supported_routes(self):
        self.assertTrue(looks_like_virtual_output("VoxShift Microphone"))
        self.assertTrue(looks_like_virtual_output("CABLE Input (VB-Audio Virtual Cable)"))
        self.assertTrue(looks_like_virtual_output("VoiceMeeter Input"))
        self.assertFalse(looks_like_virtual_output("Built-in Speakers"))

    def test_route_readiness_is_explicit(self):
        state = route_readiness("USB Mic", "CABLE Input", True)
        self.assertTrue(state["input"])
        self.assertTrue(state["output"])
        self.assertTrue(state["virtual"])
        self.assertTrue(state["running"])

        missing = route_readiness("", "Built-in Speakers", False)
        self.assertFalse(missing["input"])
        self.assertTrue(missing["output"])
        self.assertFalse(missing["virtual"])
        self.assertFalse(missing["running"])

    def test_preferences_are_atomic_and_sanitized(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "ui.json"
            store = AppPreferencesStore(path)
            store.state.onboarding_complete = True
            store.state.last_page = "Soundboard"
            store.state.window_geometry = "99999x10+4000+4000"
            store.save()

            loaded = AppPreferencesStore(path)
            self.assertTrue(loaded.state.onboarding_complete)
            self.assertEqual(loaded.state.last_page, "Soundboard")
            self.assertEqual(loaded.state.window_geometry, "3000x680")

    def test_invalid_page_falls_back_to_home(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "ui.json"
            path.write_text('{"last_page":"NotARealPage","window_geometry":"bad"}', encoding="utf-8")
            loaded = AppPreferencesStore(path)
            self.assertEqual(loaded.state.last_page, "Home")
            self.assertEqual(loaded.state.window_geometry, "1320x820")


if __name__ == "__main__":
    unittest.main()
