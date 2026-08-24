from __future__ import annotations

from copy import deepcopy


PROFILE_TEMPLATES: dict[str, dict] = {
    "Gaming": {
        "voice": "Clean",
        "gain_db": 1.0,
        "wet": 0.9,
        "gate_db": -58.0,
        "pitch_semitones": 0.0,
        "formant_color": 0.0,
        "eq_enabled": True,
        "eq_80_db": 1.0,
        "eq_250_db": -0.5,
        "eq_1000_db": 0.0,
        "eq_4000_db": 1.5,
        "eq_12000_db": 0.5,
        "noise_suppression": 0.55,
        "agc_enabled": True,
        "agc_target_dbfs": -18.0,
        "agc_max_gain_db": 10.0,
        "cleanup_backend": "auto",
        "echo_cancellation": False,
        "soundboard_master": 0.9,
        "soundboard_duck_db": 4.0,
        "allow_overlap": True,
        "sample_rate": 48000,
        "blocksize": 256,
    },
    "Streaming": {
        "voice": "Broadcast",
        "gain_db": 1.5,
        "wet": 1.0,
        "gate_db": -55.0,
        "pitch_semitones": 0.0,
        "formant_color": 0.05,
        "eq_enabled": True,
        "eq_80_db": 1.5,
        "eq_250_db": -1.0,
        "eq_1000_db": 0.0,
        "eq_4000_db": 2.5,
        "eq_12000_db": 1.0,
        "noise_suppression": 0.45,
        "agc_enabled": True,
        "agc_target_dbfs": -18.0,
        "agc_max_gain_db": 12.0,
        "cleanup_backend": "auto",
        "echo_cancellation": False,
        "soundboard_master": 0.85,
        "soundboard_duck_db": 6.0,
        "allow_overlap": True,
        "sample_rate": 48000,
        "blocksize": 256,
    },
    "Calls": {
        "voice": "Clean",
        "gain_db": 0.0,
        "wet": 0.75,
        "gate_db": -60.0,
        "pitch_semitones": 0.0,
        "formant_color": 0.0,
        "eq_enabled": True,
        "eq_80_db": -3.0,
        "eq_250_db": -1.5,
        "eq_1000_db": 0.5,
        "eq_4000_db": 2.0,
        "eq_12000_db": -1.0,
        "noise_suppression": 0.65,
        "agc_enabled": True,
        "agc_target_dbfs": -20.0,
        "agc_max_gain_db": 12.0,
        "cleanup_backend": "auto",
        "echo_cancellation": False,
        "soundboard_master": 0.7,
        "soundboard_duck_db": 10.0,
        "allow_overlap": False,
        "sample_rate": 48000,
        "blocksize": 256,
    },
}


def template_settings(name: str) -> dict:
    if name not in PROFILE_TEMPLATES:
        raise KeyError(name)
    return deepcopy(PROFILE_TEMPLATES[name])


def unique_profile_name(existing: list[str], base: str) -> str:
    used = {str(name).casefold() for name in existing}
    if base.casefold() not in used:
        return base
    counter = 2
    while f"{base} {counter}".casefold() in used:
        counter += 1
    return f"{base} {counter}"
