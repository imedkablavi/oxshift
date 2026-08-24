from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import tempfile


VALID_PAGES = ("Home", "Voices", "Mixer", "Soundboard", "Studio", "Profiles", "AI Models", "Audio")


def preferences_path() -> Path:
    override = os.environ.get("OXSHIFT_CONFIG_HOME", "").strip()
    if override:
        return Path(override).expanduser() / "ui.json"
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "OxShift"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "oxshift"
    return base / "ui.json"


@dataclass(slots=True)
class AppPreferences:
    schema: int = 2
    onboarding_complete: bool = False
    last_page: str = "Home"
    window_geometry: str = "1320x820"
    compact_tips_dismissed: bool = False
    autosave_profile: bool = True
    restore_last_page: bool = True
    global_hotkeys_enabled: bool = True

    def sanitize(self) -> None:
        self.schema = 2
        self.onboarding_complete = bool(self.onboarding_complete)
        self.compact_tips_dismissed = bool(self.compact_tips_dismissed)
        self.autosave_profile = bool(self.autosave_profile)
        self.restore_last_page = bool(self.restore_last_page)
        self.global_hotkeys_enabled = bool(self.global_hotkeys_enabled)
        if self.last_page not in VALID_PAGES:
            self.last_page = "Home"
        value = str(self.window_geometry or "1320x820").strip()
        size = value.split("+", 1)[0]
        try:
            width_raw, height_raw = size.lower().split("x", 1)
            width = min(3000, max(1040, int(width_raw)))
            height = min(2000, max(680, int(height_raw)))
            self.window_geometry = f"{width}x{height}"
        except (TypeError, ValueError):
            self.window_geometry = "1320x820"


class AppPreferencesStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or preferences_path()
        self.state = AppPreferences()
        self.load()

    def load(self) -> AppPreferences:
        if not self.path.is_file():
            self.state = AppPreferences()
            return self.state
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            safe = {key: value for key, value in raw.items() if key in AppPreferences.__annotations__}
            self.state = AppPreferences(**safe)
            self.state.sanitize()
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self.state = AppPreferences()
        return self.state

    def save(self) -> None:
        self.state.sanitize()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, raw_tmp = tempfile.mkstemp(prefix="ui-", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(asdict(self.state), handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            Path(raw_tmp).replace(self.path)
        finally:
            Path(raw_tmp).unlink(missing_ok=True)

    def remember_page(self, page: str) -> None:
        self.state.last_page = page
        self.save()

    def complete_onboarding(self) -> None:
        self.state.onboarding_complete = True
        self.save()
