from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import cached_property

import numpy as np

DEFAULT_LENGTH_MS = 30.0
MIN_LENGTH_MS = 1.0


class Window(Enum):
    RECTANGULAR = ("Rectangular (no window)", (1.0,))
    HANNING = ("Hanning", (0.5, 0.5))
    HAMMING = ("Hamming", (0.54, 0.46))
    BLACKMAN = ("Blackman", (0.42, 0.5, 0.08))

    def __init__(self, label: str, coefficients: tuple[float, ...]) -> None:
        self.label = label
        self.coefficients = coefficients


def window(kind: Window, n: int) -> np.ndarray:
    """l(n) = a0 - a1 cos(2πn / (N-1)) + a2 cos(4πn / (N-1)), n = 0 .. N-1."""
    phase = 2 * np.pi * np.arange(n) / max(n - 1, 1)
    w = np.zeros(n)
    for i, a in enumerate(kind.coefficients):
        w += (-1) ** i * a * np.cos(i * phase)
    return w


def _relative(values: np.ndarray) -> np.ndarray:
    peak = values.max() if values.size else 0.0
    return values / peak if peak > 0 else np.zeros_like(values)


@dataclass(frozen=True)
class Spectrum:
    sample_rate: int
    window: Window
    n: int
    frequencies: np.ndarray  # f_k = k * fs / N, k = 0 .. N/2
    amplitude: np.ndarray  # |X(k)|
    density: np.ndarray  # S(k) = X(k) * conj(X(k)) = |X(k)|^2

    @property
    def resolution_hz(self) -> float:
        return self.sample_rate / self.n

    @cached_property
    def relative_amplitude(self) -> np.ndarray:
        return _relative(self.amplitude)

    @cached_property
    def relative_density(self) -> np.ndarray:
        return _relative(self.density)


def spectrum(x: np.ndarray, sample_rate: int, kind: Window) -> Spectrum:
    """X(k) = sum x(n) l(n) e^(-j2πnk/N) for k = 0 .. N/2 (the rest mirrors it,
    since x is real), computed with the FFT."""
    n = x.size
    amplitude = np.abs(np.fft.rfft(x * window(kind, n)))
    return Spectrum(
        sample_rate=sample_rate,
        window=kind,
        n=n,
        frequencies=np.fft.rfftfreq(n, 1 / sample_rate),
        amplitude=amplitude,
        density=amplitude**2,
    )


def loudest_start(x: np.ndarray, n: int) -> int:
    """Start of the ``n``-sample block of ``x`` with the most energy."""
    if n >= x.size:
        return 0
    energy = np.concatenate(([0.0], np.cumsum(np.square(x))))
    return int(np.argmax(energy[n:] - energy[:-n]))
