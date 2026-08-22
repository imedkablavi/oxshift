from __future__ import annotations

from collections.abc import Callable
import threading


class GlobalHotkeyManager:
    """Thin optional wrapper around pynput GlobalHotKeys.

    Hotkeys use pynput syntax such as ``<ctrl>+<alt>+1`` or ``<f8>``.
    Failure to initialize never prevents OxShift from starting.
    """

    def __init__(self) -> None:
        self._listener = None
        self._lock = threading.Lock()
        self.last_error = ""

    @property
    def running(self) -> bool:
        return self._listener is not None

    def start(self, bindings: dict[str, Callable[[], None]]) -> bool:
        self.stop()
        bindings = {key.strip(): callback for key, callback in bindings.items() if key.strip()}
        if not bindings:
            return True
        try:
            from pynput import keyboard

            listener = keyboard.GlobalHotKeys(bindings)
            listener.daemon = True
            listener.start()
            with self._lock:
                self._listener = listener
            self.last_error = ""
            return True
        except Exception as exc:
            self.last_error = str(exc)
            return False

    def stop(self) -> None:
        with self._lock:
            listener, self._listener = self._listener, None
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass
