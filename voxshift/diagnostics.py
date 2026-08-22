from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import platform
import sys
import time
from typing import Any


@dataclass(slots=True)
class AudioHealth:
    status: str
    sample_rate: int
    blocksize: int
    buffer_ms: float
    callback_ms: float
    callback_peak_ms: float
    xruns: int
    pitch_backend: str
    recorder_dropped_blocks: int
    vc_enabled: bool
    vc_ready: bool
    vc_inference_ms: float
    vc_underruns: int


def health_from_engine(engine) -> AudioHealth:
    vc = engine.voice_converter
    stats = getattr(vc, "stats", None)
    return AudioHealth(
        status=str(engine.last_status),
        sample_rate=int(engine.sample_rate),
        blocksize=int(engine.blocksize),
        buffer_ms=float(engine.estimated_buffer_latency_ms),
        callback_ms=float(engine.callback_ms),
        callback_peak_ms=float(engine.callback_peak_ms),
        xruns=int(engine.xruns),
        pitch_backend=str(engine.pitch_backend),
        recorder_dropped_blocks=int(engine.recorder.state.dropped_blocks),
        vc_enabled=bool(vc.config.enabled),
        vc_ready=bool(vc.ready),
        vc_inference_ms=float(getattr(stats, "inference_ms", 0.0) if stats else 0.0),
        vc_underruns=int(getattr(stats, "underruns", 0) if stats else 0),
    )


def build_diagnostics(engine, devices: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Build a support snapshot without usernames, paths, sound names, or model filenames."""
    device_summary = []
    for device in devices or []:
        device_summary.append(
            {
                "hostapi": int(device.get("hostapi", -1)),
                "max_input_channels": int(device.get("max_input_channels", 0)),
                "max_output_channels": int(device.get("max_output_channels", 0)),
                "default_samplerate": float(device.get("default_samplerate", 0.0)),
            }
        )
    return {
        "schema": 1,
        "generated_unix": int(time.time()),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
        },
        "audio": asdict(health_from_engine(engine)),
        "devices": device_summary,
    }


def diagnostics_json(engine, devices: list[dict[str, Any]] | None = None) -> str:
    return json.dumps(build_diagnostics(engine, devices), indent=2, sort_keys=True)
