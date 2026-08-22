from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


@dataclass(slots=True)
class CleanupSettings:
    noise_suppression: float = 0.45
    agc_enabled: bool = True
    agc_target_dbfs: float = -18.0
    agc_max_gain_db: float = 12.0

    def sanitize(self) -> None:
        self.noise_suppression = float(np.clip(self.noise_suppression, 0.0, 1.0))
        self.agc_target_dbfs = float(np.clip(self.agc_target_dbfs, -30.0, -8.0))
        self.agc_max_gain_db = float(np.clip(self.agc_max_gain_db, 0.0, 24.0))


class MicCleanup:
    """Low-latency adaptive microphone cleanup for the realtime callback.

    This is intentionally lightweight and dependency-free. It estimates a slowly moving
    noise floor from low-energy blocks, applies a soft downward expander instead of a hard
    spectral gate, then applies smoothed automatic gain control. It is not marketed as
    acoustic echo cancellation or neural denoising; those remain optional future backends.
    """

    def __init__(self, sample_rate: int = 48000) -> None:
        self.sample_rate = int(sample_rate)
        self.noise_floor = 0.003
        self.agc_gain = 1.0
        self.input_rms = 0.0
        self.output_rms = 0.0
        self.applied_gain_db = 0.0

    @staticmethod
    def _rms(x: np.ndarray) -> float:
        return float(np.sqrt(np.mean(np.square(x), dtype=np.float64))) if x.size else 0.0

    def reset(self) -> None:
        self.noise_floor = 0.003
        self.agc_gain = 1.0
        self.input_rms = 0.0
        self.output_rms = 0.0
        self.applied_gain_db = 0.0

    def process(self, block: np.ndarray, settings: CleanupSettings) -> np.ndarray:
        x = np.asarray(block, dtype=np.float32)
        if x.ndim == 1:
            x = x[:, None]
        settings.sanitize()

        rms = self._rms(x)
        self.input_rms = rms

        # Learn room/noise floor only from relatively quiet blocks, with a very slow rise.
        if rms < max(self.noise_floor * 2.2, 0.02):
            alpha = 0.965 if rms < self.noise_floor else 0.995
            self.noise_floor = max(1e-5, alpha * self.noise_floor + (1.0 - alpha) * rms)

        strength = settings.noise_suppression
        if strength > 0.001:
            floor = max(self.noise_floor, 1e-5)
            ratio = rms / floor
            # Soft downward expansion: preserve speech transients and avoid binary gating.
            if ratio <= 1.0:
                attenuation = 1.0 - 0.92 * strength
            elif ratio < 3.2:
                t = (ratio - 1.0) / 2.2
                attenuation = (1.0 - 0.92 * strength) * (1.0 - t) + t
            else:
                attenuation = 1.0
            work = x * float(np.clip(attenuation, 0.05, 1.0))
        else:
            work = x

        if settings.agc_enabled:
            level = max(self._rms(work), 1e-6)
            target = 10.0 ** (settings.agc_target_dbfs / 20.0)
            desired = target / level
            max_gain = 10.0 ** (settings.agc_max_gain_db / 20.0)
            desired = float(np.clip(desired, 0.25, max_gain))
            # Fast attack when reducing gain, slower release when increasing it.
            coeff = 0.78 if desired < self.agc_gain else 0.965
            self.agc_gain = coeff * self.agc_gain + (1.0 - coeff) * desired
            work = work * self.agc_gain
        else:
            self.agc_gain = 1.0

        self.applied_gain_db = 20.0 * math.log10(max(self.agc_gain, 1e-6))
        out = np.clip(work, -1.0, 1.0).astype(np.float32, copy=False)
        self.output_rms = self._rms(out)
        return out
