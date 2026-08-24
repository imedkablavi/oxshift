#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import statistics
import sys
import time

# When executed as `python scripts/benchmark_audio.py`, Python puts `scripts/`
# on sys.path rather than the repository root. Add the root explicitly so the
# benchmark exercises the checked-out OxShift package in CI and local clones.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np

from voxshift.dsp import DSPSettings, VoiceDSP
from voxshift.speech_processing import SpeechProcessingSettings, SpeechProcessor


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    pos = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
    return float(ordered[pos])


def bench(sample_rate: int, blocksize: int, seconds: float) -> dict:
    dsp = VoiceDSP(sample_rate, 1)
    cleanup = SpeechProcessor(sample_rate)
    dsp_settings = DSPSettings(preset="Clean", pitch_semitones=0.0, formant_color=0.0)
    cleanup_settings = SpeechProcessingSettings(backend="builtin", noise_suppression=0.45, agc_enabled=True)
    budget_ms = blocksize / sample_rate * 1000.0
    t = np.arange(blocksize, dtype=np.float32) / sample_rate
    block = (0.12 * np.sin(2.0 * np.pi * 220.0 * t))[:, None].astype(np.float32)

    for _ in range(30):
        dsp.process(cleanup.process(block, cleanup_settings), dsp_settings)

    timings: list[float] = []
    deadline = time.perf_counter() + max(0.25, seconds)
    while time.perf_counter() < deadline:
        started = time.perf_counter_ns()
        cleaned = cleanup.process(block, cleanup_settings)
        output = dsp.process(cleaned, dsp_settings)
        if output.shape != block.shape or not np.isfinite(output).all():
            raise RuntimeError("pipeline produced invalid output")
        timings.append((time.perf_counter_ns() - started) / 1_000_000.0)

    over = sum(value > budget_ms for value in timings)
    return {
        "sample_rate": sample_rate,
        "blocksize": blocksize,
        "buffer_budget_ms": budget_ms,
        "iterations": len(timings),
        "mean_ms": statistics.fmean(timings) if timings else 0.0,
        "p50_ms": percentile(timings, 0.50),
        "p95_ms": percentile(timings, 0.95),
        "p99_ms": percentile(timings, 0.99),
        "peak_ms": max(timings, default=0.0),
        "simulated_over_budget_blocks": over,
        "simulated_over_budget_percent": (over / len(timings) * 100.0) if timings else 0.0,
        "p95_budget_ratio": (percentile(timings, 0.95) / budget_ms) if budget_ms else 0.0,
        "pitch_backend": dsp.pitch_backend,
        "cleanup_backend": cleanup.backend,
    }


def to_markdown(report: dict) -> str:
    lines = [
        "# OxShift offline realtime benchmark",
        "",
        f"Platform: `{report['platform']}`",
        "",
        "| Rate | Block | Budget ms | p50 ms | p95 ms | p99 ms | Peak ms | Over budget |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["results"]:
        lines.append(
            f"| {row['sample_rate']} | {row['blocksize']} | {row['buffer_budget_ms']:.3f} | "
            f"{row['p50_ms']:.3f} | {row['p95_ms']:.3f} | {row['p99_ms']:.3f} | "
            f"{row['peak_ms']:.3f} | {row['simulated_over_budget_percent']:.2f}% |"
        )
    lines += [
        "",
        "> This is an offline CPU pipeline benchmark, not a substitute for hardware/driver round-trip latency measurement. Real-device XRuns are tracked by AudioEngine at runtime.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=3.0, help="seconds per block size")
    parser.add_argument("--json", type=Path, default=Path("benchmark.json"))
    parser.add_argument("--markdown", type=Path, default=Path("benchmark.md"))
    parser.add_argument("--fail-p95-ratio", type=float, default=0.0, help="optional non-flaky local gate; 0 disables")
    args = parser.parse_args()

    report = {
        "schema": 1,
        "platform": f"{platform.system()} {platform.release()} {platform.machine()} / Python {platform.python_version()}",
        "results": [bench(48000, block, args.seconds) for block in (128, 256, 512, 1024)],
    }
    args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    args.markdown.write_text(to_markdown(report), encoding="utf-8")
    print(to_markdown(report))

    if args.fail_p95_ratio > 0 and any(row["p95_budget_ratio"] > args.fail_p95_ratio for row in report["results"]):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
