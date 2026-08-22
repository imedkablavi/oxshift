from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import tempfile
import uuid

from .dsp import DEFAULT_EFFECT_ORDER, VALID_EFFECTS


def _config_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "OxShift"
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "oxshift"


@dataclass(slots=True)
class StudioProfile:
    id: str
    name: str
    voice: str = "Clean"
    gain_db: float = 0.0
    wet: float = 1.0
    gate_db: float = -55.0
    pitch_semitones: float = 0.0
    formant_color: float = 0.0
    noise_suppression: float = 0.45
    agc_enabled: bool = True
    agc_target_dbfs: float = -18.0
    agc_max_gain_db: float = 12.0
    effect_order: list[str] = field(default_factory=lambda: list(DEFAULT_EFFECT_ORDER))
    disabled_effects: list[str] = field(default_factory=list)
    soundboard_master: float = 0.85
    soundboard_duck_db: float = 0.0
    allow_overlap: bool = True
    sample_rate: int = 48000
    blocksize: int = 256
    input_device_name: str = ""
    output_device_name: str = ""

    def sanitize(self) -> None:
        self.name = (self.name or "Profile").strip()[:80]
        self.gain_db = float(max(-24.0, min(24.0, self.gain_db)))
        self.wet = float(max(0.0, min(1.0, self.wet)))
        self.gate_db = float(max(-90.0, min(-10.0, self.gate_db)))
        self.pitch_semitones = float(max(-12.0, min(12.0, self.pitch_semitones)))
        self.formant_color = float(max(-1.0, min(1.0, self.formant_color)))
        self.noise_suppression = float(max(0.0, min(1.0, self.noise_suppression)))
        self.agc_target_dbfs = float(max(-30.0, min(-8.0, self.agc_target_dbfs)))
        self.agc_max_gain_db = float(max(0.0, min(24.0, self.agc_max_gain_db)))
        clean_order: list[str] = []
        for name in list(self.effect_order or []):
            if name in VALID_EFFECTS and name not in clean_order:
                clean_order.append(name)
        for name in DEFAULT_EFFECT_ORDER:
            if name not in clean_order:
                clean_order.append(name)
        self.effect_order = clean_order
        self.disabled_effects = [name for name in dict.fromkeys(self.disabled_effects or []) if name in VALID_EFFECTS]
        self.soundboard_master = float(max(0.0, min(1.5, self.soundboard_master)))
        self.soundboard_duck_db = float(max(0.0, min(36.0, self.soundboard_duck_db)))
        self.sample_rate = self.sample_rate if self.sample_rate in {44100, 48000, 96000} else 48000
        self.blocksize = self.blocksize if self.blocksize in {128, 256, 512, 1024} else 256
        self.input_device_name = str(self.input_device_name or "")[:200]
        self.output_device_name = str(self.output_device_name or "")[:200]


class ProfileStore:
    VERSION = 3

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (_config_dir() / "profiles.json")
        self.items: list[StudioProfile] = []
        self.active_id: str = ""
        self.load()
        if not self.items:
            default = StudioProfile(id=uuid.uuid4().hex, name="Default")
            self.items = [default]
            self.active_id = default.id
            self.save()

    @property
    def active(self) -> StudioProfile:
        profile = next((p for p in self.items if p.id == self.active_id), None)
        if profile is None:
            profile = self.items[0]
            self.active_id = profile.id
        return profile

    def create(self, name: str, *, clone: StudioProfile | None = None) -> StudioProfile:
        source = clone or self.active
        profile = StudioProfile(**asdict(source))
        profile.id = uuid.uuid4().hex
        profile.name = name
        profile.sanitize()
        self.items.append(profile)
        self.active_id = profile.id
        self.save()
        return profile

    def update_active(self, **changes) -> StudioProfile:
        profile = self.active
        for key, value in changes.items():
            if hasattr(profile, key) and key != "id":
                setattr(profile, key, value)
        profile.sanitize()
        self.save()
        return profile

    def select(self, profile_id: str) -> StudioProfile | None:
        if any(p.id == profile_id for p in self.items):
            self.active_id = profile_id
            self.save()
            return self.active
        return None

    def delete(self, profile_id: str) -> bool:
        if len(self.items) <= 1:
            return False
        before = len(self.items)
        self.items = [p for p in self.items if p.id != profile_id]
        if len(self.items) == before:
            return False
        if self.active_id == profile_id:
            self.active_id = self.items[0].id
        self.save()
        return True

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": self.VERSION, "active_id": self.active_id, "profiles": [asdict(item) for item in self.items]}
        fd, raw_tmp = tempfile.mkstemp(prefix="profiles-", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            Path(raw_tmp).replace(self.path)
        finally:
            Path(raw_tmp).unlink(missing_ok=True)

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            loaded: list[StudioProfile] = []
            for raw in payload.get("profiles", []):
                safe = {k: v for k, v in raw.items() if k in StudioProfile.__annotations__}
                profile = StudioProfile(**safe)
                profile.sanitize()
                loaded.append(profile)
            self.items = loaded
            self.active_id = str(payload.get("active_id", ""))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self.items = []
            self.active_id = ""
