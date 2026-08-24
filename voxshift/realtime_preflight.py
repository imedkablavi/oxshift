from __future__ import annotations

from dataclasses import dataclass
import time

import numpy as np

from .dsp import DSPSettings, VoiceDSP
from .speech_processing import SpeechProcessingSettings, SpeechProcessor


@dataclass(frozen=True, slots=True)
class RealtimeHeadroomResult:
    sample_rate: int
    blocksize: int
    budget_ms: float
    p95_ms: float
    peak_ms: float
    budget_ratio: float
    safe: bool
    iterations: int
    pitch_backend: str


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    pos = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
    return float(ordered[pos])


def _profile_dsp_settings(profile) -> DSPSettings:
    return DSPSettings(
        preset=str(profile.voice),
        gain_db=float(profile.gain_db),
        wet=float(profile.wet),
        gate_db=float(profile.gate_db),
        pitch_semitones=float(profile.pitch_semitones),
        formant_color=float(profile.formant_color),
        eq_enabled=bool(profile.eq_enabled),
        eq_bands_db=(
            float(profile.eq_80_db),
            float(profile.eq_250_db),
            float(profile.eq_1000_db),
            float(profile.eq_4000_db),
            float(profile.eq_12000_db),
        ),
        effect_order=tuple(profile.effect_order or ()),
        disabled_effects=tuple(profile.disabled_effects or ()),
    )


def _profile_cleanup_settings(profile) -> SpeechProcessingSettings:
    # Force the lightweight built-in backend for callback-budget calibration. Optional
    # WebRTC may be measured differently by its native implementation; the runtime health
    # counters remain the final source of truth after start.
    return SpeechProcessingSettings(
        backend="builtin",
        noise_suppression=float(profile.noise_suppression),
        agc_enabled=bool(profile.agc_enabled),
        agc_target_dbfs=float(profile.agc_target_dbfs),
        agc_max_gain_db=float(profile.agc_max_gain_db),
        echo_cancellation=False,
    )


def measure_profile_headroom(
    profile,
    *,
    blocksize: int | None = None,
    iterations: int = 14,
    safe_ratio: float = 0.80,
) -> RealtimeHeadroomResult:
    """Measure local DSP callback headroom using the active profile outside PortAudio.

    The check intentionally includes microphone cleanup + the full local DSP/effect chain,
    including EQ and the native pitch stage that can be CPU-heavy. It excludes AI conversion
    because AI inference already runs on a bounded worker queue outside the realtime callback.
    """
    sample_rate = int(profile.sample_rate)
    frames = int(blocksize if blocksize is not None else profile.blocksize)
    if sample_rate not in {44100, 48000, 96000}:
        raise ValueError("unsupported sample rate for realtime preflight")
    if frames not in {128, 256, 512, 1024}:
        raise ValueError("unsupported block size for realtime preflight")

    dsp = VoiceDSP(sample_rate, 1)
    cleanup = SpeechProcessor(sample_rate)
    dsp_settings = _profile_dsp_settings(profile)
    cleanup_settings = _profile_cleanup_settings(profile)
    t = np.arange(frames, dtype=np.float32) / sample_rate
    source = (
        0.10 * np.sin(2.0 * np.pi * 180.0 * t)
        + 0.025 * np.sin(2.0 * np.pi * 3200.0 * t)
    )[:, None].astype(np.float32, copy=False)

    # Warm native DSP/pitch/EQ state before collecting measurements.
    for _ in range(3):
        dsp.process(cleanup.process(source, cleanup_settings), dsp_settings)

    timings: list[float] = []
    for _ in range(max(6, int(iterations))):
        started = time.perf_counter_ns()
        output = dsp.process(cleanup.process(source, cleanup_settings), dsp_settings)
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000.0
        if output.shape != source.shape or not np.isfinite(output).all():
            raise RuntimeError("realtime preflight produced invalid DSP output")
        timings.append(elapsed_ms)

    budget_ms = frames / sample_rate * 1000.0
    p95 = _percentile(timings, 0.95)
    peak = max(timings, default=0.0)
    ratio = p95 / budget_ms if budget_ms else float("inf")
    return RealtimeHeadroomResult(
        sample_rate=sample_rate,
        blocksize=frames,
        budget_ms=budget_ms,
        p95_ms=p95,
        peak_ms=peak,
        budget_ratio=ratio,
        safe=ratio <= float(safe_ratio),
        iterations=len(timings),
        pitch_backend=dsp.pitch_backend,
    )


def find_safe_blocksize(
    profile,
    *,
    safe_ratio: float = 0.80,
    iterations: int = 14,
) -> tuple[RealtimeHeadroomResult, list[RealtimeHeadroomResult]]:
    """Return the first safe block size at or above the profile's current size.

    If no candidate is safe, the returned first element is the largest measured result with
    ``safe=False`` so the UI can fail closed and explain the measured headroom.
    """
    choices = (128, 256, 512, 1024)
    current = int(profile.blocksize)
    start = next((index for index, value in enumerate(choices) if value >= current), len(choices) - 1)
    measured: list[RealtimeHeadroomResult] = []
    for block in choices[start:]:
        result = measure_profile_headroom(
            profile,
            blocksize=block,
            iterations=iterations,
            safe_ratio=safe_ratio,
        )
        measured.append(result)
        if result.safe:
            return result, measured
    return measured[-1], measured


def choose_safe_blocksize_from_ratios(
    current: int,
    ratios: dict[int, float],
    *,
    safe_ratio: float = 0.80,
) -> int | None:
    """Pure decision helper used by tests and non-timing callers."""
    for block in (128, 256, 512, 1024):
        if block >= int(current) and block in ratios and float(ratios[block]) <= safe_ratio:
            return block
    return None
