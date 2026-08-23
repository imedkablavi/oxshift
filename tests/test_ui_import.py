import unittest


class UIImportTests(unittest.TestCase):
    def test_alpha_product_ui_imports_without_starting_tk(self):
        from voxshift.alpha_ui import OxShiftAlphaUI
        from voxshift.pro_ui import OxShiftStudioUI

        self.assertTrue(callable(OxShiftAlphaUI))
        self.assertTrue(issubclass(OxShiftAlphaUI, OxShiftStudioUI))

    def test_legacy_ui_modules_remain_importable_for_rollback_only(self):
        from voxshift.enhanced_ui import OxShiftEnhancedUI
        from voxshift.advanced_ui import OxShiftAdvancedUI, WaveformEditor

        self.assertTrue(callable(OxShiftEnhancedUI))
        self.assertTrue(callable(OxShiftAdvancedUI))
        self.assertTrue(callable(WaveformEditor))


if __name__ == "__main__":
    unittest.main()
