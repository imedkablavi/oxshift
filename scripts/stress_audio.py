#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import statistics
import sys
import threading
import time
import tracemalloc

# Support direct execution from a checkout: `python scripts/stress_audio.py`.
# Without this, Python places only scripts/ on sys.path and the checked-out
# `voxshift` package cannot be imported in CI or fresh clones.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np

from voxshift.dsp import DSPSettings, VoiceDSP
from voxshift.rvc_runtime import PassthroughAdapter, RealtimeVoiceConverter, RuntimeConfig
from voxshift.soundboard import SoundboardEngine
from voxshift.speech_processing import SpeechProcessingSettings, SpeechProcessor


def rss_bytes() -> int | None:
    try:
        import resource

        raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Linux reports KiB, macOS reports bytes.
        return int(raw if platform.system() == "Darwin" else raw * 1024)
    except Exception:
        return None


def fmt_mb(value: int | float | None) -> float | None:
    return None if value is None else float(value) / (1024.0 * 1024.0)


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
    return float(ordered[index])


def run(duration: float, sample_rate: int, blocksize: int, pace: bool) -> dict:
    cleanup = SpeechProcessor(sample_rate)
    dsp = VoiceDSP(sample_rate, 1)
    board = SoundboardEngine(sample_rate)
    converter = RealtimeVoiceConverter(
        PassthroughAdapter(sample_rate),
        RuntimeConfig(enabled=True, input_queue_blocks=4, output_queue_blocks=4, passthrough_on_underrun=True),
    )
    converter.start()

    cleanup_settings = SpeechProcessingSettings(
        backend="builtin",
        noise_suppression=0.45,
        agc_enabled=True,
        agc_target_dbfs=-18.0,
        agc_max_gain_db=12.0,
    )
    dsp_settings = DSPSettings(preset="Cyber", effect_order=(
        "filter", "pitch", "timbre", "drive", "modulation", "tremolo", "echo", "compressor"
    ))

    block_seconds = blocksize / sample_rate
    budget_ms = block_seconds * 1000.0
    phase = 0
    frames = np.arange(blocksize, dtype=np.float32)
    timings: list[float] = []
    checkpoints: list[dict] = []
    invalid_blocks = 0
    started_wall = time.monotonic()
    deadline = started_wall + max(0.1, duration)
    next_checkpoint = started_wall
    rss_start = rss_bytes()
    thread_start = threading.active_count()
    tracemalloc.start()
    traced_start, _ = tracemalloc.get_traced_memory()

    iterations = 0
    try:
        while time.monotonic() < deadline:
            iteration_started = time.perf_counter_ns()
            t = (frames + phase) / sample_rate
            source = (0.10 * np.sin(2.0 * np.pi * 180.0 * t) + 0.02 * np.sin(2.0 * np.pi * 3200.0 * t))
            block = source[:, None].astype(np.float32, copy=False)
            phase += blocksize

            cleaned = cleanup.process(block, cleanup_settings)
            converted = converter.process(cleaned)
            processed = dsp.process(converted, dsp_settings)
            mixed = np.clip(processed + board.mix(blocksize), -1.0, 1.0).astype(np.float32, copy=False)
            if mixed.shape != (blocksize, 1) or not np.isfinite(mixed).all():
                invalid_blocks += 1

            elapsed_ms = (time.perf_counter_ns() - iteration_started) / 1_000_000.0
            timings.append(elapsed_ms)
            iterations += 1

            now = time.monotonic()
            if now >= next_checkpoint:
                current, peak = tracemalloc.get_traced_memory()
                checkpoints.append({
                    "elapsed_seconds": now - started_wall,
                    "traced_current_mb": fmt_mb(current),
                    "traced_peak_mb": fmt_mb(peak),
                    "rss_peak_mb": fmt_mb(rss_bytes()),
                    "threads": threading.active_count(),
                    "vc_input_drops": converter.stats.dropped_input_blocks,
                    "vc_output_underruns": converter.stats.output_underruns,
                })
                next_checkpoint = now + 30.0

            if pace:
                target = started_wall + iterations * block_seconds
                delay = target - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
    finally:
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        converter.stop()

    rss_end = rss_bytes()
    runtime = time.monotonic() - started_wall
    over_budget = sum(value > budget_ms for value in timings)
    return {
        "schema": 1,
        "platform": f"{platform.system()} {platform.release()} {platform.machine()} / Python {platform.python_version()}",
        "requested_duration_seconds": duration,
        "runtime_seconds": runtime,
        "sample_rate": sample_rate,
        "blocksize": blocksize,
        "buffer_budget_ms": budget_ms,
        "pace_realtime": pace,
        "iterations": iterations,
        "invalid_blocks": invalid_blocks,
        "mean_pipeline_ms": statistics.fmean(timings) if timings else 0.0,
        "p95_pipeline_ms": percentile(timings, 0.95),
        "p99_pipeline_ms": percentile(timings, 0.99),
        "peak_pipeline_ms": max(timings, default=0.0),
        "over_budget_blocks": over_budget,
        "over_budget_percent": (over_budget / len(timings) * 100.0) if timings else 0.0,
        "tracemalloc_start_mb": fmt_mb(traced_start),
        "tracemalloc_end_mb": fmt_mb(current),
        "tracemalloc_peak_mb": fmt_mb(peak),
        "rss_start_mb": fmt_mb(rss_start),
        "rss_end_or_peak_mb": fmt_mb(rss_end),
        "threads_start": thread_start,
        "threads_end": threading.active_count(),
        "vc": {
            "submitted_blocks": converter.stats.submitted_blocks,
            "converted_blocks": converter.stats.converted_blocks,
            "dropped_input_blocks": converter.stats.dropped_input_blocks,
            "output_underruns": converter.stats.output_underruns,
            "last_error": converter.stats.last_error,
        },
        "checkpoints": checkpoints,
    }


def markdown(report: dict) -> str:
    growth = None
    if report["tracemalloc_start_mb"] is not None and report["tracemalloc_end_mb"] is not None:
        growth = report["tracemalloc_end_mb"] - report["tracemalloc_start_mb"]
    return "\n".join([
        "# OxShift audio stress report",
        "",
        f"- Runtime: **{report['runtime_seconds']:.1f}s** ({report['iterations']} blocks)",
        f"- Format: **{report['sample_rate']} Hz / {report['blocksize']} frames**",
        f"- Pipeline p95: **{report['p95_pipeline_ms']:.3f} ms** vs **{report['buffer_budget_ms']:.3f} ms** block budget",
        f"- Over-budget blocks: **{report['over_budget_percent']:.3f}%**",
        f"- Invalid output blocks: **{report['invalid_blocks']}**",
        f"- Traced Python allocation growth: **{growth:.2f} MiB**" if growth is not None else "- Traced Python allocation growth: unavailable",
        f"- Traced peak: **{report['tracemalloc_peak_mb']:.2f} MiB**",
        f"- Threads: **{report['threads_start']} -> {report['threads_end']}**",
        f"- VC queue drops / underruns: **{report['vc']['dropped_input_blocks']} / {report['vc']['output_underruns']}**",
        "",
        "> This harness stresses the in-process realtime pipeline without opening physical devices. A release candidate still requires a hardware soak with PortAudio/PipeWire/WASAPI and runtime XRun counters.",
        "",
    ])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=7200.0, help="wall-clock stress duration in seconds")
    parser.add_argument("--sample-rate", type=int, default=48000)
    parser.add_argument("--blocksize", type=int, default=256)
    parser.add_argument("--no-pace", action="store_true", help="run as fast as possible (CI smoke mode)")
    parser.add_argument("--json", type=Path, default=Path("stress.json"))
    parser.add_argument("--markdown", type=Path, default=Path("stress.md"))
    parser.add_argument("--max-traced-growth-mb", type=float, default=0.0, help="optional failure threshold; 0 disables")
    args = parser.parse_args()

    report = run(args.duration, args.sample_rate, args.blocksize, pace=not args.no_pace)
    args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    args.markdown.write_text(markdown(report), encoding="utf-8")
    print(markdown(report))

    if report["invalid_blocks"]:
        raise SystemExit(2)
    if report["vc"]["last_error"]:
        raise SystemExit(3)
    if args.max_traced_growth_mb > 0:
        growth = report["tracemalloc_end_mb"] - report["tracemalloc_start_mb"]
        if growth > args.max_traced_growth_mb:
            raise SystemExit(4)


if __name__ == "__main__":
    main()
