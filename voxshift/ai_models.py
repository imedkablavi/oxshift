from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil

from .model_validation import ModelValidationError, validate_bundle


def _data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "OxShift" / "models"
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "oxshift" / "models"


@dataclass(frozen=True, slots=True)
class AIModel:
    name: str
    model_path: str
    index_path: str = ""
    format: str = "unknown"
    backend: str = "unavailable"
    schema: str = ""
    manifest_path: str = ""
    validation_error: str = ""

    @property
    def executable(self) -> bool:
        return self.backend == "validated-onnx"


@dataclass(frozen=True, slots=True)
class AICapabilities:
    onnxruntime: bool
    providers: tuple[str, ...]
    rvc_adapter_ready: bool


class AIModelRegistry:
    """Local catalog with a strict trust boundary between imported and executable models.

    Raw .onnx/.pth files may be copied into the local catalog, but are quarantined and never
    exposed as executable adapters. Alpha execution is limited to allow-listed bundles that
    carry an ``oxshift-model.json`` manifest, pinned SHA-256 digest and validated ONNX I/O
    signature. PyTorch ``.pth`` is catalog-only because loading arbitrary pickle-backed model
    files is outside the Alpha trust boundary.
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or _data_dir()
        self.root.mkdir(parents=True, exist_ok=True)

    def capabilities(self) -> AICapabilities:
        providers: tuple[str, ...] = ()
        available = False
        try:
            import onnxruntime as ort

            providers = tuple(ort.get_available_providers())
            available = True
        except Exception:
            pass
        return AICapabilities(
            onnxruntime=available,
            providers=providers,
            rvc_adapter_ready=available,
        )

    def scan(self) -> list[AIModel]:
        models: list[AIModel] = []
        claimed: set[Path] = set()
        caps = self.capabilities()

        for manifest in sorted(self.root.rglob("oxshift-model.json")):
            try:
                bundle = validate_bundle(manifest, inspect_graph=caps.onnxruntime)
                claimed.add(bundle.model_path.resolve())
                backend = "validated-onnx" if caps.onnxruntime else "validation-pending-runtime"
                models.append(
                    AIModel(
                        name=bundle.name,
                        model_path=str(bundle.model_path),
                        format="onnx",
                        backend=backend,
                        schema=bundle.schema,
                        manifest_path=str(manifest),
                    )
                )
            except ModelValidationError as exc:
                models.append(
                    AIModel(
                        name=manifest.parent.name or "Invalid bundle",
                        model_path="",
                        format="bundle",
                        backend="rejected",
                        manifest_path=str(manifest),
                        validation_error=str(exc),
                    )
                )

        indices = {path.stem.lower(): path for path in self.root.rglob("*.index")}
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".onnx", ".pth"}:
                continue
            if path.resolve() in claimed:
                continue
            fmt = path.suffix.lower().lstrip(".")
            index = indices.get(path.stem.lower())
            reason = (
                "Raw ONNX is quarantined until it is wrapped in a validated OxShift bundle"
                if fmt == "onnx"
                else "PyTorch .pth loading is disabled in Alpha"
            )
            models.append(
                AIModel(
                    name=path.stem,
                    model_path=str(path),
                    index_path=str(index) if index else "",
                    format=fmt,
                    backend="quarantined",
                    validation_error=reason,
                )
            )
        return models

    def import_files(self, paths: list[str]) -> list[Path]:
        """Import files into the local catalog without granting execution trust."""
        imported: list[Path] = []
        for raw in paths:
            source = Path(raw).expanduser()
            if not source.is_file() or source.suffix.lower() not in {".onnx", ".pth", ".index", ".json"}:
                continue
            if source.suffix.lower() == ".json" and source.name != "oxshift-model.json":
                continue
            destination = self._deduplicated_destination(source.name)
            shutil.copy2(source, destination)
            imported.append(destination)
        return imported

    def import_validated_bundle(self, manifest_path: str | Path) -> Path:
        """Validate a bundle first, then copy its manifest+model into an isolated local folder."""
        bundle = validate_bundle(manifest_path, inspect_graph=True)
        safe_name = "".join(char if char.isalnum() or char in "-_" else "-" for char in bundle.name).strip("-")
        safe_name = safe_name or "model"
        destination = self.root / safe_name
        counter = 2
        while destination.exists():
            destination = self.root / f"{safe_name}-{counter}"
            counter += 1
        destination.mkdir(parents=True, exist_ok=False)
        try:
            model_target = destination / bundle.model_path.name
            shutil.copy2(bundle.model_path, model_target)
            manifest_target = destination / "oxshift-model.json"
            shutil.copy2(Path(manifest_path), manifest_target)
            validate_bundle(manifest_target, inspect_graph=True)
            return manifest_target
        except Exception:
            shutil.rmtree(destination, ignore_errors=True)
            raise

    def _deduplicated_destination(self, filename: str) -> Path:
        destination = self.root / filename
        if not destination.exists():
            return destination
        stem = destination.stem
        suffix = destination.suffix
        counter = 2
        while True:
            candidate = self.root / f"{stem}-{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1
