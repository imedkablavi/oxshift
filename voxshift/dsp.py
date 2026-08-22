from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .voices import get_preset


@dataclass(slots=True)
class DSPSettings:
    preset: str = "Clean"
    gain_db: float = 0.0
    wet: float = 1.0
    gate_db: float = -55.0
    lowpass_hz: float | None = None
    highpass_hz: float | None = None
    drive: float | None = None
    robot_hz: float | None = None
    tremolo_hz: float | None = None
    echo_ms: float | None = None
    echo_mix: float | None = None
    compressor: float | None = None
    pitch_semitones: float | None = None
    formant_color: float | None = None


class VoiceDSP:
    """Allocation-conscious real-time DSP rack used by OxShift's local mode."""

    def __init__(self, sample_rate: float, channels: int = 1) -> None:
        self.sample_rate = float(sample_rate)
        self.channels = channels
        self.phase_robot = 0.0
        self.phase_tremolo = 0.0
        self._lp_state = np.zeros(channels, dtype=np.float32)
        self._hp_lp_state = np.zeros(channels, dtype=np.float32)
        self._color_lp_state = np.zeros(channels, dtype=np.float32)
        self._echo = np.zeros((max(1, int(self.sample_rate * 0.8)), channels), dtype=np.float32)
        self._echo_pos = 0
        self._pitch = None
        self.pitch_backend = "disabled"
        try:
            from pedalboard import PitchShift

            self._pitch = PitchShift(semitones=0.0)
            self.pitch_backend = "pedalboard/rubberband"
        except Exception:
            self._pitch = None

    @staticmethod
    def _db_to_amp(db: float) -> float:
        return float(10.0 ** (db / 20.0))

    def reset(self) -> None:
        self.phase_robot = 0.0
        self.phase_tremolo = 0.0
        self._lp_state.fill(0)
        self._hp_lp_state.fill(0)
        self._color_lp_state.fill(0)
        self._echo.fill(0)
        self._echo_pos = 0
        if self._pitch is not None:
            try:
                self._pitch.reset()
            except Exception:
                pass

    def _one_pole_lowpass(self, x: np.ndarray, cutoff: float, state: np.ndarray) -> np.ndarray:
        cutoff = float(np.clip(cutoff, 20.0, self.sample_rate * 0.45))
        dt = 1.0 / self.sample_rate
        rc = 1.0 / (2.0 * math.pi * cutoff)
        a = dt / (rc + dt)
        y = np.empty_like(x)
        s = state.copy()
        for i in range(x.shape[0]):
            s += a * (x[i] - s)
            y[i] = s
        state[:] = s
        return y

    def _bandwidth(self, x: np.ndarray, highpass_hz: float, lowpass_hz: float) -> np.ndarray:
        y = x
        if highpass_hz > 25.0:
            low = self._one_pole_lowpass(y, highpass_hz, self._hp_lp_state)
            y = y - low
        if lowpass_hz < self.sample_rate * 0.44:
            y = self._one_pole_lowpass(y, lowpass_hz, self._lp_state)
        return y

    def _pitch_shift(self, x: np.ndarray, semitones: float) -> np.ndarray:
        semitones = float(np.clip(semitones, -12.0, 12.0))
        if abs(semitones) < 0.01 or self._pitch is None:
            return x
        try:
            self._pitch.semitones = semitones
            channels_first = np.ascontiguousarray(x.T, dtype=np.float32)
            shifted = self._pitch.process(
                channels_first,
                self.sample_rate,
                buffer_size=max(256, x.shape[0]),
                reset=False,
            )
            shifted = np.asarray(shifted, dtype=np.float32)
            if shifted.ndim == 1:
                shifted = shifted[None, :]
            shifted = shifted.T
            if shifted.shape == x.shape:
                return shifted
        except Exception:
            pass
        return x

    def _formant_color(self, x: np.ndarray, amount: float) -> np.ndarray:
        """Low-cost spectral-envelope color control.

        This is intentionally labelled as an experimental timbre/formant-color control in
        the UI; it is not a full independent formant shifter. Positive values emphasize
        articulation, negative values darken the spectral envelope.
        """
        amount = float(np.clip(amount, -1.0, 1.0))
        if abs(amount) < 0.001:
            return x
        low = self._one_pole_lowpass(x, 1200.0, self._color_lp_state)
        if amount > 0:
            high = x - low
            return (x + high * (0.9 * amount)).astype(np.float32, copy=False)
        dark = (-amount)
        return (x * (1.0 - 0.55 * dark) + low * (0.55 * dark)).astype(np.float32, copy=False)

    def _ring_mod(self, x: np.ndarray, hz: float) -> np.ndarray:
        if hz <= 0.0:
            return x
        n = x.shape[0]
        omega = 2.0 * math.pi * hz / self.sample_rate
        phases = self.phase_robot + omega * np.arange(n, dtype=np.float32)
        carrier = np.sin(phases)[:, None].astype(np.float32, copy=False)
        self.phase_robot = float((self.phase_robot + omega * n) % (2.0 * math.pi))
        return (x * carrier).astype(np.float32, copy=False)

    def _tremolo(self, x: np.ndarray, hz: float) -> np.ndarray:
        if hz <= 0.0:
            return x
        n = x.shape[0]
        omega = 2.0 * math.pi * hz / self.sample_rate
        phases = self.phase_tremolo + omega * np.arange(n, dtype=np.float32)
        lfo = (0.72 + 0.28 * np.sin(phases))[:, None].astype(np.float32, copy=False)
        self.phase_tremolo = float((self.phase_tremolo + omega * n) % (2.0 * math.pi))
        return (x * lfo).astype(np.float32, copy=False)

    def _echo_block(self, x: np.ndarray, delay_ms: float, mix: float) -> np.ndarray:
        mix = float(np.clip(mix, 0.0, 0.65))
        if delay_ms <= 0.0 or mix <= 0.0:
            return x
        delay = int(np.clip(self.sample_rate * delay_ms / 1000.0, 1, len(self._echo) - 1))
        out = np.empty_like(x)
        for i in range(x.shape[0]):
            read_pos = (self._echo_pos - delay) % len(self._echo)
            delayed = self._echo[read_pos]
            sample = x[i] + delayed * mix
            out[i] = sample
            self._echo[self._echo_pos] = x[i] + delayed * (mix * 0.32)
            self._echo_pos = (self._echo_pos + 1) % len(self._echo)
        return out

    @staticmethod
    def _compress(x: np.ndarray, amount: float) -> np.ndarray:
        amount = float(np.clip(amount, 0.0, 1.0))
        if amount <= 0.0:
            return x
        threshold = 0.72 - (0.45 * amount)
        ratio = 1.0 + (7.0 * amount)
        mag = np.abs(x)
        over = np.maximum(mag - threshold, 0.0)
        compressed_mag = mag - over + (over / ratio)
        return (np.sign(x) * compressed_mag).astype(np.float32, copy=False)

    def process(self, block: np.ndarray, settings: DSPSettings) -> np.ndarray:
        x = np.asarray(block, dtype=np.float32)
        if x.ndim == 1:
            x = x[:, None]
        dry = x
        preset = get_preset(settings.preset)

        gate = self._db_to_amp(settings.gate_db)
        work = np.where(np.abs(x) >= gate, x, 0.0).astype(np.float32, copy=False)

        highpass = preset.highpass_hz if settings.highpass_hz is None else settings.highpass_hz
        lowpass = preset.lowpass_hz if settings.lowpass_hz is None else settings.lowpass_hz
        drive = preset.drive if settings.drive is None else settings.drive
        robot_hz = preset.robot_hz if settings.robot_hz is None else settings.robot_hz
        tremolo_hz = preset.tremolo_hz if settings.tremolo_hz is None else settings.tremolo_hz
        echo_ms = preset.echo_ms if settings.echo_ms is None else settings.echo_ms
        echo_mix = preset.echo_mix if settings.echo_mix is None else settings.echo_mix
        compressor = preset.compressor if settings.compressor is None else settings.compressor
        pitch = preset.pitch_semitones if settings.pitch_semitones is None else settings.pitch_semitones
        formant_color = preset.formant_color if settings.formant_color is None else settings.formant_color

        work = self._bandwidth(work, highpass, lowpass)
        work = self._pitch_shift(work, pitch)
        work = self._formant_color(work, formant_color)
        if drive > 1.001:
            work = np.tanh(work * drive).astype(np.float32, copy=False)
        work = self._ring_mod(work, robot_hz)
        work = self._tremolo(work, tremolo_hz)
        work = self._echo_block(work, echo_ms, echo_mix)
        work = self._compress(work, compressor)

        gain = self._db_to_amp(settings.gain_db + preset.gain_db)
        wet = float(np.clip(settings.wet, 0.0, 1.0))
        out = ((dry * (1.0 - wet)) + (work * wet)) * gain
        return np.clip(out, -1.0, 1.0).astype(np.float32, copy=False)
