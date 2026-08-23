from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .model_validation import ValidatedModelBundle, validate_bundle


@dataclass(frozen=True, slots=True)
class AdapterInfo:
    name: str
    schema: str
    sample_rate: int
    provider: str


class ValidatedStreamingOnnxAdapter:
    """Adapter for the allow-listed ``oxshift-rvc-stream-v1`` ONNX schema.

    The schema is intentionally narrow for Alpha: a float32 mono audio block and one
    float32 pitch-shift scalar go in; a same-length float32 mono block comes out. The
    manifest/checksum/signature are validated before this class creates its inference
    session. Inference is expected to run only on RealtimeVoiceConverter's worker thread.
    """

    def __init__(self, bundle: ValidatedModelBundle, provider: str | None = None) -> None:
        if bundle.schema != "oxshift-rvc-stream-v1":
            raise ValueError(f"unsupported adapter schema: {bundle.schema}")

        import onnxruntime as ort

        available = tuple(ort.get_available_providers())
        selected = provider or (
            "CUDAExecutionProvider" if "CUDAExecutionProvider" in available else "CPUExecutionProvider"
        )
        if selected not in available:
            raise ValueError(f"requested ONNX provider is unavailable: {selected}")

        options = ort.SessionOptions()
        options.enable_mem_pattern = False
        self._session = ort.InferenceSession(
            str(bundle.model_path),
            sess_options=options,
            providers=[selected],
        )
        self.bundle = bundle
        self.sample_rate = int(bundle.sample_rate)
        self.info = AdapterInfo(bundle.name, bundle.schema, self.sample_rate, selected)

    @classmethod
    def from_manifest(cls, manifest: str | Path, provider: str | None = None) -> "ValidatedStreamingOnnxAdapter":
        return cls(validate_bundle(manifest, inspect_graph=True), provider=provider)

    def convert(self, audio: np.ndarray, pitch_shift: float = 0.0) -> np.ndarray:
        x = np.asarray(audio, dtype=np.float32)
        if x.ndim == 2:
            if x.shape[1] != 1:
                raise ValueError("validated streaming adapter requires mono audio")
            mono = x[:, 0]
        elif x.ndim == 1:
            mono = x
        else:
            raise ValueError("audio must be [frames] or [frames, 1]")

        block = np.ascontiguousarray(mono[None, :], dtype=np.float32)
        pitch = np.asarray([float(np.clip(pitch_shift, -24.0, 24.0))], dtype=np.float32)
        result = self._session.run(["audio"], {"audio": block, "pitch_shift": pitch})[0]
        y = np.asarray(result, dtype=np.float32)
        if y.ndim == 2 and y.shape[0] == 1:
            y = y[0]
        y = y.reshape(-1)
        if y.shape[0] != mono.shape[0] or not np.isfinite(y).all():
            raise ValueError("validated adapter returned invalid audio")
        return np.clip(y, -1.0, 1.0)[:, None].astype(np.float32, copy=False)

    def close(self) -> None:
        self._session = None
