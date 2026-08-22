from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VoicePreset:
    name: str
    category: str
    description: str
    emoji: str
    gain_db: float = 0.0
    wet: float = 1.0
    gate_db: float = -55.0
    lowpass_hz: float = 20000.0
    highpass_hz: float = 20.0
    drive: float = 1.0
    robot_hz: float = 0.0
    tremolo_hz: float = 0.0
    echo_ms: float = 0.0
    echo_mix: float = 0.0
    compressor: float = 0.0


VOICE_PRESETS: tuple[VoicePreset, ...] = (
    VoicePreset("Clean", "Essential", "Transparent processing for calls and streaming.", "●", compressor=0.18),
    VoicePreset("Broadcast", "Essential", "Tighter, louder voice for podcasts and streams.", "◉", gain_db=2.5, highpass_hz=90, lowpass_hz=13500, compressor=0.58),
    VoicePreset("Deep", "Human", "Darker, heavier tone with controlled dynamics.", "▼", gain_db=1.0, lowpass_hz=2600, drive=1.12, compressor=0.38),
    VoicePreset("Bright", "Human", "Clearer presence for soft microphones.", "△", highpass_hz=150, lowpass_hz=15500, gain_db=1.5, compressor=0.28),
    VoicePreset("Anonymous", "Character", "Dark masked voice for fictional or privacy-oriented use.", "◈", lowpass_hz=1700, drive=1.7, robot_hz=38, compressor=0.25),
    VoicePreset("Robot", "Character", "Classic metallic ring-modulated robot effect.", "▣", robot_hz=70, drive=1.2),
    VoicePreset("Android", "Character", "Cleaner synthetic voice with faster modulation.", "◇", highpass_hz=110, lowpass_hz=5200, robot_hz=115, drive=1.35, compressor=0.2),
    VoicePreset("Radio", "Device", "Narrow-band communications radio effect.", "⌁", highpass_hz=300, lowpass_hz=3400, drive=2.2, compressor=0.3),
    VoicePreset("Telephone", "Device", "Classic telephone bandwidth and saturation.", "☎", highpass_hz=380, lowpass_hz=3000, drive=1.75, compressor=0.2),
    VoicePreset("Intercom", "Device", "Compressed public-address / intercom character.", "▤", highpass_hz=220, lowpass_hz=4300, drive=1.5, compressor=0.65),
    VoicePreset("Ghost", "Creative", "Unstable ambience using tremolo and short echo.", "≈", lowpass_hz=6500, tremolo_hz=5.5, echo_ms=115, echo_mix=0.24),
    VoicePreset("Cyber", "Creative", "Digital sci-fi tone with subtle modulation.", "✦", highpass_hz=120, lowpass_hz=7200, robot_hz=42, tremolo_hz=7.0, drive=1.3, echo_ms=38, echo_mix=0.12),
    VoicePreset("Megaphone", "Creative", "Aggressive mid-focused megaphone sound.", "◁", highpass_hz=420, lowpass_hz=4200, drive=2.8, compressor=0.48),
    VoicePreset("Low-Fi", "Creative", "Dark, deliberately degraded voice texture.", "▧", highpass_hz=170, lowpass_hz=2350, drive=1.55, tremolo_hz=2.2),
)

PRESET_BY_NAME = {preset.name: preset for preset in VOICE_PRESETS}
CATEGORIES = ("All",) + tuple(dict.fromkeys(p.category for p in VOICE_PRESETS))


def get_preset(name: str) -> VoicePreset:
    return PRESET_BY_NAME.get(name, PRESET_BY_NAME["Clean"])
