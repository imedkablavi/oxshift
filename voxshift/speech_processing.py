from __future__ import annotations

from dataclasses import dataclass
import importlib.util

import numpy as np

from .cleanup import CleanupSettings, MicCleanup


@dataclass(slots=True)
class SpeechProcessingSettings:
    backend: str = "auto"
    noise_suppression: float = 0.45
    agc_enabled: bool = True
    agc_target_dbfs: float = -18.0
    agc_max_gain_db: float = 12.0
    echo_cancellation: bool = False
    stream_delay_ms: int = 0

    def sanitize(self) -> None:
        if self.backend not in {"auto", "builtin", "webrtc"}:
            self.backend = "auto"
        self.noise_suppression = float(np.clip(self.noise_suppression, 0.0, 1.0))
        self.agc_target_dbfs = float(np.clip(self.agc_target_dbfs, -30.0, -8.0))
        self.agc_max_gain_db = float(np.clip(self.agc_max_gain_db, 0.0, 50.0))
        self.stream_delay_ms = int(np.clip(self.stream_delay_ms, 0, 500))


class SpeechProcessor:
    """Selectable realtime speech-cleanup backend.

    WebRTC is optional. If it is not installed or cannot be initialized, OxShift falls
    back to the built-in adaptive processor. Echo cancellation is only enabled when a
    same-length far-end reference is supplied; silently pretending AEC works without a
    reference would be incorrect.
    """

    def __init__(self, sample_rate: int = 48000) -> None:
        self.sample_rate = int(sample_rate)
        self._builtin = MicCleanup(sample_rate=self.sample_rate)
        self._webrtc = None
        self._webrtc_signature: tuple | None = None
        self.backend = "builtin"
        self.last_error = ""
        self.speech_probability = 0.0
        self.applied_gain_db = 0.0
        self.noise_floor = 0.0
        self.output_rms = 0.0

    @staticmethod
    def webrtc_available() -> bool:
        return importlib.util.find_spec("pywebrtc_audio") is not None

    def reset(self) -> None:
        self._builtin.reset()
        if self._webrtc is not None:
            try:
                self._webrtc.reset()
            except Exception:
                pass
        self.speech_probability = 0.0
        self.applied_gain_db = 0.0
        self.noise_floor = 0.0
        self.output_rms = 0.0

    @staticmethod
    def _rms(x: np.ndarray) -> float:
        return float(np.sqrt(np.mean(np.square(x), dtype=np.float64))) if x.size else 0.0

    def _build_webrtc(self, settings: SpeechProcessingSettings) -> bool:
        if self.sample_rate not in {16000, 32000, 48000}:
            self.last_error = f"WebRTC backend does not support {self.sample_rate} Hz"
            return False
        try:
            from pywebrtc_audio import AudioProcessor

            ns_level = int(np.clip(round(settings.noise_suppression * 3.0), 0, 3))
            signature = (
                self.sample_rate,
                ns_level,
                bool(settings.agc_enabled),
                bool(settings.echo_cancellation),
                round(settings.agc_max_gain_db, 2),
                int(settings.stream_delay_ms),
            )
            if self._webrtc is None or signature != self._webrtc_signature:
                self._webrtc = AudioProcessor(
                    sample_rate=self.sample_rate,
                    num_channels=1,
                    echo_cancellation=bool(settings.echo_cancellation),
                    noise_suppression=settings.noise_suppression > 0.001,
                    high_pass_filter=True,
                    auto_gain_control=bool(settings.agc_enabled),
                    ns_level=ns_level,
                    agc_gain_db=0.0,
                    agc_max_gain_db=float(settings.agc_max_gain_db),
                    stream_delay_ms=int(settings.stream_delay_ms),
                )
                self._webrtc_signature = signature
            return True
        except Exception as exc:
            self.last_error = str(exc)
            self._webrtc = None
            self._webrtc_signature = None
            return False

    def process(
        self,
        block: np.ndarray,
        settings: SpeechProcessingSettings,
        far_reference: np.ndarray | None = None,
    ) -> np.ndarray:
        settings.sanitize()
        x = np.asarray(block, dtype=np.float32)
        if x.ndim == 2:
            x = x[:, 0]
        x = np.ascontiguousarray(x, dtype=np.float32)

        wants_webrtc = settings.backend == "webrtc" or (settings.backend == "auto" and self.webrtc_available())
        can_aec = not settings.echo_cancellation or (
            far_reference is not None and np.asarray(far_reference).size == x.size
        )

        if wants_webrtc and can_aec and self._build_webrtc(settings):
            try:
                far = None
                if settings.echo_cancellation:
                    far = np.ascontiguousarray(np.asarray(far_reference, dtype=np.float32).reshape(-1))
                out = self._webrtc.process(x, far)
                out = np.asarray(out, dtype=np.float32).reshape(-1, 1)
                self.backend = "webrtc"
                self.speech_probability = float(getattr(self._webrtc, "speech_probability", 0.0) or 0.0)
                self.applied_gain_db = float(getattr(self._webrtc, "gain_db", 0.0) or 0.0)
                self.noise_floor = 0.0
                self.output_rms = self._rms(out)
                self.last_error = ""
                return np.clip(out, -1.0, 1.0).astype(np.float32, copy=False)
            except Exception as exc:
                self.last_error = str(exc)

        # Built-in fallback maps the shared user controls to the lightweight processor.
        fallback = CleanupSettings(
            noise_suppression=settings.noise_suppression,
            agc_enabled=settings.agc_enabled,
            agc_target_dbfs=settings.agc_target_dbfs,
            agc_max_gain_db=min(settings.agc_max_gain_db, 24.0),
        )
        out = self._builtin.process(x[:, None], fallback)
        self.backend = "builtin"
        if settings.echo_cancellation and not can_aec:
            self.last_error = "AEC requested but no valid far-end reference is available"
        self.applied_gain_db = self._builtin.applied_gain_db
        self.noise_floor = self._builtin.noise_floor
        self.output_rms = self._builtin.output_rms
        self.speech_probability = 0.0
        return out
