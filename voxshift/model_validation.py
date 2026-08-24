from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any


SUPPORTED_MODEL_SCHEMAS = frozenset({"oxshift-rvc-stream-v1"})
MAX_MODEL_BYTES = 2 * 1024 * 1024 * 1024


class ModelValidationError(ValueError):
    """Raised when a local AI bundle is not safe/compatible enough to load."""


@dataclass(frozen=True, slots=True)
class ValidatedModelBundle:
    name: str
    schema: str
    version: int
    sample_rate: int
    root: Path
    model_path: Path
    sha256: str
    input_names: tuple[str, ...]
    output_names: tuple[str, ...]


_ALLOWED_KEYS = {
    "name",
    "schema",
    "version",
    "sample_rate",
    "model",
    "sha256",
}


def _safe_child(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    resolved_root = root.resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ModelValidationError("model path escapes bundle directory") from exc
    return candidate


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ModelValidationError(f"invalid model manifest: {exc}") from exc
    if not isinstance(payload, dict):
        raise ModelValidationError("model manifest must be a JSON object")
    unknown = set(payload) - _ALLOWED_KEYS
    if unknown:
        raise ModelValidationError(f"unknown manifest fields: {', '.join(sorted(unknown))}")
    return payload


def _validate_manifest_values(payload: dict[str, Any]) -> tuple[str, str, int, int, str, str]:
    name = str(payload.get("name", "")).strip()
    schema = str(payload.get("schema", "")).strip()
    model = str(payload.get("model", "")).strip()
    checksum = str(payload.get("sha256", "")).strip().lower()
    try:
        version = int(payload.get("version", 0))
        sample_rate = int(payload.get("sample_rate", 0))
    except (TypeError, ValueError) as exc:
        raise ModelValidationError("version and sample_rate must be integers") from exc

    if not name or len(name) > 120:
        raise ModelValidationError("model name is required and must be <= 120 characters")
    if schema not in SUPPORTED_MODEL_SCHEMAS:
        raise ModelValidationError(f"unsupported model schema: {schema or 'missing'}")
    if version != 1:
        raise ModelValidationError("unsupported model manifest version")
    if sample_rate not in {32000, 40000, 44100, 48000}:
        raise ModelValidationError("unsupported model sample rate")
    if not model or Path(model).suffix.lower() != ".onnx":
        raise ModelValidationError("validated Alpha bundles must reference one .onnx model")
    if len(checksum) != 64 or any(char not in "0123456789abcdef" for char in checksum):
        raise ModelValidationError("sha256 must be a 64-character hexadecimal digest")
    return name, schema, version, sample_rate, model, checksum


def _validate_onnx_signature(model_path: Path, schema: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    try:
        import onnxruntime as ort
    except Exception as exc:
        raise ModelValidationError("onnxruntime is required to validate this bundle") from exc

    try:
        options = ort.SessionOptions()
        options.enable_mem_pattern = False
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
        session = ort.InferenceSession(
            str(model_path),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        inputs = tuple(item.name for item in session.get_inputs())
        outputs = tuple(item.name for item in session.get_outputs())
    except Exception as exc:
        raise ModelValidationError(f"ONNX graph validation failed: {exc}") from exc

    if schema == "oxshift-rvc-stream-v1":
        if inputs != ("audio", "pitch_shift"):
            raise ModelValidationError(
                "oxshift-rvc-stream-v1 requires inputs exactly: audio, pitch_shift"
            )
        if outputs != ("audio",):
            raise ModelValidationError("oxshift-rvc-stream-v1 requires output exactly: audio")
    return inputs, outputs


def validate_bundle(manifest: str | Path, inspect_graph: bool = True) -> ValidatedModelBundle:
    """Validate a local ONNX bundle before any inference session is exposed to the runtime.

    Validation is intentionally strict. Raw .onnx/.pth files remain importable for cataloging,
    but they are never marked executable. A runnable Alpha model must live next to an
    ``oxshift-model.json`` manifest, use an allow-listed schema, remain inside its bundle
    directory, match a pinned SHA-256 digest, and expose the expected ONNX I/O signature.

    This function performs disk I/O and may instantiate an ONNX session, so it must never be
    called from the realtime audio callback.
    """
    manifest_path = Path(manifest).expanduser().resolve()
    if not manifest_path.is_file():
        raise ModelValidationError("model manifest does not exist")

    payload = _read_manifest(manifest_path)
    name, schema, version, sample_rate, model, checksum = _validate_manifest_values(payload)
    model_path = _safe_child(manifest_path.parent, model)
    if not model_path.is_file():
        raise ModelValidationError("model file does not exist")
    size = model_path.stat().st_size
    if size <= 0 or size > MAX_MODEL_BYTES:
        raise ModelValidationError("model file size is outside the allowed range")

    actual = sha256_file(model_path)
    if actual != checksum:
        raise ModelValidationError("model checksum does not match manifest")

    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    if inspect_graph:
        inputs, outputs = _validate_onnx_signature(model_path, schema)

    return ValidatedModelBundle(
        name=name,
        schema=schema,
        version=version,
        sample_rate=sample_rate,
        root=manifest_path.parent,
        model_path=model_path,
        sha256=actual,
        input_names=inputs,
        output_names=outputs,
    )
