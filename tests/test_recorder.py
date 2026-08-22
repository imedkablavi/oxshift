from pathlib import Path
import tempfile
import time
import unittest
import wave

import numpy as np

from voxshift.recorder import OutputRecorder


class RecorderTests(unittest.TestCase):
    def test_writes_pcm16_wav(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.wav"
            recorder = OutputRecorder(sample_rate=48000, queue_blocks=16)
            self.assertTrue(recorder.start(path))
            block = np.linspace(-0.25, 0.25, 480, dtype=np.float32)[:, None]
            for _ in range(5):
                recorder.push(block)
            state = recorder.stop()

            self.assertTrue(path.exists())
            self.assertEqual(state.frames_written, 2400)
            self.assertEqual(state.error, "")
            with wave.open(str(path), "rb") as wav:
                self.assertEqual(wav.getnchannels(), 1)
                self.assertEqual(wav.getsampwidth(), 2)
                self.assertEqual(wav.getframerate(), 48000)
                self.assertEqual(wav.getnframes(), 2400)

    def test_start_is_idempotent_while_recording(self):
        with tempfile.TemporaryDirectory() as tmp:
            recorder = OutputRecorder()
            path = Path(tmp) / "one.wav"
            self.assertTrue(recorder.start(path))
            self.assertFalse(recorder.start(Path(tmp) / "two.wav"))
            recorder.stop()

    def test_push_while_idle_is_safe(self):
        recorder = OutputRecorder()
        recorder.push(np.zeros((256, 1), dtype=np.float32))
        self.assertFalse(recorder.state.recording)
        self.assertEqual(recorder.state.frames_written, 0)


if __name__ == "__main__":
    unittest.main()
