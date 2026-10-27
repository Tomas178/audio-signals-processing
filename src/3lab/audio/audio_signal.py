from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

_CHANNEL_LAYOUTS = {
    1: ["Mono"],
    2: ["Left", "Right"],
    6: ["FL", "FR", "C", "LFE", "SL", "SR"],
    8: ["FL", "FR", "C", "LFE", "BL", "BR", "SL", "SR"],
}

_SPEAKER_BITS = [
    "FL",
    "FR",
    "C",
    "LFE",
    "BL",
    "BR",
    "FLC",
    "FRC",
    "BC",
    "SL",
    "SR",
    "TC",
    "TFL",
    "TFC",
    "TFR",
    "TBL",
    "TBC",
    "TBR",
]


@dataclass
class AudioSignal:
    path: Path
    samples: np.ndarray
    sample_rate: int
    n_channels: int
    bits_per_sample: int
    valid_bits: int
    subtype: str
    file_format: str
    channel_mask: int = 0

    @property
    def n_samples(self) -> int:
        return int(self.samples.shape[0])

    @property
    def duration_s(self) -> float:
        return self.n_samples / self.sample_rate

    @property
    def is_float(self) -> bool:
        return self.samples.dtype.kind == "f"

    @property
    def format_name(self) -> str:
        return "IEEE float" if self.is_float else "PCM"

    @property
    def amplitude_label(self) -> str:
        if self.is_float:
            return f"Amplitude (IEEE float, {self.bits_per_sample}-bit)"

        return f"Amplitude ({self.valid_bits}-bit PCM)"

    @property
    def channel_names(self) -> list[str]:
        n = self.n_channels
        if self.channel_mask:
            names = [
                name
                for bit, name in enumerate(_SPEAKER_BITS)
                if self.channel_mask >> bit & 1
            ][:n]
            return names + [f"Ch {i + 1}" for i in range(len(names), n)]

        if n in _CHANNEL_LAYOUTS:
            return list(_CHANNEL_LAYOUTS[n])

        return [f"Ch {i + 1}" for i in range(n)]

    @property
    def _container_shift(self) -> int:
        return self.samples.dtype.itemsize * 8 - self.valid_bits

    def real_amplitude(self) -> np.ndarray:
        if self.is_float:
            return self.samples

        shift = self._container_shift
        if shift > 0:
            return self.samples >> shift

        return self.samples

    def with_amplitude(self, amplitude: np.ndarray) -> AudioSignal:
        """A copy holding ``amplitude`` (on the ``real_amplitude`` scale) as its
        samples: integer PCM is rounded to the nearest quantization level,
        clipped to full scale and left-justified again, so the copy is stored
        exactly as ``read_signal`` would read it back from a saved file."""
        dtype = self.samples.dtype
        if self.is_float:
            return replace(self, samples=amplitude.astype(dtype))

        lo, hi = self.amplitude_range
        levels = np.rint(amplitude)
        np.clip(levels, lo, hi, out=levels)
        samples = levels.astype(dtype)
        shift = self._container_shift
        if shift > 0:
            samples <<= shift

        return replace(self, samples=samples)

    def channel_samples(self) -> np.ndarray:
        """Real amplitude as float64, with multiple channels averaged into one."""
        amplitude = self.real_amplitude()
        if amplitude.ndim == 1:
            return amplitude.astype(np.float64)
        return amplitude.mean(axis=1, dtype=np.float64)

    @property
    def amplitude_range(self) -> tuple[float, float]:
        if self.is_float:
            peak = float(np.max(np.abs(self.samples))) if self.n_samples else 1.0
            peak = max(peak, 1.0)
            return (-peak, peak)
        limit = 2 ** (self.valid_bits - 1)
        return (float(-limit), float(limit - 1))

    def sample_at_time(self, t_seconds: float) -> int:
        sample = int(round(t_seconds * self.sample_rate))
        return max(0, min(sample, self.n_samples))
