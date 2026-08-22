from __future__ import annotations

from dataclasses import replace
from threading import Lock
import time
from typing import Callable

import numpy as np

from .dsp import DSPSettings, VoiceDSP
from .recorder import OutputRecorder
from .rvc_runtime import RealtimeVoiceConverter
from .soundboard import SoundboardEngine


class AudioEngine:
    def __init__(self) -> None:
        self._stream = None
        self._settings = DSPSettings()
        self._lock = Lock()
        self.input_level = 0.0
        self.output_level = 0.0
        self.soundboard_level = 0.0
        self.last_status = "Stopped"
        self.on_status: Callable[[str], None] | None = None
        self.soundboard = SoundboardEngine(sample_rate=48000)
        self.voice_converter = RealtimeVoiceConverter()
        self.recorder = OutputRecorder(sample_rate=48000)
        self.sample_rate = 48000
        self.blocksize = 256
        self.callback_ms = 0.0
        self.callback_peak_ms = 0.0
        self.xruns = 0
        self.pitch_backend = "unknown"

    @staticmethod
    def devices():
        import sounddevice as sd
        return sd.query_devices()

    def update_settings(self, **kwargs) -> None:
        with self._lock:
            self._settings = replace(self._settings, **kwargs)

    def _set_status(self, text: str) -> None:
        self.last_status = text
        if self.on_status:
            self.on_status(text)

    def start_recording(self, path: str) -> bool:
        return self.recorder.start(path, sample_rate=self.sample_rate)

    def stop_recording(self):
        return self.recorder.stop()

    def start(
        self,
        input_device: int | None,
        output_device: int | None,
        sample_rate: int = 48000,
        blocksize: int = 256,
    ) -> None:
        if self._stream is not None:
            return
        if sample_rate not in {44100, 48000, 96000}:
            raise ValueError("sample_rate must be 44100, 48000 or 96000")
        if blocksize not in {128, 256, 512, 1024}:
            raise ValueError("blocksize must be 128, 256, 512 or 1024")

        import sounddevice as sd

        self.sample_rate = int(sample_rate)
        self.blocksize = int(blocksize)
        self.xruns = 0
        self.callback_peak_ms = 0.0
        if self.soundboard.sample_rate != self.sample_rate:
            self.soundboard.stop_all()
            self.soundboard.sample_rate = self.sample_rate
        self.recorder.sample_rate = self.sample_rate
        dsp = VoiceDSP(sample_rate=sample_rate, channels=1)
        self.pitch_backend = dsp.pitch_backend
        budget_ms = (blocksize / sample_rate) * 1000.0
        if self.voice_converter.config.enabled and self.voice_converter.ready:
            self.voice_converter.start()

        def callback(indata, outdata, frames, time_info, status):
            started = time.perf_counter()
            if status:
                self.last_status = str(status)
                self.xruns += 1

            mono = indata[:, :1]
            self.input_level = float(np.sqrt(np.mean(np.square(mono), dtype=np.float64)))
            with self._lock:
                settings = self._settings

            converted = self.voice_converter.process(mono)
            processed = dsp.process(converted, settings)
            board = self.soundboard.mix(frames)
            self.soundboard_level = float(np.sqrt(np.mean(np.square(board), dtype=np.float64)))

            if self.soundboard.is_playing and self.soundboard.settings.ducking_db > 0:
                duck_amp = float(10.0 ** (-self.soundboard.settings.ducking_db / 20.0))
                processed = processed * duck_amp

            final = np.clip(processed + board, -1.0, 1.0).astype(np.float32, copy=False)
            self.output_level = float(np.sqrt(np.mean(np.square(final), dtype=np.float64)))
            self.recorder.push(final)

            if outdata.shape[1] == 1:
                outdata[:] = final
            else:
                outdata[:] = np.repeat(final, outdata.shape[1], axis=1)

            elapsed_ms = (time.perf_counter() - started) * 1000.0
            self.callback_ms = elapsed_ms
            self.callback_peak_ms = max(self.callback_peak_ms * 0.995, elapsed_ms)
            if elapsed_ms > budget_ms:
                self.xruns += 1

        self._stream = sd.Stream(
            samplerate=sample_rate,
            blocksize=blocksize,
            device=(input_device, output_device),
            channels=(1, 1),
            dtype="float32",
            latency="low",
            callback=callback,
        )
        self._stream.start()
        self._set_status("Running")

    @property
    def estimated_buffer_latency_ms(self) -> float:
        return (self.blocksize / self.sample_rate) * 1000.0 if self.sample_rate else 0.0

    def stop(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()
        self.recorder.stop()
        self.voice_converter.stop()
        self.soundboard.stop_all()
        self.input_level = 0.0
        self.output_level = 0.0
        self.soundboard_level = 0.0
        self.callback_ms = 0.0
        self._set_status("Stopped")
