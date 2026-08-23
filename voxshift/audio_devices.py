from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Any


@dataclass(frozen=True, slots=True)
class DeviceIdentity:
    index: int | None
    name: str
    hostapi: int | None = None


def capture_identity(devices: Iterable[Mapping[str, Any]], index: int | None) -> DeviceIdentity:
    if index is None:
        return DeviceIdentity(None, "", None)
    rows = list(devices)
    if not (0 <= int(index) < len(rows)):
        return DeviceIdentity(index, "", None)
    row = rows[int(index)]
    return DeviceIdentity(int(index), str(row.get("name", "")), row.get("hostapi"))


def resolve_device_index(
    devices: Iterable[Mapping[str, Any]],
    identity: DeviceIdentity,
    direction: str,
) -> int | None:
    """Resolve a device after PortAudio re-enumeration.

    Device numeric indexes are not stable across USB/Bluetooth reconnects. Prefer an exact
    name+host API match, then exact name, then a normalized name match. Only fall back to the
    old numeric index when it still points at a device that supports the requested direction.
    """
    rows = list(devices)
    channel_key = "max_input_channels" if direction == "input" else "max_output_channels"

    def usable(row: Mapping[str, Any]) -> bool:
        try:
            return int(row.get(channel_key, 0) or 0) > 0
        except (TypeError, ValueError):
            return False

    wanted = identity.name.strip()
    if wanted:
        exact_host = [
            i
            for i, row in enumerate(rows)
            if usable(row)
            and str(row.get("name", "")).strip() == wanted
            and (identity.hostapi is None or row.get("hostapi") == identity.hostapi)
        ]
        if exact_host:
            return exact_host[0]

        exact = [
            i for i, row in enumerate(rows)
            if usable(row) and str(row.get("name", "")).strip() == wanted
        ]
        if exact:
            return exact[0]

        normalized = " ".join(wanted.casefold().split())
        fuzzy = [
            i
            for i, row in enumerate(rows)
            if usable(row)
            and " ".join(str(row.get("name", "")).casefold().split()) == normalized
        ]
        if fuzzy:
            return fuzzy[0]

    if identity.index is not None and 0 <= identity.index < len(rows) and usable(rows[identity.index]):
        return identity.index
    return None
