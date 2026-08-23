import unittest

from voxshift.audio_devices import DeviceIdentity, capture_identity, resolve_device_index


DEVICES = [
    {"name": "Built-in Speakers", "hostapi": 0, "max_input_channels": 0, "max_output_channels": 2},
    {"name": "USB Mic", "hostapi": 0, "max_input_channels": 1, "max_output_channels": 0},
    {"name": "CABLE Input", "hostapi": 0, "max_input_channels": 0, "max_output_channels": 2},
]


class AudioDeviceResolutionTests(unittest.TestCase):
    def test_capture_identity_keeps_stable_fields(self):
        identity = capture_identity(DEVICES, 1)
        self.assertEqual(identity, DeviceIdentity(1, "USB Mic", 0))

    def test_reconnect_resolves_by_name_after_index_changes(self):
        identity = capture_identity(DEVICES, 1)
        reordered = [
            {"name": "Webcam Mic", "hostapi": 0, "max_input_channels": 1, "max_output_channels": 0},
            {"name": "Built-in Speakers", "hostapi": 0, "max_input_channels": 0, "max_output_channels": 2},
            {"name": "USB Mic", "hostapi": 0, "max_input_channels": 1, "max_output_channels": 0},
        ]
        self.assertEqual(resolve_device_index(reordered, identity, "input"), 2)

    def test_wrong_direction_is_rejected(self):
        identity = DeviceIdentity(2, "CABLE Input", 0)
        self.assertIsNone(resolve_device_index(DEVICES, identity, "input"))
        self.assertEqual(resolve_device_index(DEVICES, identity, "output"), 2)

    def test_missing_named_device_does_not_bind_to_unusable_old_index(self):
        identity = DeviceIdentity(1, "USB Mic", 0)
        only_outputs = [
            {"name": "Speakers", "hostapi": 0, "max_input_channels": 0, "max_output_channels": 2},
            {"name": "Headphones", "hostapi": 0, "max_input_channels": 0, "max_output_channels": 2},
        ]
        self.assertIsNone(resolve_device_index(only_outputs, identity, "input"))


if __name__ == "__main__":
    unittest.main()
