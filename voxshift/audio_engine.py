from __future__ import annotations

from dataclasses import replace
from threading import Lock
from typing import Callable

import numpy as np

from .dsp import DSPSettings, VoiceDSP


class AudioEngine:
    def __init__(self) -> None:
        self._stream = None
        self._settings = DSPSettings()
        self._lock = Lock()
        self.input_level = 0.0
        self.output_level = 0.0
        self.last_status = "Stopped"
        self.on_status: Callable[[str], None] | None = None

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

    def start(self, input_device: int | None, output_device: int | None, sample_rate: int = 48000, blocksize: int = 256) -> None:
        if self._stream is not None:
            return

        import sounddevice as sd
        dsp = VoiceDSP(sample_rate=sample_rate, channels=1)

        def callback(indata, outdata, frames, time_info, status):
            if status:
                self.last_status = str(status)
            mono = indata[:, :1]
            self.input_level = float(np.sqrt(np.mean(np.square(mono), dtype=np.float64)))
            with self._lock:
                settings = self._settings
            processed = dsp.process(mono, settings)
            self.output_level = float(np.sqrt(np.mean(np.square(processed), dtype=np.float64)))
            if outdata.shape[1] == 1:
                outdata[:] = processed
            else:
                outdata[:] = np.repeat(processed, outdata.shape[1], axis=1)

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

    def stop(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()
        self.input_level = 0.0
        self.output_level = 0.0
        self._set_status("Stopped")
