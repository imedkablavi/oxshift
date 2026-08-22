from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import threading
import time
from typing import Deque
import uuid

import numpy as np

SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".aiff", ".aif"}


def _config_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "OxShift"
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "oxshift"


@dataclass(slots=True)
class SoundItem:
    id: str
    name: str
    path: str
    volume: float = 1.0
    hotkey: str = ""
    category: str = "General"
    favorite: bool = False
    loop: bool = False
    trim_start: float = 0.0
    trim_end: float = 0.0


@dataclass(slots=True)
class SoundboardSettings:
    master_volume: float = 0.85
    ducking_db: float = 0.0
    allow_overlap: bool = True
    monitor_enabled: bool = False


@dataclass(slots=True)
class PlaybackState:
    item_id: str
    active: bool = True
    paused: bool = False
    position_seconds: float = 0.0
    duration_seconds: float = 0.0
    error: str = ""
    underruns: int = 0


class _PlaybackSession:
    def __init__(self, item: SoundItem, sample_rate: int, chunk_frames: int = 4096) -> None:
        self.item = item
        self.sample_rate = sample_rate
        self.chunk_frames = chunk_frames
        self.queue: Deque[np.ndarray] = deque()
        self.queue_frames = 0
        self.max_queue_frames = sample_rate * 2
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.finished = False
        self.leftover = np.empty(0, dtype=np.float32)
        self.state = PlaybackState(item_id=item.id)
        self.thread = threading.Thread(target=self._worker, name=f"OxShiftSound-{item.id[:8]}", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.state.active = False

    def set_paused(self, paused: bool) -> None:
        self.state.paused = paused
        if paused:
            self.pause_event.set()
        else:
            self.pause_event.clear()

    def _worker(self) -> None:
        try:
            from pedalboard.io import AudioFile

            path = Path(self.item.path)
            if not path.exists():
                raise FileNotFoundError(path)

            while not self.stop_event.is_set():
                with AudioFile(str(path)).resampled_to(self.sample_rate) as audio:
                    self.state.duration_seconds = float(audio.frames / self.sample_rate) if audio.frames else 0.0
                    if self.item.trim_start > 0:
                        audio.seek(int(self.item.trim_start * self.sample_rate))

                    end_frame = int(self.item.trim_end * self.sample_rate) if self.item.trim_end > 0 else 0
                    while not self.stop_event.is_set():
                        if self.pause_event.is_set():
                            time.sleep(0.02)
                            continue

                        with self.lock:
                            queued = self.queue_frames
                        if queued >= self.max_queue_frames:
                            time.sleep(0.01)
                            continue

                        if end_frame and audio.tell() >= end_frame:
                            break

                        frames_to_read = self.chunk_frames
                        if end_frame:
                            frames_to_read = min(frames_to_read, max(0, end_frame - audio.tell()))
                        if frames_to_read <= 0:
                            break

                        block = audio.read(frames_to_read)
                        if block.size == 0:
                            break
                        if block.ndim == 2:
                            mono = np.mean(block, axis=0, dtype=np.float32)
                        else:
                            mono = np.asarray(block, dtype=np.float32)
                        mono = np.ascontiguousarray(mono, dtype=np.float32)

                        with self.lock:
                            self.queue.append(mono)
                            self.queue_frames += len(mono)

                    if not self.item.loop:
                        break

            self.finished = True
        except Exception as exc:  # audio decoder failures must never crash the realtime engine
            self.state.error = str(exc)
            self.finished = True

    def pull(self, frames: int) -> np.ndarray:
        if self.state.paused:
            return np.zeros(frames, dtype=np.float32)

        out = np.zeros(frames, dtype=np.float32)
        written = 0
        with self.lock:
            while written < frames:
                if self.leftover.size:
                    take = min(frames - written, self.leftover.size)
                    out[written : written + take] = self.leftover[:take]
                    self.leftover = self.leftover[take:]
                    written += take
                    continue
                if not self.queue:
                    break
                chunk = self.queue.popleft()
                self.queue_frames -= len(chunk)
                self.leftover = chunk

        if written == 0 and not self.finished and not self.state.paused:
            self.state.underruns += 1
        self.state.position_seconds += written / self.sample_rate
        if self.finished and not self.leftover.size:
            with self.lock:
                if not self.queue:
                    self.state.active = False
        return out * float(np.clip(self.item.volume, 0.0, 2.0))


class SoundboardEngine:
    """Persistent, streaming soundboard designed to be mixed inside AudioEngine's callback.

    File decoding and resampling happen on background threads. The realtime callback only
    consumes already-decoded float32 blocks from bounded queues.
    """

    def __init__(self, sample_rate: int = 48000) -> None:
        self.sample_rate = sample_rate
        self.settings = SoundboardSettings()
        self.items: list[SoundItem] = []
        self._sessions: dict[str, _PlaybackSession] = {}
        self._lock = threading.RLock()
        self.config_path = _config_dir() / "soundboard.json"
        self.load()

    def add_files(self, paths: list[str]) -> list[SoundItem]:
        added: list[SoundItem] = []
        known = {str(Path(item.path).resolve()) for item in self.items}
        for raw in paths:
            path = Path(raw).expanduser()
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            resolved = str(path.resolve())
            if resolved in known:
                continue
            item = SoundItem(id=uuid.uuid4().hex, name=path.stem, path=resolved)
            self.items.append(item)
            added.append(item)
            known.add(resolved)
        if added:
            self.save()
        return added

    def remove(self, item_id: str) -> None:
        self.stop(item_id)
        self.items = [item for item in self.items if item.id != item_id]
        self.save()

    def update_item(self, item_id: str, **changes) -> SoundItem | None:
        for item in self.items:
            if item.id != item_id:
                continue
            for key, value in changes.items():
                if hasattr(item, key):
                    setattr(item, key, value)
            self.save()
            return item
        return None

    def get(self, item_id: str) -> SoundItem | None:
        return next((item for item in self.items if item.id == item_id), None)

    def play(self, item_id: str) -> bool:
        item = self.get(item_id)
        if item is None:
            return False
        if not self.settings.allow_overlap:
            self.stop_all()
        self.stop(item_id)
        session = _PlaybackSession(item=item, sample_rate=self.sample_rate)
        with self._lock:
            self._sessions[item_id] = session
        session.start()
        return True

    def toggle_pause(self, item_id: str) -> bool:
        with self._lock:
            session = self._sessions.get(item_id)
        if session is None:
            return False
        session.set_paused(not session.state.paused)
        return session.state.paused

    def stop(self, item_id: str) -> None:
        with self._lock:
            session = self._sessions.pop(item_id, None)
        if session:
            session.stop()

    def stop_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.stop()

    def mix(self, frames: int) -> np.ndarray:
        with self._lock:
            sessions = list(self._sessions.items())
        if not sessions:
            return np.zeros((frames, 1), dtype=np.float32)

        mixed = np.zeros(frames, dtype=np.float32)
        stale: list[str] = []
        for item_id, session in sessions:
            mixed += session.pull(frames)
            if not session.state.active:
                stale.append(item_id)

        if stale:
            with self._lock:
                for item_id in stale:
                    self._sessions.pop(item_id, None)

        mixed *= float(np.clip(self.settings.master_volume, 0.0, 1.5))
        return np.clip(mixed, -1.0, 1.0)[:, None].astype(np.float32, copy=False)

    @property
    def is_playing(self) -> bool:
        with self._lock:
            return any(s.state.active and not s.state.paused for s in self._sessions.values())

    def states(self) -> list[PlaybackState]:
        with self._lock:
            return [session.state for session in self._sessions.values()]

    def save(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "settings": asdict(self.settings),
            "items": [asdict(item) for item in self.items],
        }
        temp = self.config_path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        temp.replace(self.config_path)

    def load(self) -> None:
        if not self.config_path.exists():
            return
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
            settings = payload.get("settings", {})
            self.settings = SoundboardSettings(**{k: v for k, v in settings.items() if k in SoundboardSettings.__annotations__})
            loaded = []
            for raw in payload.get("items", []):
                safe = {k: v for k, v in raw.items() if k in SoundItem.__annotations__}
                item = SoundItem(**safe)
                loaded.append(item)
            self.items = loaded
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self.items = []
