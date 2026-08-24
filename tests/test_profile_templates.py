import unittest

from voxshift.profile_templates import PROFILE_TEMPLATES, template_settings, unique_profile_name


class ProfileTemplateTests(unittest.TestCase):
    def test_common_templates_exist(self):
        self.assertIn("Gaming", PROFILE_TEMPLATES)
        self.assertIn("Streaming", PROFILE_TEMPLATES)
        self.assertIn("Calls", PROFILE_TEMPLATES)
        for settings in PROFILE_TEMPLATES.values():
            self.assertEqual(settings["sample_rate"], 48000)
            self.assertIn(settings["blocksize"], {128, 256, 512, 1024})

    def test_template_settings_returns_copy(self):
        first = template_settings("Gaming")
        first["gain_db"] = 99
        self.assertNotEqual(template_settings("Gaming")["gain_db"], 99)

    def test_unique_profile_name_is_case_insensitive(self):
        self.assertEqual(unique_profile_name(["Gaming"], "Gaming"), "Gaming 2")
        self.assertEqual(unique_profile_name(["gaming", "Gaming 2"], "Gaming"), "Gaming 3")
        self.assertEqual(unique_profile_name([], "Calls"), "Calls")


if __name__ == "__main__":
    unittest.main()
