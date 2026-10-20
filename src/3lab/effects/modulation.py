from __future__ import annotations

import math
from enum import Enum

import numpy as np

from audio.audio_signal import AudioSignal

DEFAULT_RATE_HZ = 2.0
RATE_RANGE_HZ = (0.1, 50.0)
DEFAULT_DEPTH = 100  # percent
DEPTH_RANGE = (0, 100)


class Waveform(Enum):
    SINE = ("Sine", 3 / 8)
    TRIANGLE = ("Triangle", 1 / 3)
    SQUARE = ("Square", 1 / 2)
    SAWTOOTH = ("Sawtooth (ramp down)", 1 / 3)

    def __init__(self, label: str, mean_square: float) -> None:
        self.label = label
        self.mean_square = mean_square  # E[u^2] over one period


def shape(phase: np.ndarray, waveform: Waveform) -> np.ndarray:
    """Unipolar wave u in [0, 1] of a phase in periods (one period per unit),
    starting at full level: u(0) = 1."""
    if waveform is Waveform.SINE:
        return 0.5 * (1.0 + np.cos(2 * np.pi * phase))
    if waveform is Waveform.TRIANGLE:
        return np.abs(1.0 - 2.0 * phase)
    if waveform is Waveform.SQUARE:
        return np.where(phase < 0.5, 1.0, 0.0)
    return 1.0 - phase  # sawtooth: instant attack, linear decay


def modulator(
    n: int,
    sample_rate: int,
    waveform: Waveform,
    rate_hz: float,
    depth: float = 1.0,
) -> np.ndarray:
    """m[k] = 1 - depth * (1 - u(k * rate / fs mod 1)) for k = 0 .. n - 1.

    m swings between 1 - depth and 1: depth 1 goes from silence to full level,
    depth 0 leaves the signal unchanged. The phase is taken from the absolute
    sample index, so m is continuous over the whole recording.
    """
    phase = np.arange(n) * (rate_hz / sample_rate) % 1.0
    return 1.0 - depth * (1.0 - shape(phase, waveform))


def modulate(signal: AudioSignal, m: np.ndarray) -> AudioSignal:
    """s~ = m * s: every channel is multiplied by the same m(t), on the real
    amplitude scale, and rounded back to the source's quantization levels."""
    amplitude = signal.real_amplitude()
    gain = m[:, None] if amplitude.ndim > 1 else m
    return signal.with_amplitude(amplitude * gain)


def rms(x: np.ndarray) -> float:
    return math.sqrt(float(np.mean(np.square(x, dtype=np.float64)))) if x.size else 0.0


def level_change_db(original: np.ndarray, processed: np.ndarray) -> float:
    """RMS level of ``processed`` relative to ``original``, in dB."""
    reference = rms(original)
    if reference == 0:
        return float("nan")
    ratio = rms(processed) / reference
    return 20 * math.log10(ratio) if ratio > 0 else float("-inf")


def expected_level_db(waveform: Waveform, depth: float) -> float:
    """Level change for a signal that does not depend on m: 10 log10 E[m^2],
    with E[m^2] = 1 - d + d^2 E[u^2], because E[u] = 1/2 for every shape."""
    return 10 * math.log10(1.0 - depth + depth**2 * waveform.mean_square)
