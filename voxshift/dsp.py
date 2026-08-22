from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


@dataclass(slots=True)
class DSPSettings:
    preset: str = "Clean"
    gain_db: float = 0.0
    wet: float = 1.0
    gate_db: float = -55.0


class VoiceDSP:
    """Small, callback-safe DSP chain for the MVP."""

    def __init__(self, sample_rate: float, channels: int = 1) -> None:
        self.sample_rate = float(sample_rate)
        self.channels = channels
        self.phase = 0.0
        self._radio_lp = np.zeros(channels, dtype=np.float32)
        self._radio_hp = np.zeros(channels, dtype=np.float32)
        self._anon_lp = np.zeros(channels, dtype=np.float32)

    @staticmethod
    def _db_to_amp(db: float) -> float:
        return float(10.0 ** (db / 20.0))

    def _one_pole_lowpass(self, x: np.ndarray, cutoff: float, state: np.ndarray) -> np.ndarray:
        dt = 1.0 / self.sample_rate
        rc = 1.0 / (2.0 * math.pi * cutoff)
        a = dt / (rc + dt)
        y = np.empty_like(x)
        s = state.copy()
        for i in range(x.shape[0]):
            s += a * (x[i] - s)
            y[i] = s
        state[:] = s
        return y

    def _radio(self, x: np.ndarray) -> np.ndarray:
        low = self._one_pole_lowpass(x, 300.0, self._radio_hp)
        hp = x - low
        band = self._one_pole_lowpass(hp, 3400.0, self._radio_lp)
        return np.tanh(band * 2.2).astype(np.float32, copy=False)

    def _robot(self, x: np.ndarray) -> np.ndarray:
        n = x.shape[0]
        omega = 2.0 * math.pi * 70.0 / self.sample_rate
        phases = self.phase + omega * np.arange(n, dtype=np.float32)
        carrier = np.sin(phases)[:, None].astype(np.float32, copy=False)
        self.phase = float((self.phase + omega * n) % (2.0 * math.pi))
        return (x * carrier).astype(np.float32, copy=False)

    def _anonymous(self, x: np.ndarray) -> np.ndarray:
        dark = self._one_pole_lowpass(x, 1700.0, self._anon_lp)
        n = x.shape[0]
        omega = 2.0 * math.pi * 38.0 / self.sample_rate
        phases = self.phase + omega * np.arange(n, dtype=np.float32)
        ring = np.sin(phases)[:, None].astype(np.float32, copy=False)
        self.phase = float((self.phase + omega * n) % (2.0 * math.pi))
        return np.tanh(dark * 1.8 + dark * ring * 0.28).astype(np.float32, copy=False)

    def process(self, block: np.ndarray, settings: DSPSettings) -> np.ndarray:
        x = np.asarray(block, dtype=np.float32)
        if x.ndim == 1:
            x = x[:, None]
        dry = x

        gate = self._db_to_amp(settings.gate_db)
        work = np.where(np.abs(x) >= gate, x, 0.0).astype(np.float32, copy=False)

        preset = settings.preset.lower()
        if preset == "radio":
            wet_signal = self._radio(work)
        elif preset == "robot":
            wet_signal = self._robot(work)
        elif preset == "anonymous":
            wet_signal = self._anonymous(work)
        else:
            wet_signal = work

        gain = self._db_to_amp(settings.gain_db)
        wet = float(np.clip(settings.wet, 0.0, 1.0))
        out = ((dry * (1.0 - wet)) + (wet_signal * wet)) * gain
        return np.clip(out, -1.0, 1.0).astype(np.float32, copy=False)
