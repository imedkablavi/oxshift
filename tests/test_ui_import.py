import unittest


class UIImportTests(unittest.TestCase):
    def test_product_ui_imports_without_starting_tk(self):
        from voxshift.pro_ui import OxShiftStudioUI

        self.assertTrue(callable(OxShiftStudioUI))


if __name__ == "__main__":
    unittest.main()
