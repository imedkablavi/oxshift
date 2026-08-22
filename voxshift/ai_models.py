from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil


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


@dataclass(frozen=True, slots=True)
class AICapabilities:
    onnxruntime: bool
    providers: tuple[str, ...]
    rvc_adapter_ready: bool


class AIModelRegistry:
    """Local model catalog and backend capability detector.

    This module deliberately separates model storage/discovery from inference. RVC model
    architectures are not interchangeable with arbitrary ONNX graphs, so OxShift only marks
    a model usable after a compatible inference adapter has validated its inputs/outputs.
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
            rvc_adapter_ready=False,
        )

    def scan(self) -> list[AIModel]:
        models: list[AIModel] = []
        indices = {path.stem.lower(): path for path in self.root.rglob("*.index")}
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".onnx", ".pth"}:
                continue
            fmt = path.suffix.lower().lstrip(".")
            index = indices.get(path.stem.lower())
            backend = "onnx" if fmt == "onnx" and self.capabilities().onnxruntime else "unavailable"
            models.append(
                AIModel(
                    name=path.stem,
                    model_path=str(path),
                    index_path=str(index) if index else "",
                    format=fmt,
                    backend=backend,
                )
            )
        return models

    def import_files(self, paths: list[str]) -> list[Path]:
        imported: list[Path] = []
        for raw in paths:
            source = Path(raw).expanduser()
            if not source.is_file() or source.suffix.lower() not in {".onnx", ".pth", ".index"}:
                continue
            destination = self._deduplicated_destination(source.name)
            shutil.copy2(source, destination)
            imported.append(destination)
        return imported

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
