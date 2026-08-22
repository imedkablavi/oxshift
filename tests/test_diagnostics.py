import json
import unittest

from voxshift.diagnostics import build_diagnostics, diagnostics_json


class _RecorderState:
    dropped_blocks = 3


class _Recorder:
    state = _RecorderState()


class _Stats:
    inference_ms = 8.5
    underruns = 2


class _Config:
    enabled = True


class _Converter:
    config = _Config()
    ready = True
    stats = _Stats()


class _Engine:
    last_status = "Running"
    sample_rate = 48000
    blocksize = 256
    estimated_buffer_latency_ms = 5.333
    callback_ms = 1.4
    callback_peak_ms = 2.7
    xruns = 1
    pitch_backend = "pedalboard"
    recorder = _Recorder()
    voice_converter = _Converter()


class DiagnosticsTests(unittest.TestCase):
    def test_snapshot_contains_health_without_device_names(self):
        devices = [
            {
                "name": "Private USB Microphone Name",
                "hostapi": 1,
                "max_input_channels": 2,
                "max_output_channels": 0,
                "default_samplerate": 48000,
            }
        ]
        snapshot = build_diagnostics(_Engine(), devices)
        self.assertEqual(snapshot["audio"]["xruns"], 1)
        self.assertEqual(snapshot["audio"]["vc_inference_ms"], 8.5)
        encoded = json.dumps(snapshot)
        self.assertNotIn("Private USB Microphone Name", encoded)

    def test_json_is_parseable(self):
        payload = diagnostics_json(_Engine(), [])
        parsed = json.loads(payload)
        self.assertEqual(parsed["schema"], 1)
        self.assertEqual(parsed["audio"]["sample_rate"], 48000)


if __name__ == "__main__":
    unittest.main()
