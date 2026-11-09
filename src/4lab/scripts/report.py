"""Print the README result tables (Markdown) of the spectrum analysis.

Run as a module from ``src/4lab`` (or via ``make report4`` from the repo root):

    cd src/4lab && uv run python -m scripts.report

As in the tool, multi-channel files are mixed to mono and the spectra are
relative to their largest value. Unless a table says otherwise, the window is
Hanning and a segment starts where the loudest 100 ms of the recording begins.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from analysis.spectrum import Spectrum, Window, loudest_start, spectrum, window
from audio.wav_io import read_signal

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
LENGTHS_MS = (10, 20, 30, 50, 100, 200, 300, 500, 1000)
MULTITONE_BAND = (285.0, 595.0)  # the 10 Hz-spaced lines 290 ... 590 Hz
PEAK_LEVEL = 0.1  # a peak must reach 10 % of the largest value

# Half-width of each window's main lobe in DFT bins: a peak must be the
# largest value at least this far on both sides.
_GUARD = {
    Window.RECTANGULAR: 1,
    Window.HANNING: 2,
    Window.HAMMING: 2,
    Window.BLACKMAN: 3,
}
_ORIGIN = {
    "speech": "voice",
    "music": "music",
    "dtmf": "telephone tones",
    "multitone": "test signal",
    "pure_tones": "test tones",
    "sinus": "test tone",
    "square": "generated",
    "noise": "noise",
}


def _name(path: Path) -> str:
    return re.sub(r"\s*\[.*?\]", "", path.stem)


def _origin(path: Path) -> str:
    lowered = path.name.lower()
    return next((kind for key, kind in _ORIGIN.items() if key in lowered), "—")


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


def _mix(prefix: str) -> tuple[int, np.ndarray]:
    signal = read_signal(next(DATA_DIR.rglob(f"{prefix}*.wav")))
    return signal.sample_rate, signal.channel_samples()


def _start(x: np.ndarray, fs: int) -> int:
    return loudest_start(x, round(0.1 * fs))


def _cut(x: np.ndarray, fs: int, ms: float, start: int) -> np.ndarray:
    """``ms`` of ``x`` from ``start``, moved back if it would run past the end."""
    n = round(ms * fs / 1000)
    start = max(0, min(start, x.size - n))
    return x[start : start + n]


def _peaks(values: np.ndarray, guard: int, level: float = PEAK_LEVEL) -> np.ndarray:
    """Indices of the local maxima that reach ``level`` of the largest value,
    strongest first."""
    padded = np.pad(values, guard, constant_values=-1.0)
    windows = sliding_window_view(padded, 2 * guard + 1)
    is_peak = (windows.max(axis=1) == values) & (values >= level * values.max())
    found = np.flatnonzero(is_peak)
    return found[np.argsort(-values[found], kind="stable")]


def _highest(values: np.ndarray, freqs: np.ndarray, level: float) -> float:
    """Highest frequency whose relative value reaches ``level``."""
    return float(freqs[np.flatnonzero(values >= level)[-1]])


def _centroid(values: np.ndarray, freqs: np.ndarray) -> float:
    return float((freqs * values).sum() / values.sum())


def _db(ratio: float) -> str:
    return f"{20 * math.log10(ratio):.1f}"


def _difference(a: Spectrum, b: Spectrum) -> float:
    """Relative change of the amplitude spectrum, in %."""
    x, y = a.relative_amplitude, b.relative_amplitude
    return 100 * float(np.linalg.norm(x - y) / np.linalg.norm(x))


def _window_properties(kind: Window, n: int = 1024, pad: int = 64):
    """Main lobe and side lobes of the window's own spectrum, in DFT bins."""
    w = window(kind, n)
    response = np.abs(np.fft.rfft(w, n * pad))
    response /= response[0]
    offset = np.arange(response.size) / pad
    first_zero = offset[np.argmax(np.diff(response) > 0)]
    width_3db = 2 * offset[np.argmax(response < 10 ** (-3 / 20))]
    side_lobe = response[offset > first_zero].max()
    return width_3db, first_zero, side_lobe, float(w.mean())


def _multitone_lines(spec: Spectrum) -> int:
    lo, hi = MULTITONE_BAND
    band = np.where(
        (spec.frequencies >= lo) & (spec.frequencies <= hi),
        spec.relative_amplitude,
        0.0,
    )
    return _peaks(band, 1).size


def frequency_content() -> None:
    rows = []
    for path in sorted(DATA_DIR.rglob("*.wav")):
        signal = read_signal(path)
        x, fs = signal.channel_samples(), signal.sample_rate
        start = _start(x, fs)
        spec = spectrum(_cut(x, fs, 100, start), fs, Window.HANNING)
        a, f = spec.relative_amplitude, spec.frequencies
        peaks = _peaks(a, _GUARD[Window.HANNING])
        if peaks.size > 10:
            dominant = f"none ({peaks.size} peaks ≥ 10 %)"
        else:
            dominant = ", ".join(f"{f[k]:.0f} ({a[k]:.2f})" for k in peaks[:5])
        rows.append(
            [
                _name(path),
                _origin(path),
                f"{start / fs:.2f}",
                dominant,
                f"{_highest(a, f, 0.01):.0f}",
                f"{_highest(a, f, 0.001):.0f}",
            ]
        )
    _table(
        "Table 1. Frequency content (loudest 100 ms, Δf = 10 Hz, Hanning window)",
        [
            "Signal",
            "Origin",
            "Start, s",
            "Dominant frequencies, Hz (relative \\|X\\|)",
            "Highest f with \\|X\\| ≥ 1 %, Hz",
            "… ≥ 0.1 %, Hz",
        ],
        rows,
    )


def noise_slopes() -> None:
    """Mean density one decade apart: white is flat, pink falls as 1/f and
    brown as 1/f^2 (10 and 20 dB per decade)."""
    rows = []
    for prefix, expected in (
        ("White_noise_uniform", "0 (flat)"),
        ("White_noise_gaussian", "0 (flat)"),
        ("Pink_noise", "−1 (1/f)"),
        ("Brown_noise", "−2 (1/f²)"),
    ):
        fs, x = _mix(prefix)
        spec = spectrum(x[: 10 * fs], fs, Window.HANNING)

        def band(lo: float, hi: float, spec=spec) -> float:
            f = spec.frequencies
            return float(spec.density[(f >= lo) & (f < hi)].mean())

        drop = 10 * math.log10(band(100, 200) / band(1000, 2000))
        alpha = round(-drop / 10, 2) + 0.0  # no "-0.00"
        rows.append([prefix, f"{drop:.1f}", f"{alpha:.2f}", expected])
    _table(
        "Table 2. Noises: spectral density at 100–200 Hz vs 1–2 kHz "
        "(whole file, up to 10 s)",
        ["Signal", "Drop per decade, dB", "S ∝ f^α, α", "Slides: α"],
        rows,
    )


def segment_length() -> None:
    prefixes = ("Sinus_125Hz", "Multitone", "DTMF", "Speech#1")
    signals = {prefix: _mix(prefix) for prefix in prefixes}
    starts = {prefix: _start(x, fs) for prefix, (fs, x) in signals.items()}
    guard = _GUARD[Window.HANNING]
    rows = []
    for ms in LENGTHS_MS:
        specs = {
            prefix: spectrum(_cut(x, fs, ms, starts[prefix]), fs, Window.HANNING)
            for prefix, (fs, x) in signals.items()
        }
        sine, dtmf, speech = specs["Sinus_125Hz"], specs["DTMF"], specs["Speech#1"]
        voice = _peaks(speech.relative_amplitude, guard)
        rows.append(
            [
                str(ms),
                f"{1000 / ms:.3g}",
                f"{sine.frequencies[np.argmax(sine.amplitude)]:.1f}",
                str(_multitone_lines(specs["Multitone"])),
                str(_peaks(dtmf.relative_amplitude, guard).size),
                f"{voice.size} ({speech.frequencies[voice].min():.0f})",
            ]
        )
    _table(
        "Table 3. Segment length T (Hanning window)",
        [
            "T, ms",
            "Δf = 1/T, Hz",
            "Sinus_125Hz: peak at, Hz",
            "Multitone: lines seen in 290–590 Hz (of 23)",
            "DTMF_tones from a tone onset: peaks ≥ 10 %",
            "Speech#1: peaks ≥ 10 % (lowest, Hz)",
        ],
        rows,
    )


def windows() -> None:
    fs_m, multi = _mix("Multitone")
    fs_s, sine = _mix("Sinus_500Hz")
    multi_part = _cut(multi, fs_m, 200, _start(multi, fs_m))
    sine_part = _cut(sine, fs_s, 30, _start(sine, fs_s))
    rows = []
    for kind in Window:
        width, zero, side, gain = _window_properties(kind)
        spec = spectrum(sine_part, fs_s, kind)
        peak = spec.frequencies[np.argmax(spec.amplitude)]
        far = np.abs(spec.frequencies - peak) > 10 * spec.resolution_hz
        rows.append(
            [
                kind.label,
                f"{width:.2f}",
                f"{zero:.2f}",
                _db(side),
                f"{gain:.2f}",
                str(_multitone_lines(spectrum(multi_part, fs_m, kind))),
                _db(spec.relative_amplitude[far].max()),
            ]
        )
    _table(
        "Table 4. Window functions",
        [
            "Window",
            "Main lobe at −3 dB, bins",
            "Main lobe to first zero, ± bins",
            "Highest side lobe, dB",
            "Coherent gain Σl/N",
            "Multitone, 200 ms: lines seen (of 23)",
            "Sinus_500Hz, 30 ms: leakage > 10 Δf from the peak, dB",
        ],
        rows,
    )


def boundary_shift() -> None:
    kinds = (Window.RECTANGULAR, Window.HANNING)
    rows = []
    for prefix in (
        "Sinus_500Hz",
        "Square_440Hz",
        "DTMF_tones",
        "Speech#1",
        "Music#1",
        "White_noise_gaussian",
    ):
        fs, x = _mix(prefix)
        n, s0 = round(0.03 * fs), _start(x, fs)  # 30 + 5 ms fit in the 100 ms
        cells = []
        for shift in (1, round(0.001 * fs), round(0.005 * fs)):
            for kind in kinds:
                a = spectrum(x[s0 : s0 + n], fs, kind)
                b = spectrum(x[s0 + shift : s0 + shift + n], fs, kind)
                cells.append(f"{_difference(a, b):.1f}")
        rows.append([prefix, *cells])
    _table(
        "Table 5. Change of the amplitude spectrum when a 30 ms segment is moved, "
        "‖ΔX‖ / ‖X‖, %",
        [
            "Signal",
            "1 sample: Rect.",
            "1 sample: Hanning",
            "1 ms: Rect.",
            "1 ms: Hanning",
            "5 ms: Rect.",
            "5 ms: Hanning",
        ],
        rows,
    )


def amplitude_vs_density() -> None:
    rows = []
    for path in sorted(DATA_DIR.rglob("*.wav")):
        signal = read_signal(path)
        x, fs = signal.channel_samples(), signal.sample_rate
        spec = spectrum(_cut(x, fs, 100, _start(x, fs)), fs, Window.HANNING)
        a, s, f = spec.relative_amplitude, spec.relative_density, spec.frequencies
        guard = _GUARD[Window.HANNING]
        rows.append(
            [
                _name(path),
                str(_peaks(a, guard).size),
                str(_peaks(s, guard).size),
                f"{_highest(a, f, 0.01):.0f}",
                f"{_highest(s, f, 0.01):.0f}",
                f"{_centroid(a, f):.0f}",
                f"{_centroid(s, f):.0f}",
            ]
        )
    _table(
        "Table 6. Amplitude spectrum |X| vs spectral density S = |X|² "
        "(loudest 100 ms, Hanning window)",
        [
            "Signal",
            "Peaks ≥ 10 %: \\|X\\|",
            "Peaks ≥ 10 %: S",
            "Highest f ≥ 1 %: \\|X\\|, Hz",
            "Highest f ≥ 1 %: S, Hz",
            "Centroid of \\|X\\|, Hz",
            "Centroid of S, Hz",
        ],
        rows,
    )


def main() -> None:
    frequency_content()
    noise_slopes()
    segment_length()
    windows()
    boundary_shift()
    amplitude_vs_density()


if __name__ == "__main__":
    main()
