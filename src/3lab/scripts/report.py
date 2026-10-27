"""Print the README result tables (Markdown) of the modulation effect.

Run as a module from ``src/3lab`` (or via ``make report3`` from the repo root):

    cd src/3lab && uv run python -m scripts.report

Unless a table says otherwise the modulating signal runs at 2 Hz with 100 %
depth, and levels are the RMS over all channels of a recording. The last table
sweeps the rate on recordings whose loudness changes over time.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from audio.wav_io import read_signal
from effects.modulation import (
    Waveform,
    expected_level_db,
    level_change_db,
    modulate,
    modulator,
)

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
RATE_HZ = 2.0
DEPTHS = (0.25, 0.5, 0.75, 1.0)
RATES_HZ = (0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 40.0)
# Recordings whose loudness changes over time, for the rate sweep.
_UNEVEN = ("Speech#1", "Music#1", "DTMF_tones")

_FORMULAS = {
    Waveform.SINE: "½(1 + cos 2πφ)",
    Waveform.TRIANGLE: "\\|1 − 2φ\\|",
    Waveform.SQUARE: "1 if φ < ½, else 0",
}
# Fourier series of u: the sidebands a tone f0 gets at f0 ± n·f_m.
_SIDEBANDS = {
    Waveform.SINE: "n = 1 only",
    Waveform.TRIANGLE: "odd n, ∝ 1/n²",
    Waveform.SQUARE: "odd n, ∝ 1/n",
}


def _name(path: Path) -> str:
    return re.sub(r"\s*\[.*?\]", "", path.stem)


def _table(title: str, headers: list[str], rows: list[list[str]]) -> None:
    """Markdown table with padded columns, so it also reads well as plain text:
    the first column is left-aligned, the others are centred."""
    widths = [
        max(3, len(header), *(len(row[i]) for row in rows))
        for i, header in enumerate(headers)
    ]

    def line(cells: list[str]) -> str:
        padded = [cells[0].ljust(widths[0])]
        padded += [
            cell.center(w) for cell, w in zip(cells[1:], widths[1:], strict=True)
        ]
        return "| " + " | ".join(padded) + " |"

    rule = ["-" * widths[0]] + [":" + "-" * (w - 2) + ":" for w in widths[1:]]
    print(f"\n#### {title}\n")
    print(line(headers))
    print("| " + " | ".join(rule) + " |")
    for row in rows:
        print(line(row))


def _largest_step(waveform: Waveform, sample_rate: int = 44100) -> float:
    """Largest change of m between two neighbouring samples."""
    m = modulator(sample_rate, sample_rate, waveform, RATE_HZ)
    return float(np.abs(np.diff(m)).max())


def main() -> None:
    labels = [w.label.split(" (")[0] for w in Waveform]
    _table(
        f"Table 1. Modulating signals (100 % depth; step at {RATE_HZ:g} Hz, 44.1 kHz)",
        [
            "Modulating signal",
            "u(φ)",
            "E[m²]",
            "Level change",
            "Largest step of m per sample",
            "Sidebands at f₀ ± n·f_m",
        ],
        [
            [
                w.label,
                _FORMULAS[w],
                f"{w.mean_square:.3f}",
                f"{expected_level_db(w, 1.0):+.2f} dB",
                f"{_largest_step(w):.2g}",
                _SIDEBANDS[w],
            ]
            for w in Waveform
        ],
    )

    rows = [
        ["**Expected**", "", *(f"{expected_level_db(w, 1.0):+.2f}" for w in Waveform)]
    ]
    for path in sorted(DATA_DIR.rglob("*.wav")):
        signal = read_signal(path)
        original = signal.real_amplitude()
        n, fs = signal.n_samples, signal.sample_rate
        levels = []
        for waveform in Waveform:
            processed = modulate(signal, modulator(n, fs, waveform, RATE_HZ))
            levels.append(
                f"{level_change_db(original, processed.real_amplitude()):+.2f}"
            )
        rows.append([_name(path), str(signal.n_channels), *levels])
    _table(
        f"Table 2. Measured RMS level change, dB ({RATE_HZ:g} Hz, 100 % depth)",
        ["Signal", "Channels", *labels],
        rows,
    )

    _table(
        "Table 3. Expected level change, dB, by depth",
        ["Modulating signal", *(f"{d:.0%}" for d in DEPTHS)],
        [
            [w.label, *(f"{expected_level_db(w, d):+.2f}" for d in DEPTHS)]
            for w in Waveform
        ],
    )

    rows = []
    for prefix in _UNEVEN:
        path = next(DATA_DIR.rglob(f"{prefix}*.wav"), None)
        if path is None:
            continue
        signal = read_signal(path)
        original = signal.real_amplitude()
        n, fs = signal.n_samples, signal.sample_rate
        for waveform in (Waveform.SINE, Waveform.SQUARE):
            levels = []
            for rate in RATES_HZ:
                processed = modulate(signal, modulator(n, fs, waveform, rate))
                level = level_change_db(original, processed.real_amplitude())
                levels.append(f"{level:+.2f}")
            rows.append([_name(path), waveform.label, *levels])
    _table(
        "Table 4. Measured RMS level change, dB, by rate (100 % depth)",
        ["Signal", "Modulating signal", *(f"{r:g} Hz" for r in RATES_HZ)],
        rows,
    )


if __name__ == "__main__":
    main()
