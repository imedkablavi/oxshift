import unittest


class UIImportTests(unittest.TestCase):
    def test_product_ui_imports_without_starting_tk(self):
        from voxshift.pro_ui import OxShiftStudioUI
        from voxshift.enhanced_ui import OxShiftEnhancedUI

        self.assertTrue(callable(OxShiftStudioUI))
        self.assertTrue(callable(OxShiftEnhancedUI))


if __name__ == "__main__":
    unittest.main()
