"""Print the README result tables (Markdown) for every WAV under ``data/``.

Run as a module from ``src/2lab`` (or via ``make report2`` from the repo root):

    cd src/2lab && uv run python -m scripts.report

Unless a table says otherwise: L = 16 bins over the whole signal's min-max
(shared by all frames), 20 ms frames with 50 % overlap, and multi-channel files
mixed to mono.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from analysis.entropy import BinRange, EntropyAnalysis, analyze
from analysis.summary import signal_type
from audio.audio_signal import AudioSignal
from audio.wav_io import read_signal

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
_TYPE_ORDER = ("periodic", "pseudo-periodic", "random")


def _name(path: Path) -> str:
    return re.sub(r"\s*\[.*?\]", "", path.stem)


def _table(title: str, headers: list[str], rows: list[list[str]]) -> None:
    print(f"\n#### {title}\n")
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join(["---"] + [":-:"] * (len(headers) - 1)) + "|")
    for row in rows:
        print("| " + " | ".join(row) + " |")


def _mean_std(a: EntropyAnalysis) -> str:
    return f"{a.local_mean:.2f} ± {a.local_std:.2f}"


def _longest_active_run(a: EntropyAnalysis) -> tuple[int, int]:
    """Samples of the longest run of frames that are not silent, i.e. whose
    values do not all fall into a single bin."""
    active = np.concatenate(([False], a.frame_h > 0, [False]))
    changes = np.flatnonzero(active[1:] != active[:-1])
    starts, ends = changes[::2], changes[1::2]
    i = int(np.argmax(ends - starts))
    return a.framing.span(starts[i])[0], a.framing.span(ends[i] - 1)[1]


def main() -> None:
    recordings: list[tuple[str, str, AudioSignal, np.ndarray]] = []
    for path in sorted(DATA_DIR.rglob("*.wav")):
        signal = read_signal(path)
        kind = signal_type(path.name)
        recordings.append((kind, _name(path), signal, signal.channel_samples(None)))
    order = {kind: i for i, kind in enumerate(_TYPE_ORDER)}
    recordings.sort(key=lambda r: (order.get(r[0], len(order)), r[1]))

    rows = []
    for kind, name, signal, x in recordings:
        a = analyze(x, signal.sample_rate)
        rows.append(
            [
                name,
                kind,
                f"{a.entropy:.2f}",
                f"{a.entropy / a.h_max:.2f}",
                _mean_std(a),
                f"{a.local_min:.2f} – {a.local_max:.2f}",
                f"{a.gap:.2f}",
            ]
        )
    _table(
        "Global and local entropy (L = 16, 20 ms frames, shared bins)",
        [
            "Signal",
            "Type",
            "H, bits",
            "H / Hmax",
            "Local H",
            "Local min – max",
            "H − local mean",
        ],
        rows,
    )

    bin_counts = (8, 16, 32, 64)
    rows = []
    for _, name, signal, x in recordings:
        cells = []
        for bins in bin_counts:
            a = analyze(x, signal.sample_rate, bins=bins)
            cells.append(f"{a.entropy:.2f} ({a.entropy / a.h_max:.2f})")
        rows.append([name, *cells])
    _table(
        "Global entropy H, bits (and H / Hmax) for different numbers of bins",
        ["Signal", *(f"L = {bins}" for bins in bin_counts)],
        rows,
    )

    settings = [(mode, ms) for mode in BinRange for ms in (20, 30)]
    rows = []
    for _, name, signal, x in recordings:
        cells = [
            _mean_std(analyze(x, signal.sample_rate, ms, bin_range=mode))
            for mode, ms in settings
        ]
        rows.append([name, *cells])
    _table(
        "Local entropy (mean ± std, bits) by bin range and frame length",
        ["Signal", *(f"{mode.short}, {ms} ms" for mode, ms in settings)],
        rows,
    )

    rows = []
    for _, name, signal, x in recordings:
        if signal.n_channels == 1:
            continue
        per_channel = [
            analyze(signal.channel_samples(ch), signal.sample_rate).entropy
            for ch in range(signal.n_channels)
        ]
        rows.append(
            [
                name,
                str(signal.n_channels),
                f"{min(per_channel):.2f} – {max(per_channel):.2f}",
                f"{analyze(x, signal.sample_rate).entropy:.2f}",
            ]
        )
    _table(
        "Multi-channel recordings: single channels vs the mix",
        ["Signal", "Channels", "H of one channel (min – max)", "H of the mix"],
        rows,
    )

    rows = []
    for _, name, signal, x in recordings:
        a = analyze(x, signal.sample_rate)
        s0, s1 = _longest_active_run(a)
        if s1 - s0 > 0.95 * x.size:
            continue
        segment = a.segment_histogram(x[s0:s1])
        fs = signal.sample_rate
        rows.append(
            [
                name,
                f"{a.entropy:.2f}",
                f"{s0 / fs:.2f} – {s1 / fs:.2f}",
                f"{segment.entropy:.2f}",
            ]
        )
    _table(
        "Whole recording vs its longest non-silent segment (shared bins)",
        ["Signal", "H of the whole file", "Segment, s", "H of the segment"],
        rows,
    )


if __name__ == "__main__":
    main()
