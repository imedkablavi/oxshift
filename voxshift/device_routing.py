from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResolvedDevice:
    index: int | None
    name: str
    exact: bool
    reason: str


def _normalize(name: str) -> str:
    return " ".join(str(name or "").lower().split())


def resolve_device(items: list[tuple[int, str]], preferred_name: str, *, virtual_output: bool = False) -> ResolvedDevice:
    """Resolve a saved device name after reboot/reconnect without trusting stale indices."""
    if not items:
        return ResolvedDevice(None, "", False, "no devices")

    preferred = _normalize(preferred_name)
    if preferred:
        for index, name in items:
            if _normalize(name) == preferred:
                return ResolvedDevice(index, name, True, "exact saved device")

        tokens = [t for t in preferred.split() if len(t) >= 3]
        scored: list[tuple[int, int, str]] = []
        for index, name in items:
            candidate = _normalize(name)
            score = sum(1 for token in tokens if token in candidate)
            if score:
                scored.append((score, index, name))
        if scored:
            scored.sort(reverse=True)
            _, index, name = scored[0]
            return ResolvedDevice(index, name, False, "closest saved device")

    if virtual_output:
        for index, name in items:
            lowered = _normalize(name)
            if "oxshift" in lowered or "voxshift" in lowered:
                return ResolvedDevice(index, name, False, "preferred virtual output")

    index, name = items[0]
    return ResolvedDevice(index, name, False, "fallback first available")
