from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import queue
import threading
import time
from typing import Protocol

import numpy as np


class VoiceConversionAdapter(Protocol):
    """Minimal adapter contract for realtime voice conversion backends."""

    sample_rate: int

    def convert(self, audio: np.ndarray, pitch_shift: float = 0.0) -> np.ndarray: ...

    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class RVCManifest:
    name: str
    sample_rate: int = 40000
    synthesizer: str = "model.onnx"
    content_encoder: str = "contentvec.onnx"
    pitch_estimator: str = "rmvpe.onnx"
    index: str = ""
    speaker_id: int = 0
    version: int = 1

    @classmethod
    def load(cls, path: str | Path) -> "RVCManifest":
        manifest_path = Path(path)
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        allowed = cls.__annotations__.keys()
        values = {key: value for key, value in payload.items() if key in allowed}
        result = cls(**values)
        if result.sample_rate not in {32000, 40000, 44100, 48000}:
            raise ValueError("unsupported RVC sample rate")
        if result.version != 1:
            raise ValueError("unsupported OxShift RVC manifest version")
        return result

    def resolve(self, root: str | Path) -> dict[str, Path]:
        base = Path(root)
        files = {
            "synthesizer": base / self.synthesizer,
            "content_encoder": base / self.content_encoder,
            "pitch_estimator": base / self.pitch_estimator,
        }
        if self.index:
            files["index"] = base / self.index
        return files

    def validate_files(self, root: str | Path) -> list[str]:
        missing: list[str] = []
        for role, path in self.resolve(root).items():
            if role == "index":
                continue
            if not path.is_file():
                missing.append(role)
        return missing


@dataclass(slots=True)
class RuntimeStats:
    submitted_blocks: int = 0
    converted_blocks: int = 0
    dropped_input_blocks: int = 0
    output_underruns: int = 0
    last_inference_ms: float = 0.0
    peak_inference_ms: float = 0.0
    moving_inference_ms: float = 0.0
    last_error: str = ""


@dataclass(slots=True)
class RuntimeConfig:
    enabled: bool = False
    pitch_shift: float = 0.0
    input_queue_blocks: int = 8
    output_queue_blocks: int = 8
    passthrough_on_underrun: bool = True


class RealtimeVoiceConverter:
    """Runs slow VC inference outside the PortAudio callback.

    The audio callback calls ``process``. Blocks are copied into a bounded input queue and
    converted by a worker thread. If inference cannot keep up, the callback never blocks:
    it returns the newest converted block when available, otherwise passthrough/silence.

    This deliberately does not hard-code one RVC graph schema. Model-specific ONNX/PyTorch
    handling belongs behind ``VoiceConversionAdapter`` after a manifest validates the bundle.
    """

    def __init__(self, adapter: VoiceConversionAdapter | None = None, config: RuntimeConfig | None = None) -> None:
        self.adapter = adapter
        self.config = config or RuntimeConfig()
        self.stats = RuntimeStats()
        self._input: queue.Queue[np.ndarray] = queue.Queue(maxsize=max(1, self.config.input_queue_blocks))
        self._output: queue.Queue[np.ndarray] = queue.Queue(maxsize=max(1, self.config.output_queue_blocks))
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None
        self._last_output: np.ndarray | None = None
        self._lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self.adapter is not None

    def start(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._stop.clear()
        self._worker = threading.Thread(target=self._run, name="OxShiftVC", daemon=True)
        self._worker.start()

    def stop(self) -> None:
        self._stop.set()
        worker, self._worker = self._worker, None
        if worker and worker.is_alive():
            worker.join(timeout=0.5)
        self._drain(self._input)
        self._drain(self._output)
        self._last_output = None
        if self.adapter is not None:
            try:
                self.adapter.close()
            except Exception:
                pass

    @staticmethod
    def _drain(q: queue.Queue[np.ndarray]) -> None:
        while True:
            try:
                q.get_nowait()
            except queue.Empty:
                return

    def process(self, block: np.ndarray) -> np.ndarray:
        x = np.asarray(block, dtype=np.float32)
        if x.ndim == 1:
            x = x[:, None]
        if not self.config.enabled or self.adapter is None:
            return x
        if self._worker is None or not self._worker.is_alive():
            self.start()

        self.stats.submitted_blocks += 1
        try:
            self._input.put_nowait(np.ascontiguousarray(x.copy()))
        except queue.Full:
            self.stats.dropped_input_blocks += 1
            try:
                self._input.get_nowait()
                self._input.put_nowait(np.ascontiguousarray(x.copy()))
            except (queue.Empty, queue.Full):
                pass

        newest: np.ndarray | None = None
        while True:
            try:
                newest = self._output.get_nowait()
            except queue.Empty:
                break
        if newest is not None:
            self._last_output = newest

        if self._last_output is not None and self._last_output.shape == x.shape:
            return self._last_output
        self.stats.output_underruns += 1
        return x if self.config.passthrough_on_underrun else np.zeros_like(x)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                block = self._input.get(timeout=0.05)
            except queue.Empty:
                continue
            try:
                started = time.perf_counter()
                converted = self.adapter.convert(block, pitch_shift=float(self.config.pitch_shift)) if self.adapter else block
                elapsed = (time.perf_counter() - started) * 1000.0
                y = np.asarray(converted, dtype=np.float32)
                if y.ndim == 1:
                    y = y[:, None]
                if y.shape != block.shape or not np.isfinite(y).all():
                    raise ValueError(f"adapter returned invalid shape/data: {y.shape}, expected {block.shape}")
                y = np.clip(y, -1.0, 1.0).astype(np.float32, copy=False)

                self.stats.converted_blocks += 1
                self.stats.last_inference_ms = elapsed
                self.stats.peak_inference_ms = max(self.stats.peak_inference_ms * 0.995, elapsed)
                self.stats.moving_inference_ms = elapsed if self.stats.converted_blocks == 1 else (self.stats.moving_inference_ms * 0.9 + elapsed * 0.1)
                self.stats.last_error = ""

                try:
                    self._output.put_nowait(y)
                except queue.Full:
                    try:
                        self._output.get_nowait()
                        self._output.put_nowait(y)
                    except (queue.Empty, queue.Full):
                        pass
            except Exception as exc:
                self.stats.last_error = str(exc)


class PassthroughAdapter:
    """Test/development adapter that preserves audio and the realtime contract."""

    def __init__(self, sample_rate: int = 48000) -> None:
        self.sample_rate = sample_rate

    def convert(self, audio: np.ndarray, pitch_shift: float = 0.0) -> np.ndarray:
        return np.asarray(audio, dtype=np.float32)

    def close(self) -> None:
        return None
