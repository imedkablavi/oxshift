from __future__ import annotations

import re


TOKEN = re.compile(r"^(?:<([a-zA-Z0-9_]+)>|(.))$")


def normalize_hotkey(value: str) -> str:
    """Validate the structural subset of pynput GlobalHotKeys used by OxShift.

    Examples: ``<f8>``, ``<ctrl>+<alt>+1`` and ``<shift>+a``. Backend availability is
    intentionally not checked here because Wayland can reject otherwise valid hotkeys.
    """
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    if any(char.isspace() for char in raw):
        raise ValueError("hotkey cannot contain spaces")
    parts = raw.split("+")
    if not 1 <= len(parts) <= 5 or any(not part for part in parts):
        raise ValueError("use pynput syntax such as <ctrl>+<alt>+1 or <f8>")
    normalized: list[str] = []
    for part in parts:
        match = TOKEN.match(part)
        if not match:
            raise ValueError(f"invalid hotkey token: {part}")
        named, literal = match.groups()
        if named is not None:
            normalized.append(f"<{named}>")
        else:
            if literal == "+":
                raise ValueError("the + key is not supported in this compact editor")
            normalized.append(literal)
    if len(set(normalized)) != len(normalized):
        raise ValueError("hotkey contains a duplicate key/modifier")
    return "+".join(normalized)
