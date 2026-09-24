"""In-memory representation of a decoded audio signal.

This module is pure logic (no Qt / no I/O): it holds the samples read from a
WAV file together with the metadata needed to display them, and exposes the
derived views the UI needs -- notably :meth:`AudioSignal.real_amplitude`, which
returns the samples on the true quantization scale (requirement 5).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

# WAVE format tags (wFormatTag).
FMT_PCM = 0x0001
FMT_FLOAT = 0x0003
FMT_EXTENSIBLE = 0xFFFE


@dataclass
class AudioSignal:
    """A fully in-memory audio signal plus the metadata used for display.

    ``raw_data`` and ``fmt_chunk`` are the verbatim bytes of the source file's
    ``data`` and ``fmt `` chunks; they let a segment be exported with the exact
    original format (bit depth, channel layout, ...) without re-encoding.
    """

    path: Path
    samples: np.ndarray  # shape (n,) for mono or (n, channels) otherwise
    sample_rate: int
    n_channels: int
    bits_per_sample: int  # container width declared in the file's fmt header
    valid_bits: int  # real quantization depth (valid bits per sample)
    audio_format: int  # resolved format: FMT_PCM or FMT_FLOAT
    raw_data: bytes  # verbatim data-chunk bytes (for faithful export)
    frame_size: int  # bytes per frame (nBlockAlign)
    fmt_chunk: bytes  # verbatim fmt-chunk bytes (for faithful export)

    # -- basic derived properties -------------------------------------------

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

    # -- sample access ------------------------------------------------------

    def channel(self, index: int) -> np.ndarray:
        """Return the samples of a single channel."""
        if self.samples.ndim == 1:
            return self.samples
        return self.samples[:, index]

    def real_amplitude(self) -> np.ndarray:
        """Samples expressed on the true quantization scale (requirement 5).

        scipy left-justifies sub-container bit depths into the container integer
        type (e.g. a packed 24-bit sample becomes an int32 shifted left by 8).
        Shifting back down by ``container_bits - valid_bits`` recovers the real
        integer code values (24-bit lands in the +/-2**23 range instead of
        +/-2**31). The discarded low bits were zero-fill, so the shift is exact.
        Float signals are already real and are returned unchanged.
        """
        if self.is_float:
            return self.samples
        container_bits = self.samples.dtype.itemsize * 8
        shift = container_bits - self.valid_bits
        if shift > 0:
            return self.samples >> shift
        return self.samples

    @property
    def amplitude_range(self) -> tuple[float, float]:
        """Full-scale amplitude range for the Y axis, per quantization depth."""
        if self.is_float:
            peak = float(np.max(np.abs(self.samples))) if self.n_frames else 1.0
            peak = max(peak, 1.0)
            return (-peak, peak)
        limit = 2 ** (self.valid_bits - 1)
        return (float(-limit), float(limit - 1))

    def frame_at_time(self, t_seconds: float) -> int:
        """Frame index for a time in seconds, clamped to ``[0, n_frames]``."""
        frame = int(round(t_seconds * self.sample_rate))
        return max(0, min(frame, self.n_frames))
