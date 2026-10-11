"""Headless verification of the entropy analysis (no display needed).

Run as a module from ``src/2lab`` (or via ``make test2`` from the repo root):

    cd src/2lab && QT_QPA_PLATFORM=offscreen uv run python -m scripts.selftest

It checks the entropy formula on signals whose entropy is known exactly, the
50 % overlap framing at the common sample rates, that the vectorised per-frame
entropies equal a plain frame-by-frame loop over ``np.histogram``, and that
every recording under ``data/`` gives entropies within [0, log2 L]. Finally it
drives the GUI offscreen: load files, change every setting, select a frame and
compare files.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from analysis.entropy import (
    DEFAULT_BINS,
    BinRange,
    Framing,
    bin_counts,
    entropy_bits,
    frame_entropies,
    histogram,
)
from analysis.summary import summarize_file

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
L = DEFAULT_BINS


def _expect(errors: list[str], name: str, got: float, want: float, tol=1e-12):
    if not abs(got - want) <= tol:
        errors.append(f"{name}: got {got:.6f}, expected {want:.6f} (+/- {tol:g})")


def _check_formula() -> list[str]:
    """Histograms whose entropy is known exactly."""
    errors: list[str] = []
    _expect(errors, "constant signal", histogram(np.full(1000, 7.0), L).entropy, 0.0)
    two_levels = np.repeat([-1.0, 1.0], 500)
    _expect(errors, "two equal levels", histogram(two_levels, L).entropy, 1.0)
    levels = np.repeat(np.arange(L, dtype=np.float64), 100)  # one level per bin
    _expect(errors, f"{L} equal levels", histogram(levels, L).entropy, math.log2(L))
    _expect(errors, "empty histogram", float(entropy_bits(np.zeros(L))), 0.0)
    return errors


def _check_distributions() -> list[str]:
    """A sine follows the arcsine law, uniform noise fills every bin equally,
    and shuffling the samples does not change the entropy."""
    errors: list[str] = []
    period = 997
    sine = np.sin(2 * np.pi * (np.arange(period * 1000) + 0.5) / period)
    p = np.diff(np.arcsin(np.linspace(-1.0, 1.0, L + 1))) / np.pi
    theory = float(-(p * np.log2(p)).sum())
    sine_h = histogram(sine, L).entropy
    _expect(errors, "sine vs arcsine law", sine_h, theory, 0.01)
    noise = np.random.default_rng(0).uniform(-1.0, 1.0, 1_000_000)
    _expect(errors, "uniform noise", histogram(noise, L).entropy, math.log2(L), 0.01)
    shuffled = np.random.default_rng(1).permutation(sine)
    _expect(errors, "shuffled sine", histogram(shuffled, L).entropy, sine_h)
    return errors


def _check_framing() -> list[str]:
    """Frames are 2 x hop long (exactly 50 % overlap), within one sample of
    the requested duration, and only whole frames are taken."""
    errors: list[str] = []
    for rate in (8000, 16000, 22050, 32000, 44100, 48000, 96000):
        for frame_ms in (20, 25, 30):
            framing = Framing.from_ms(frame_ms, rate)
            label = f"{frame_ms} ms @ {rate} Hz"
            if framing.length != 2 * framing.hop:
                errors.append(f"{label}: length {framing.length} != 2 x hop")
            if abs(framing.length - frame_ms * rate / 1000) > 1:
                errors.append(f"{label}: {framing.length} samples")
            n = rate + 123
            count = framing.count(n)
            if framing.span(count - 1)[1] > n or framing.span(count)[1] <= n:
                errors.append(f"{label}: {count} frames do not fit {n} samples")
    if Framing.from_ms(20, 16000).count(100) != 0:
        errors.append("a signal shorter than one frame must give no frames")
    return errors


def _naive_entropy(frame: np.ndarray, lo: float, hi: float) -> float:
    counts, _ = np.histogram(frame, bins=L, range=(lo, hi))
    p = counts[counts > 0] / counts.sum()
    return float(-(p * np.log2(p)).sum())


def _check_vectorised() -> list[str]:
    """Block-wise bincount equals np.histogram frame by frame, in both bin-range
    modes and across the borders of the processing blocks."""
    errors: list[str] = []
    rng = np.random.default_rng(2)
    gain = np.repeat(rng.uniform(0.05, 1.0, 40), 500)
    x = rng.normal(size=gain.size) * gain  # 20 000 samples of changing level
    framing = Framing.from_ms(20, 8000)  # 160-sample frames, hop 80
    for value_range in (None, (float(x.min()), float(x.max()))):
        mode = "own" if value_range is None else "shared"
        fast = frame_entropies(x, framing, L, value_range, block=1000)
        slow = []
        for k in range(framing.count(x.size)):
            s0, s1 = framing.span(k)
            frame = x[s0:s1]
            lo, hi = value_range or (frame.min(), frame.max())
            slow.append(_naive_entropy(frame, lo, hi))
        if fast.shape != (len(slow),) or not np.allclose(fast, slow, atol=1e-12):
            errors.append(f"{mode}-range frame entropies differ from a plain loop")
    big = rng.normal(size=1_500_000)  # longer than one processing block
    lo, hi = float(big.min()), float(big.max())
    reference, _ = np.histogram(big, bins=L, range=(lo, hi))
    if not np.array_equal(bin_counts(big, L, lo, hi), reference):
        errors.append("whole-signal bin counts differ from np.histogram")
    return errors


def _check_file(path: Path) -> list[str]:
    errors: list[str] = []
    summary = summarize_file(path)
    a = summary.analysis
    if not 0.0 <= a.entropy <= a.h_max + 1e-9:
        errors.append(f"H = {a.entropy} outside [0, {a.h_max}]")
    if a.n_frames == 0:
        errors.append("no whole frame")
    elif not (
        np.all(np.isfinite(a.frame_h))
        and a.frame_h.min() >= 0.0
        and a.frame_h.max() <= a.h_max + 1e-9
    ):
        errors.append(f"local entropies outside [0, {a.h_max}]")
    print(
        f"  {path.name:46s} {summary.kind:16s} H = {a.entropy:.3f}  "
        f"local {a.local_mean:.3f} +/- {a.local_std:.3f}"
    )
    return errors


def _check_gui(files: list[Path]) -> list[str]:
    """Drive the window offscreen; any exception also fails the test."""
    from PyQt6 import QtWidgets

    from ui.main_window import MainWindow

    mono = next((p for p in files if p.name.startswith("Sinus_500Hz")), None)
    multi = next((p for p in files if p.name.startswith("Speech#1")), None)
    if mono is None or multi is None:
        return ["Sinus_500Hz / Speech#1 sample files not found"]
    errors: list[str] = []
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow()

    window.load(mono)
    if window._channel.isEnabled():
        errors.append("the channel choice must be disabled for a mono file")
    window.load(multi)
    if window._channel.currentData() is not None:
        errors.append("a multi-channel file must start on the channel mix")

    window._channel.setCurrentIndex(3)
    window._frame_ms.setValue(30)
    window._bins.setValue(32)
    window._bin_range.setCurrentIndex(1)
    a = window._analysis
    if (a.bins, a.framing.length, a.bin_range) != (32, 1440, BinRange.OWN):
        errors.append("the settings were not applied to the analysis")

    k = int(a.frame_h.argmax())
    window.select_frame(k)
    if window._span != a.framing.span(k) or (
        f"H = {a.frame_h[k]:.3f} bits" not in window._segment_info.text()
    ):
        errors.append("selecting a frame must show that frame's entropy")
    window.grab()

    window.compare([mono, multi])
    if window._compare is None or window._compare.table.rowCount() != 2:
        errors.append("the comparison table should list both files")
    else:
        window._compare.close()
    window.close()
    app.processEvents()
    return errors


def main() -> int:
    failed = 0
    checks = {
        "formula": _check_formula,
        "distributions": _check_distributions,
        "framing": _check_framing,
        "vectorised": _check_vectorised,
    }
    for name, check in checks.items():
        for err in check():
            print(f"  {name} FAIL: {err}")
            failed += 1

    files = sorted(DATA_DIR.rglob("*.wav"))
    if not files:
        print(f"No .wav files found under {DATA_DIR}")
        return 2
    print(f"Testing {len(files)} files under {DATA_DIR} (channels mixed, L = {L}):")
    for path in files:
        try:
            errors = _check_file(path)
        except Exception as exc:
            print(f"  {path.name:46s} ERROR: {exc}")
            failed += 1
            continue
        for err in errors:
            print(f"      FAIL: {err}")
        failed += 1 if errors else 0

    for err in _check_gui(files):
        print(f"  GUI FAIL: {err}")
        failed += 1

    print("-" * 70)
    if failed:
        print(f"FAILED: {failed} problem(s).")
        return 1
    print("OK: formula, framing, per-frame entropies and GUI all verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
