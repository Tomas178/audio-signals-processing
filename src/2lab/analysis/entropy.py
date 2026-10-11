from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

DEFAULT_BINS = 16
BINS_RANGE = (2, 256)
DEFAULT_FRAME_MS = 20
FRAME_MS_RANGE = (20, 30)

_BLOCK = 1 << 20  # samples binned per numpy pass; bounds memory on long files


class BinRange(Enum):
    SIGNAL = ("shared", "Whole-signal range (shared bins)")
    OWN = ("own", "Own range of each frame / segment")

    def __init__(self, short: str, label: str) -> None:
        self.short = short
        self.label = label


def _bin_index(x: np.ndarray, bins: int, lo, hi) -> np.ndarray:
    """Equal-width bin of every value over [lo, hi]; the maximum goes into the
    last bin and a zero-width range puts everything into the first one."""
    width = np.asarray(hi, dtype=np.float64) - lo
    width = np.where(width > 0, width, 1.0)
    idx = np.floor((x - lo) * bins / width).astype(np.intp)
    return np.clip(idx, 0, bins - 1, out=idx)


def bin_counts(
    x: np.ndarray, bins: int, lo: float, hi: float, block: int = _BLOCK
) -> np.ndarray:
    counts = np.zeros(bins, dtype=np.int64)
    for start in range(0, x.size, block):
        idx = _bin_index(x[start : start + block], bins, lo, hi)
        counts += np.bincount(idx, minlength=bins)
    return counts


def entropy_bits(counts: np.ndarray) -> np.ndarray:
    """H = -sum(f_i * log2 f_i) along the last axis, with f_i = n_i / N.

    Written as f * log2(1 / f) so empty bins (0 * log 0 := 0) and a single
    full bin give exactly +0.0.
    """
    counts = np.asarray(counts, dtype=np.float64)
    total = counts.sum(axis=-1, keepdims=True)
    f = np.divide(counts, total, out=np.zeros_like(counts), where=total > 0)
    inverse = np.divide(1.0, f, out=np.ones_like(f), where=f > 0)
    return (f * np.log2(inverse)).sum(axis=-1)


@dataclass(frozen=True)
class Histogram:
    edges: np.ndarray
    counts: np.ndarray

    @property
    def frequencies(self) -> np.ndarray:
        total = self.counts.sum()
        return self.counts / total if total else np.zeros(self.counts.size)

    @property
    def entropy(self) -> float:
        return float(entropy_bits(self.counts))


def histogram(
    x: np.ndarray, bins: int, value_range: tuple[float, float] | None = None
) -> Histogram:
    """Histogram over ``value_range``, or over the data's own min-max."""
    if value_range is None:
        value_range = (float(x.min()), float(x.max())) if x.size else (0.0, 0.0)
    lo, hi = value_range
    if hi <= lo:
        hi = lo + 1.0
    return Histogram(np.linspace(lo, hi, bins + 1), bin_counts(x, bins, lo, hi))


@dataclass(frozen=True)
class Framing:
    """Frames of ``2 * hop`` samples every ``hop`` samples: exactly 50 % overlap."""

    sample_rate: int
    hop: int

    @classmethod
    def from_ms(cls, frame_ms: float, sample_rate: int) -> Framing:
        return cls(sample_rate, max(1, round(frame_ms * sample_rate / 2000)))

    @property
    def length(self) -> int:
        return 2 * self.hop

    @property
    def length_ms(self) -> float:
        return 1000 * self.length / self.sample_rate

    @property
    def hop_ms(self) -> float:
        return 1000 * self.hop / self.sample_rate

    def count(self, n_samples: int) -> int:
        if n_samples < self.length:
            return 0
        return 1 + (n_samples - self.length) // self.hop

    def span(self, k: int) -> tuple[int, int]:
        start = k * self.hop
        return start, start + self.length

    def centers_s(self, count: int) -> np.ndarray:
        return np.arange(1, count + 1) * self.hop / self.sample_rate


def frame_entropies(
    x: np.ndarray,
    framing: Framing,
    bins: int,
    value_range: tuple[float, float] | None = None,
    block: int = _BLOCK,
) -> np.ndarray:
    """Entropy of every whole frame; ``value_range=None`` bins each frame over
    its own min-max, otherwise all frames share bins over ``value_range``."""
    n = framing.count(x.size)
    result = np.empty(n)
    if n == 0:
        return result
    frames = sliding_window_view(x, framing.length)[:: framing.hop]
    rows = max(1, block // framing.length)
    for start in range(0, n, rows):
        chunk = frames[start : start + rows]
        if value_range is None:
            lo = chunk.min(axis=1, keepdims=True)
            hi = chunk.max(axis=1, keepdims=True)
        else:
            lo, hi = value_range
        idx = _bin_index(chunk, bins, lo, hi)
        idx += bins * np.arange(len(chunk))[:, None]
        counts = np.bincount(idx.ravel(), minlength=bins * len(chunk))
        result[start : start + len(chunk)] = entropy_bits(counts.reshape(-1, bins))
    return result


@dataclass(frozen=True)
class EntropyAnalysis:
    bins: int
    bin_range: BinRange
    framing: Framing
    whole: Histogram
    frame_h: np.ndarray

    @property
    def entropy(self) -> float:
        return self.whole.entropy

    @property
    def h_max(self) -> float:
        return float(np.log2(self.bins))

    @property
    def n_frames(self) -> int:
        return self.frame_h.size

    def _frame_stat(self, reduce) -> float:
        return float(reduce(self.frame_h)) if self.n_frames else float("nan")

    @property
    def local_mean(self) -> float:
        return self._frame_stat(np.mean)

    @property
    def local_std(self) -> float:
        return self._frame_stat(np.std)

    @property
    def local_min(self) -> float:
        return self._frame_stat(np.min)

    @property
    def local_max(self) -> float:
        return self._frame_stat(np.max)

    @property
    def gap(self) -> float:
        return self.entropy - self.local_mean

    def segment_histogram(self, samples: np.ndarray) -> Histogram:
        if self.bin_range is BinRange.SIGNAL:
            shared = (float(self.whole.edges[0]), float(self.whole.edges[-1]))
            return histogram(samples, self.bins, shared)
        return histogram(samples, self.bins)


def analyze(
    x: np.ndarray,
    sample_rate: int,
    frame_ms: float = DEFAULT_FRAME_MS,
    bins: int = DEFAULT_BINS,
    bin_range: BinRange = BinRange.SIGNAL,
) -> EntropyAnalysis:
    framing = Framing.from_ms(frame_ms, sample_rate)
    whole = histogram(x, bins)
    shared = (float(whole.edges[0]), float(whole.edges[-1]))
    value_range = shared if bin_range is BinRange.SIGNAL else None
    return EntropyAnalysis(
        bins=bins,
        bin_range=bin_range,
        framing=framing,
        whole=whole,
        frame_h=frame_entropies(x, framing, bins, value_range),
    )
