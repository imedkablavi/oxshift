from __future__ import annotations

from dataclasses import dataclass, replace
from threading import Event, Lock, Thread, current_thread
import time
from typing import Callable

import numpy as np

from .audio_devices import DeviceIdentity, capture_identity, resolve_device_index
from .dsp import DSPSettings, VoiceDSP
from .recorder import OutputRecorder
from .rvc_runtime import RealtimeVoiceConverter
from .soundboard import SoundboardEngine
from .speech_processing import SpeechProcessingSettings, SpeechProcessor


@dataclass(frozen=True, slots=True)
class AudioStartRequest:
    input_device: DeviceIdentity
    output_device: DeviceIdentity
    sample_rate: int
    blocksize: int


class AudioEngine:
    def __init__(self) -> None:
        self._stream = None
        self._settings = DSPSettings()
        self._cleanup_settings = SpeechProcessingSettings()
        self._lock = Lock()
        self._stream_lock = Lock()
        self._recovery_stop = Event()
        self._recovery_wake = Event()
        self._recovery_thread: Thread | None = None
        self._manual_stop = True
        self._start_request: AudioStartRequest | None = None

        self.input_level = 0.0
        self.cleaned_level = 0.0
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
        self.callback_errors = 0
        self.recovery_attempts = 0
        self.recovery_successes = 0
        self.last_recovery_error = ""
        self.pitch_backend = "unknown"
        self.cleanup_backend = "builtin"
        self.cleanup_gain_db = 0.0
        self.noise_floor = 0.0
        self.speech_probability = 0.0
        self.cleanup_error = ""
        self._far_reference = np.empty((0, 1), dtype=np.float32)

    @staticmethod
    def devices():
        import sounddevice as sd
        return sd.query_devices()

    @property
    def running(self) -> bool:
        stream = self._stream
        if stream is None:
            return False
        try:
            return bool(stream.active)
        except Exception:
            return False

    def update_settings(self, **kwargs) -> None:
        with self._lock:
            self._settings = replace(self._settings, **kwargs)

    def update_cleanup(self, **kwargs) -> None:
        with self._lock:
            self._cleanup_settings = replace(self._cleanup_settings, **kwargs)
            self._cleanup_settings.sanitize()

    def set_far_reference(self, block: np.ndarray | None) -> None:
        """Provide speaker/far-end reference audio for future AEC use.

        AEC is intentionally not fed the virtual-mic output automatically: that is not the
        same signal as what the user's speakers actually reproduce. A monitor/output path can
        call this with the true speaker reference when available.
        """
        if block is None:
            self._far_reference = np.empty((0, 1), dtype=np.float32)
            return
        arr = np.asarray(block, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr[:, None]
        self._far_reference = np.ascontiguousarray(arr[:, :1], dtype=np.float32)

    def _set_status(self, text: str) -> None:
        self.last_status = text
        if self.on_status:
            self.on_status(text)

    def start_recording(self, path: str) -> bool:
        return self.recorder.start(path, sample_rate=self.sample_rate)

    def stop_recording(self):
        return self.recorder.stop()

    @staticmethod
    def _validate_format(sample_rate: int, blocksize: int) -> None:
        if sample_rate not in {44100, 48000, 96000}:
            raise ValueError("sample_rate must be 44100, 48000 or 96000")
        if blocksize not in {128, 256, 512, 1024}:
            raise ValueError("blocksize must be 128, 256, 512 or 1024")

    def start(
        self,
        input_device: int | None,
        output_device: int | None,
        sample_rate: int = 48000,
        blocksize: int = 256,
    ) -> None:
        self._validate_format(sample_rate, blocksize)
        with self._stream_lock:
            if self._stream is not None:
                return
            import sounddevice as sd

            devices = list(sd.query_devices())
            self._start_request = AudioStartRequest(
                input_device=capture_identity(devices, input_device),
                output_device=capture_identity(devices, output_device),
                sample_rate=int(sample_rate),
                blocksize=int(blocksize),
            )
            self._manual_stop = False
            self._recovery_stop.clear()
            self._recovery_wake.clear()
            self.xruns = 0
            self.callback_errors = 0
            self.callback_peak_ms = 0.0
            self.last_recovery_error = ""
            try:
                self._open_stream(sd, input_device, output_device, sample_rate, blocksize)
            except Exception:
                self._manual_stop = True
                self._start_request = None
                raise
        self._ensure_recovery_thread()
        self._set_status("Running")

    def _open_stream(self, sd, input_device, output_device, sample_rate: int, blocksize: int) -> None:
        self.sample_rate = int(sample_rate)
        self.blocksize = int(blocksize)
        if self.soundboard.sample_rate != self.sample_rate:
            self.soundboard.stop_all()
            self.soundboard.sample_rate = self.sample_rate
        self.recorder.sample_rate = self.sample_rate
        cleanup = SpeechProcessor(sample_rate=self.sample_rate)
        dsp = VoiceDSP(sample_rate=sample_rate, channels=1)
        self.pitch_backend = dsp.pitch_backend
        budget_ms = (blocksize / sample_rate) * 1000.0
        if self.voice_converter.config.enabled and self.voice_converter.ready:
            self.voice_converter.start()

        def finished_callback():
            # Never reopen devices from PortAudio's callback context. Wake the recovery worker.
            if not self._manual_stop:
                self._recovery_wake.set()

        def callback(indata, outdata, frames, time_info, status):
            started = time.perf_counter()
            try:
                if status:
                    self.last_status = str(status)
                    self.xruns += 1

                mono = indata[:, :1]
                self.input_level = float(np.sqrt(np.mean(np.square(mono), dtype=np.float64)))
                with self._lock:
                    settings = self._settings
                    cleanup_settings = self._cleanup_settings

                far = self._far_reference if self._far_reference.shape[0] == frames else None
                cleaned = cleanup.process(mono, cleanup_settings, far_reference=far)
                self.cleaned_level = cleanup.output_rms
                self.cleanup_gain_db = cleanup.applied_gain_db
                self.noise_floor = cleanup.noise_floor
                self.cleanup_backend = cleanup.backend
                self.speech_probability = cleanup.speech_probability
                self.cleanup_error = cleanup.last_error

                # This call only queues/copies blocks. Slow model inference stays on the VC worker.
                converted = self.voice_converter.process(cleaned)
                processed = dsp.process(converted, settings)
                # Soundboard mix only drains predecoded in-memory queues; no media disk I/O here.
                board = self.soundboard.mix(frames)
                self.soundboard_level = float(np.sqrt(np.mean(np.square(board), dtype=np.float64)))

                if self.soundboard.is_playing and self.soundboard.settings.ducking_db > 0:
                    duck_amp = float(10.0 ** (-self.soundboard.settings.ducking_db / 20.0))
                    processed = processed * duck_amp

                final = np.clip(processed + board, -1.0, 1.0).astype(np.float32, copy=False)
                self.output_level = float(np.sqrt(np.mean(np.square(final), dtype=np.float64)))
                # Recorder.push is a bounded queue write; WAV disk I/O runs on its worker thread.
                self.recorder.push(final)

                if outdata.shape[1] == 1:
                    outdata[:] = final
                else:
                    outdata[:] = np.repeat(final, outdata.shape[1], axis=1)
            except Exception:
                # Fail closed to silence and let the watchdog reopen the stream off callback.
                outdata.fill(0.0)
                self.callback_errors += 1
                self._recovery_wake.set()
            finally:
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                self.callback_ms = elapsed_ms
                self.callback_peak_ms = max(self.callback_peak_ms * 0.995, elapsed_ms)
                if elapsed_ms > budget_ms:
                    self.xruns += 1

        stream = sd.Stream(
            samplerate=sample_rate,
            blocksize=blocksize,
            device=(input_device, output_device),
            channels=(1, 1),
            dtype="float32",
            latency="low",
            callback=callback,
            finished_callback=finished_callback,
        )
        stream.start()
        self._stream = stream

    def _ensure_recovery_thread(self) -> None:
        worker = self._recovery_thread
        if worker is not None and worker.is_alive():
            return
        self._recovery_thread = Thread(target=self._recovery_loop, name="OxShiftAudioRecovery", daemon=True)
        self._recovery_thread.start()

    def request_recovery(self) -> None:
        """Request asynchronous stream recovery without blocking the caller."""
        if not self._manual_stop:
            self._recovery_wake.set()

    def _recovery_loop(self) -> None:
        while not self._recovery_stop.is_set():
            signaled = self._recovery_wake.wait(timeout=0.75)
            self._recovery_wake.clear()
            if self._manual_stop or self._recovery_stop.is_set():
                return

            stream = self._stream
            active = False
            if stream is not None:
                try:
                    active = bool(stream.active)
                except Exception:
                    active = False
            if active and not signaled:
                continue
            if active and signaled and self.callback_errors == 0:
                continue
            self._recover_stream()

    def _recover_stream(self) -> None:
        request = self._start_request
        if request is None or self._manual_stop:
            return
        import sounddevice as sd

        backoff = 0.25
        self._set_status("Recovering audio devices…")
        while not self._manual_stop and not self._recovery_stop.is_set():
            self.recovery_attempts += 1
            old_stream = None
            try:
                devices = list(sd.query_devices())
                input_index = resolve_device_index(devices, request.input_device, "input")
                output_index = resolve_device_index(devices, request.output_device, "output")
                if request.input_device.index is not None and input_index is None:
                    raise RuntimeError(f"input device not available: {request.input_device.name or request.input_device.index}")
                if request.output_device.index is not None and output_index is None:
                    raise RuntimeError(f"output device not available: {request.output_device.name or request.output_device.index}")

                with self._stream_lock:
                    old_stream, self._stream = self._stream, None
                    if old_stream is not None:
                        try:
                            old_stream.abort()
                        except Exception:
                            try:
                                old_stream.stop()
                            except Exception:
                                pass
                        try:
                            old_stream.close()
                        except Exception:
                            pass
                    self._open_stream(
                        sd,
                        input_index,
                        output_index,
                        request.sample_rate,
                        request.blocksize,
                    )
                self.recovery_successes += 1
                self.callback_errors = 0
                self.last_recovery_error = ""
                self._set_status("Running")
                return
            except Exception as exc:
                self.last_recovery_error = str(exc)
                self._set_status("Waiting for audio device…")
                if self._recovery_stop.wait(backoff):
                    return
                backoff = min(backoff * 2.0, 8.0)

    @property
    def estimated_buffer_latency_ms(self) -> float:
        return (self.blocksize / self.sample_rate) * 1000.0 if self.sample_rate else 0.0

    def stop(self) -> None:
        self._manual_stop = True
        self._recovery_stop.set()
        self._recovery_wake.set()
        worker, self._recovery_thread = self._recovery_thread, None
        if worker and worker.is_alive() and worker is not current_thread():
            worker.join(timeout=1.0)

        with self._stream_lock:
            stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
            except Exception:
                try:
                    stream.abort()
                except Exception:
                    pass
            finally:
                try:
                    stream.close()
                except Exception:
                    pass
        self._start_request = None
        self.recorder.stop()
        self.voice_converter.stop()
        self.soundboard.stop_all()
        self.input_level = 0.0
        self.cleaned_level = 0.0
        self.output_level = 0.0
        self.soundboard_level = 0.0
        self.callback_ms = 0.0
        self._far_reference = np.empty((0, 1), dtype=np.float32)
        self._set_status("Stopped")
