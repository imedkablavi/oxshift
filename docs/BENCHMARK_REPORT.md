# OxShift Alpha benchmark report

## Scope

OxShift has two complementary performance checks:

1. `scripts/benchmark_audio.py` measures the in-process microphone-conditioning + DSP path against the wall-clock budget of 48 kHz blocks at 128/256/512/1024 frames.
2. `scripts/stress_audio.py` repeatedly runs conditioning + the bounded VC worker + DSP + soundboard mix while tracking invalid output, processing-time percentiles, Python allocation growth, thread count, VC queue drops and underruns.

The PR CI runs a short benchmark and accelerated stress smoke and uploads both JSON and Markdown reports in the `realtime-contract-report` artifact. A separate `Audio Soak` workflow defaults to a paced 7,200-second (2-hour) run.

## What counts as evidence

For each block size, review:

- `buffer_budget_ms`: the time available before the next block at the configured rate;
- `p50_ms`, `p95_ms`, `p99_ms`, `peak_ms`;
- `simulated_over_budget_blocks` / percentage;
- runtime `AudioEngine.xruns` when a real PortAudio stream is open;
- VC `dropped_input_blocks` and `output_underruns` when inference cannot keep pace.

For stress/leak review, also inspect:

- `invalid_blocks` — must remain zero;
- `tracemalloc_start_mb` vs `tracemalloc_end_mb` and checkpoint trend;
- thread count at start/end;
- VC worker `last_error` — must remain empty;
- RSS/peak memory where the platform exposes it.

## Interpretation

An offline p95 below the block budget is useful evidence that Python-side processing is not inherently over budget on the CI CPU. It is **not** a claim about end-to-end microphone latency. Driver buffering, PipeWire/WASAPI scheduling, virtual endpoints, USB devices and optional AI inference can dominate real latency.

A release-candidate performance review therefore has three layers:

| Layer | Automated? | Gate |
|---|---|---|
| Pure processing budget | Yes | Review PR benchmark artifact; no invalid output and no systematic over-budget behavior. |
| Multi-hour in-process stability | Yes/manual workflow | 2+ hour paced soak without unbounded memory/thread growth or VC worker errors. |
| Physical round-trip / XRun behavior | Manual hardware | Test real PipeWire and Windows WASAPI routes at 48 kHz / 256 and at least one lower-latency block size. |

## Recommended physical-device matrix

- Linux PipeWire: physical USB mic -> OxShift -> `voxshift_mic` -> OBS/Discord.
- Linux hot unplug/replug: remove and reinsert the USB mic while streaming.
- Windows WASAPI: physical mic -> OxShift -> VB-CABLE/VoiceMeeter virtual playback -> paired recording endpoint -> OBS/Discord.
- Windows endpoint restart/re-enumeration: disable/enable or reconnect the chosen virtual/USB endpoint and confirm recovery counters increment and audio resumes.
- 48 kHz block sizes: 128, 256 and 512; treat 256 as the initial Alpha recommendation.

## Current reporting state

The committed source defines the benchmark/stress methodology; measured CI numbers are produced per commit and intentionally live in the workflow artifact rather than being hard-coded into this document. This prevents stale machine-specific results from being presented as universal product performance.
