from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Full, Queue
import threading
import time
import wave

import numpy as np


@dataclass(slots=True)
class RecorderState:
    recording: bool = False
    path: str = ""
    started_at: float = 0.0
    frames_written: int = 0
    dropped_blocks: int = 0
    error: str = ""


class OutputRecorder:
    """Non-blocking PCM16 WAV recorder fed by the realtime callback.

    The callback only copies into a bounded queue. Disk I/O happens on a worker thread,
    so a slow filesystem cannot block microphone processing.
    """

    def __init__(self, sample_rate: int = 48000, queue_blocks: int = 256) -> None:
        self.sample_rate = int(sample_rate)
        self.queue: Queue[np.ndarray | None] = Queue(maxsize=max(8, int(queue_blocks)))
        self.state = RecorderState()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self, path: str | Path, sample_rate: int | None = None) -> bool:
        with self._lock:
            if self.state.recording:
                return False
            target = Path(path).expanduser()
            target.parent.mkdir(parents=True, exist_ok=True)
            self.sample_rate = int(sample_rate or self.sample_rate)
            self.state = RecorderState(recording=True, path=str(target), started_at=time.time())
            self.queue = Queue(maxsize=self.queue.maxsize)
            self._thread = threading.Thread(target=self._worker, args=(target,), name="OxShiftRecorder", daemon=True)
            self._thread.start()
            return True

    def push(self, block: np.ndarray) -> None:
        if not self.state.recording:
            return
        x = np.asarray(block, dtype=np.float32)
        if x.ndim == 2:
            x = x[:, 0]
        x = np.ascontiguousarray(np.clip(x, -1.0, 1.0), dtype=np.float32)
        try:
            self.queue.put_nowait(x.copy())
        except Full:
            self.state.dropped_blocks += 1

    def stop(self) -> RecorderState:
        with self._lock:
            if not self.state.recording:
                return self.state
            self.state.recording = False
            try:
                self.queue.put_nowait(None)
            except Full:
                try:
                    self.queue.get_nowait()
                except Empty:
                    pass
                try:
                    self.queue.put_nowait(None)
                except Full:
                    pass
            thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=3.0)
        return self.state

    @property
    def duration_seconds(self) -> float:
        return self.state.frames_written / self.sample_rate if self.sample_rate else 0.0

    def _worker(self, target: Path) -> None:
        try:
            with wave.open(str(target), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(self.sample_rate)
                while True:
                    try:
                        block = self.queue.get(timeout=0.25)
                    except Empty:
                        if not self.state.recording:
                            break
                        continue
                    if block is None:
                        break
                    pcm = (np.clip(block, -1.0, 1.0) * 32767.0).astype("<i2", copy=False)
                    wav.writeframesraw(pcm.tobytes())
                    self.state.frames_written += int(len(block))
        except Exception as exc:
            self.state.error = str(exc)
            self.state.recording = False
