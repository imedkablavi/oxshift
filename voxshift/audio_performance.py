from __future__ import annotations


PERFORMANCE_PRESETS: dict[str, tuple[int, int]] = {
    "Low latency": (48000, 128),
    "Balanced": (48000, 256),
    "Stable": (48000, 512),
}

VALID_SAMPLE_RATES = (44100, 48000, 96000)
VALID_BLOCK_SIZES = (128, 256, 512, 1024)


def latency_ms(sample_rate: int, blocksize: int) -> float:
    rate = int(sample_rate)
    block = int(blocksize)
    if rate <= 0 or block <= 0:
        raise ValueError("sample rate and block size must be positive")
    return block / rate * 1000.0


def validate_audio_format(sample_rate: int, blocksize: int) -> tuple[int, int]:
    rate = int(sample_rate)
    block = int(blocksize)
    if rate not in VALID_SAMPLE_RATES:
        raise ValueError(f"unsupported sample rate: {rate}")
    if block not in VALID_BLOCK_SIZES:
        raise ValueError(f"unsupported block size: {block}")
    return rate, block
