import unittest

from voxshift.audio_devices import DeviceIdentity, capture_identity, preflight_stream_format, resolve_device_index


DEVICES = [
    {"name": "Built-in Speakers", "hostapi": 0, "max_input_channels": 0, "max_output_channels": 2},
    {"name": "USB Mic", "hostapi": 0, "max_input_channels": 1, "max_output_channels": 0},
    {"name": "CABLE Input", "hostapi": 0, "max_input_channels": 0, "max_output_channels": 2},
]


class _FakeSoundDevice:
    def __init__(self, fail_input=False, fail_output=False):
        self.fail_input = fail_input
        self.fail_output = fail_output
        self.calls = []

    def check_input_settings(self, **kwargs):
        self.calls.append(("input", kwargs))
        if self.fail_input:
            raise RuntimeError("unsupported input")

    def check_output_settings(self, **kwargs):
        self.calls.append(("output", kwargs))
        if self.fail_output:
            raise RuntimeError("unsupported output")


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

    def test_preflight_checks_both_sides_with_requested_rate(self):
        fake = _FakeSoundDevice()
        preflight_stream_format(fake, input_device=1, output_device=2, sample_rate=48000)
        self.assertEqual([kind for kind, _ in fake.calls], ["input", "output"])
        self.assertEqual(fake.calls[0][1]["samplerate"], 48000)
        self.assertEqual(fake.calls[1][1]["channels"], 1)

    def test_preflight_labels_input_and_output_failures(self):
        with self.assertRaisesRegex(ValueError, "input microphone"):
            preflight_stream_format(_FakeSoundDevice(fail_input=True), input_device=1, output_device=2, sample_rate=48000)
        with self.assertRaisesRegex(ValueError, "output/virtual route"):
            preflight_stream_format(_FakeSoundDevice(fail_output=True), input_device=1, output_device=2, sample_rate=48000)


if __name__ == "__main__":
    unittest.main()
