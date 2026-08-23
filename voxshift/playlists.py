from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path

from .soundboard import SoundboardEngine


def _config_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "OxShift"
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "oxshift"


@dataclass(slots=True)
class Playlist:
    name: str
    item_ids: list[str] = field(default_factory=list)


class PlaylistController:
    """UI-side playlist sequencer.

    Audio file decoding still belongs to SoundboardEngine worker threads. This controller only
    selects which already-imported sound should start next and is intended to be ticked from
    the UI/event loop, never from the realtime callback.
    """

    def __init__(self, board: SoundboardEngine) -> None:
        self.board = board
        self.path = _config_dir() / "playlists.json"
        self.playlists: list[Playlist] = [Playlist("Favorites")]
        self.active_name = "Favorites"
        self._sequence: list[str] = []
        self._position = -1
        self._current_id: str | None = None
        self.load()
        self.prune_missing()

    @property
    def active(self) -> Playlist:
        return next((p for p in self.playlists if p.name == self.active_name), self.playlists[0])

    def names(self) -> list[str]:
        return [p.name for p in self.playlists]

    def select(self, name: str) -> Playlist:
        match = next((p for p in self.playlists if p.name == name), None)
        if match is not None:
            self.active_name = match.name
        return self.active

    def create(self, name: str) -> Playlist:
        cleaned = " ".join(str(name).strip().split())[:80]
        if not cleaned:
            raise ValueError("playlist name is required")
        if any(p.name.casefold() == cleaned.casefold() for p in self.playlists):
            raise ValueError("playlist already exists")
        playlist = Playlist(cleaned)
        self.playlists.append(playlist)
        self.active_name = cleaned
        self.save()
        return playlist

    def delete_active(self) -> bool:
        if len(self.playlists) <= 1:
            return False
        current = self.active
        self.playlists = [p for p in self.playlists if p is not current]
        self.active_name = self.playlists[0].name
        self.stop()
        self.save()
        return True

    def add(self, item_id: str) -> bool:
        if self.board.get(item_id) is None:
            return False
        playlist = self.active
        if item_id in playlist.item_ids:
            return False
        playlist.item_ids.append(item_id)
        self.save()
        return True

    def remove(self, item_id: str) -> None:
        playlist = self.active
        playlist.item_ids = [value for value in playlist.item_ids if value != item_id]
        self.save()

    def move(self, item_id: str, delta: int) -> bool:
        playlist = self.active
        if item_id not in playlist.item_ids:
            return False
        old = playlist.item_ids.index(item_id)
        new = max(0, min(len(playlist.item_ids) - 1, old + int(delta)))
        if new == old:
            return False
        playlist.item_ids.pop(old)
        playlist.item_ids.insert(new, item_id)
        self.save()
        return True

    def play(self) -> bool:
        self.prune_missing()
        self._sequence = list(self.active.item_ids)
        self._position = -1
        self._current_id = None
        return self.next()

    def next(self) -> bool:
        if self._current_id:
            self.board.stop(self._current_id)
        self._position += 1
        while self._position < len(self._sequence):
            item_id = self._sequence[self._position]
            if self.board.get(item_id) is not None and self.board.play(item_id):
                self._current_id = item_id
                return True
            self._position += 1
        self._current_id = None
        return False

    def stop(self) -> None:
        if self._current_id:
            self.board.stop(self._current_id)
        self._sequence = []
        self._position = -1
        self._current_id = None

    def tick(self) -> None:
        current = self._current_id
        if not current:
            return
        active_ids = {state.item_id for state in self.board.states() if state.active}
        if current not in active_ids:
            self.next()

    def prune_missing(self) -> None:
        valid = {item.id for item in self.board.items}
        changed = False
        for playlist in self.playlists:
            kept = [item_id for item_id in playlist.item_ids if item_id in valid]
            if kept != playlist.item_ids:
                playlist.item_ids = kept
                changed = True
        if changed:
            self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "active": self.active_name,
            "playlists": [asdict(item) for item in self.playlists],
        }
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        temp.replace(self.path)

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            loaded: list[Playlist] = []
            for raw in payload.get("playlists", []):
                if not isinstance(raw, dict):
                    continue
                name = " ".join(str(raw.get("name", "")).strip().split())[:80]
                ids = [str(value) for value in raw.get("item_ids", []) if isinstance(value, str)]
                if name and not any(p.name.casefold() == name.casefold() for p in loaded):
                    loaded.append(Playlist(name, ids))
            if loaded:
                self.playlists = loaded
            active = str(payload.get("active", ""))
            if any(p.name == active for p in self.playlists):
                self.active_name = active
            else:
                self.active_name = self.playlists[0].name
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self.playlists = [Playlist("Favorites")]
            self.active_name = "Favorites"
