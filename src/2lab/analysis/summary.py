from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from analysis.entropy import (
    DEFAULT_BINS,
    DEFAULT_FRAME_MS,
    BinRange,
    EntropyAnalysis,
    analyze,
)
from audio.wav_io import read_signal

# Signal class of the recordings, recognised from the file name.
_SIGNAL_TYPES = {
    "sinus": "periodic",
    "pure_tones": "periodic",
    "multitone": "periodic",
    "dtmf": "periodic",
    "square": "periodic",
    "speech": "pseudo-periodic",
    "music": "pseudo-periodic",
    "noise": "random",
}


def signal_type(name: str) -> str:
    lowered = name.lower()
    return next((kind for key, kind in _SIGNAL_TYPES.items() if key in lowered), "—")


@dataclass(frozen=True)
class FileSummary:
    path: Path
    n_channels: int
    sample_rate: int
    duration_s: float
    analysis: EntropyAnalysis

    @property
    def kind(self) -> str:
        return signal_type(self.path.name)


def summarize_file(
    path: str | Path,
    frame_ms: float = DEFAULT_FRAME_MS,
    bins: int = DEFAULT_BINS,
    bin_range: BinRange = BinRange.SIGNAL,
) -> FileSummary:
    """Entropy analysis of a whole file, multi-channel files mixed to mono."""
    signal = read_signal(path)
    analysis = analyze(
        signal.channel_samples(None), signal.sample_rate, frame_ms, bins, bin_range
    )
    return FileSummary(
        path=signal.path,
        n_channels=signal.n_channels,
        sample_rate=signal.sample_rate,
        duration_s=signal.duration_s,
        analysis=analysis,
    )
