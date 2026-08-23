from __future__ import annotations

from dataclasses import dataclass
import math
import time

import numpy as np


@dataclass(frozen=True, slots=True)
class MicrophoneProbeResult:
    peak_rms: float
    mean_rms: float
    peak_dbfs: float
    duration_seconds: float


def rms_to_dbfs(value: float) -> float:
    value = max(float(value), 1e-9)
    return float(20.0 * math.log10(value))


def probe_microphone(device_index: int, *, duration_seconds: float = 1.5, sample_rate: int = 48000) -> MicrophoneProbeResult:
    """Measure microphone level without routing audio or writing it to disk.

    This helper is intended for a UI/background thread. It does not run AI inference and
    does not persist samples; the temporary capture buffer is released before returning.
    """
    import sounddevice as sd

    duration = float(min(5.0, max(0.25, duration_seconds)))
    frames = int(sample_rate * duration)
    started = time.perf_counter()
    audio = sd.rec(
        frames,
        samplerate=int(sample_rate),
        channels=1,
        dtype="float32",
        device=int(device_index),
        blocking=True,
    )
    elapsed = time.perf_counter() - started
    samples = np.asarray(audio, dtype=np.float32).reshape(-1)
    if not samples.size or not np.isfinite(samples).all():
        raise RuntimeError("microphone test returned invalid audio")

    # Work only with level summaries and drop the temporary sample buffer immediately.
    block = 1024
    levels: list[float] = []
    for offset in range(0, samples.size, block):
        chunk = samples[offset : offset + block]
        if chunk.size:
            levels.append(float(np.sqrt(np.mean(np.square(chunk), dtype=np.float64))))
    peak = max(levels, default=0.0)
    mean = float(np.mean(levels, dtype=np.float64)) if levels else 0.0
    return MicrophoneProbeResult(
        peak_rms=peak,
        mean_rms=mean,
        peak_dbfs=rms_to_dbfs(peak),
        duration_seconds=float(elapsed),
    )
