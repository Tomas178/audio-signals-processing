from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


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
    def n_frames(self) -> int:
        return int(self.samples.shape[0])

    @property
    def duration_s(self) -> float:
        return self.n_frames / self.sample_rate

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

    def real_amplitude(self) -> np.ndarray:
        if self.is_float:
            return self.samples
        container_bits = self.samples.dtype.itemsize * 8
        shift = container_bits - self.valid_bits
        if shift > 0:
            return self.samples >> shift
        return self.samples

    @property
    def amplitude_range(self) -> tuple[float, float]:
        if self.is_float:
            peak = float(np.max(np.abs(self.samples))) if self.n_frames else 1.0
            peak = max(peak, 1.0)
            return (-peak, peak)
        limit = 2 ** (self.valid_bits - 1)
        return (float(-limit), float(limit - 1))

    def frame_at_time(self, t_seconds: float) -> int:
        frame = int(round(t_seconds * self.sample_rate))
        return max(0, min(frame, self.n_frames))
