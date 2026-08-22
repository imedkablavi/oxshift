import unittest

from voxshift.device_routing import resolve_device


class DeviceRoutingTests(unittest.TestCase):
    def test_exact_saved_device_wins(self):
        items = [(2, "USB Microphone"), (5, "Built-in Audio")]
        result = resolve_device(items, "USB Microphone")
        self.assertEqual(result.index, 2)
        self.assertTrue(result.exact)

    def test_virtual_output_is_preferred(self):
        items = [(1, "Speakers"), (7, "OxShift Virtual Sink")]
        result = resolve_device(items, "", virtual_output=True)
        self.assertEqual(result.index, 7)

    def test_name_similarity_survives_suffix_change(self):
        items = [(4, "USB Microphone Analog Stereo"), (8, "Webcam Mic")]
        result = resolve_device(items, "USB Microphone")
        self.assertEqual(result.index, 4)
        self.assertFalse(result.exact)

    def test_no_devices_returns_none(self):
        result = resolve_device([], "anything")
        self.assertIsNone(result.index)


if __name__ == "__main__":
    unittest.main()
