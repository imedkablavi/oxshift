from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True, slots=True)
class WaveformEnvelope:
    minimum: np.ndarray
    maximum: np.ndarray
    duration_seconds: float
    sample_rate: int

    @property
    def points(self) -> int:
        return int(self.minimum.size)


def envelope_from_samples(samples: np.ndarray, points: int = 1200, sample_rate: int = 48000) -> WaveformEnvelope:
    x = np.asarray(samples, dtype=np.float32)
    if x.ndim == 2:
        x = np.mean(x, axis=1, dtype=np.float32)
    x = x.reshape(-1)
    points = int(np.clip(points, 16, 10000))
    duration = float(len(x) / sample_rate) if sample_rate > 0 else 0.0
    if x.size == 0:
        zeros = np.zeros(points, dtype=np.float32)
        return WaveformEnvelope(zeros, zeros.copy(), duration, int(sample_rate))

    # Split into near-equal bins without retaining a second full copy of the audio.
    edges = np.linspace(0, x.size, points + 1, dtype=np.int64)
    lo = np.empty(points, dtype=np.float32)
    hi = np.empty(points, dtype=np.float32)
    for i in range(points):
        start, end = int(edges[i]), int(edges[i + 1])
        if end <= start:
            value = x[min(start, x.size - 1)]
            lo[i] = value
            hi[i] = value
        else:
            block = x[start:end]
            lo[i] = float(np.min(block))
            hi[i] = float(np.max(block))
    return WaveformEnvelope(lo, hi, duration, int(sample_rate))


def load_waveform(path: str | Path, points: int = 1200, target_rate: int = 48000) -> WaveformEnvelope:
    """Decode a compact waveform preview using Pedalboard's streaming AudioFile API.

    The preview keeps only a bounded mono buffer sized for visualization rather than loading
    arbitrary-length music into memory. Long files are progressively decimated while read.
    """
    from pedalboard.io import AudioFile

    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)

    max_preview_samples = max(points * 64, 32768)
    chunks: list[np.ndarray] = []
    total = 0
    duration = 0.0
    with AudioFile(str(source)).resampled_to(target_rate) as audio:
        duration = float(audio.frames / target_rate) if audio.frames else 0.0
        while True:
            block = audio.read(8192)
            if block.size == 0:
                break
            if block.ndim == 2:
                mono = np.mean(block, axis=0, dtype=np.float32)
            else:
                mono = np.asarray(block, dtype=np.float32).reshape(-1)
            chunks.append(np.ascontiguousarray(mono, dtype=np.float32))
            total += mono.size
            if total > max_preview_samples * 2:
                merged = np.concatenate(chunks)
                merged = merged[::2]
                chunks = [np.ascontiguousarray(merged, dtype=np.float32)]
                total = merged.size

    preview = np.concatenate(chunks) if chunks else np.empty(0, dtype=np.float32)
    result = envelope_from_samples(preview, points=points, sample_rate=target_rate)
    return WaveformEnvelope(result.minimum, result.maximum, duration, target_rate)
