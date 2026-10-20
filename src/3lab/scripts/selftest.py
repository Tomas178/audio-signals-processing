"""Headless verification of the modulation effect (no display needed).

Run as a module from ``src/3lab`` (or via ``make test3`` from the repo root):

    cd src/3lab && QT_QPA_PLATFORM=offscreen uv run python -m scripts.selftest

It checks the four modulator shapes against their known means, that the
vectorised modulator and effect equal a plain per-sample loop, that a processed
signal is saved bit-exactly in every encoding, that the level drop matches
10 log10 E[m^2], and that every recording under ``data/`` is processed without
clipping. Finally it drives the GUI offscreen (without playing any sound).
"""

from __future__ import annotations

import math
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from audio.audio_signal import AudioSignal
from audio.wav_io import read_signal, write_signal
from effects.modulation import (
    Waveform,
    expected_level_db,
    level_change_db,
    modulate,
    modulator,
)

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
_ENCODINGS = ("PCM_U8", "PCM_16", "PCM_24", "PCM_32", "FLOAT", "DOUBLE")
_FORMAT_FIELDS = (
    "file_format",
    "subtype",
    "sample_rate",
    "n_channels",
    "valid_bits",
    "channel_mask",
)


def _expect(errors: list[str], name: str, got: float, want: float, tol=1e-12):
    if not abs(got - want) <= tol:
        errors.append(f"{name}: got {got:.6f}, expected {want:.6f} (+/- {tol:g})")


def _check_shapes() -> list[str]:
    """Over whole periods every shape stays in [0, 1], starts at full level,
    repeats exactly, averages 1/2 and has the mean square the level drop uses."""
    errors: list[str] = []
    rate, fs, period = 8.0, 8192, 1024  # rate / fs = 2**-10: every phase is exact
    for waveform in Waveform:
        name = waveform.label
        m = modulator(10 * period, fs, waveform, rate)
        if m.min() < 0.0 or m.max() > 1.0:
            errors.append(f"{name}: m outside [0, 1]")
        if not np.array_equal(m[period:], m[:-period]):
            errors.append(f"{name}: m does not repeat every {period} samples")
        _expect(errors, f"{name} m[0]", float(m[0]), 1.0)
        _expect(errors, f"{name} min", float(m.min()), 0.0, 1e-3)
        _expect(errors, f"{name} mean", float(m.mean()), 0.5, 1e-3)
        mean_square = float(np.mean(m**2))
        _expect(errors, f"{name} mean square", mean_square, waveform.mean_square, 1e-3)

        if not np.array_equal(
            modulator(period, fs, waveform, rate, 0.0), np.ones(period)
        ):
            errors.append(f"{name}: depth 0 must give m = 1 everywhere")
        partial = modulator(period, fs, waveform, rate, 0.4)
        _expect(errors, f"{name} depth 0.4 min", float(partial.min()), 0.6, 1e-3)
        _expect(errors, f"{name} depth 0.4 max", float(partial.max()), 1.0)
    return errors


def _plain_modulator(n, fs, waveform, rate, depth) -> list[float]:
    m = []
    for k in range(n):
        phase = k * (rate / fs) % 1.0
        if waveform is Waveform.SINE:
            u = 0.5 * (1.0 + math.cos(2 * math.pi * phase))
        elif waveform is Waveform.TRIANGLE:
            u = abs(1.0 - 2.0 * phase)
        elif waveform is Waveform.SQUARE:
            u = 1.0 if phase < 0.5 else 0.0
        else:
            u = 1.0 - phase
        m.append(1.0 - depth * (1.0 - u))
    return m


def _check_loop() -> list[str]:
    """The vectorised modulator and effect equal a plain per-sample loop."""
    errors: list[str] = []
    rng = np.random.default_rng(3)
    samples = rng.integers(-32768, 32768, size=(3000, 2), dtype=np.int16)
    signal = AudioSignal(
        path=Path("loop.wav"),
        samples=samples,
        sample_rate=8000,
        n_channels=2,
        bits_per_sample=16,
        valid_bits=16,
        subtype="PCM_16",
        file_format="WAV",
    )
    for waveform in Waveform:
        m = modulator(signal.n_samples, signal.sample_rate, waveform, 3.7, 0.8)
        plain_m = _plain_modulator(signal.n_samples, 8000, waveform, 3.7, 0.8)
        if not np.allclose(m, plain_m, rtol=0, atol=1e-12):
            errors.append(f"{waveform.label}: modulator differs from a plain loop")
        gains = m.tolist()
        plain = [
            [round(gains[k] * int(value)) for value in frame]
            for k, frame in enumerate(samples)
        ]
        if not np.array_equal(modulate(signal, m).samples, plain):
            errors.append(f"{waveform.label}: m * s differs from a plain loop")
    return errors


def _check_encodings() -> list[str]:
    """A stereo tone in every encoding is modulated, saved and read back: the
    file keeps the source format and exactly the processed samples."""
    errors: list[str] = []
    t = np.arange(4800) / 48000
    tone = 0.5 * np.column_stack((np.sin(2 * np.pi * 440 * t), np.cos(1.5 * t)))
    with tempfile.TemporaryDirectory() as tmp:
        for subtype in _ENCODINGS:
            source = Path(tmp) / f"{subtype}.wav"
            sf.write(source, tone, 48000, subtype=subtype)
            signal = read_signal(source)
            m = modulator(signal.n_samples, signal.sample_rate, Waveform.SINE, 5.0)
            processed = modulate(signal, m)
            dst = Path(tmp) / f"{subtype}_processed.wav"
            write_signal(dst, processed)
            reread = read_signal(dst)
            for field in _FORMAT_FIELDS:
                got, want = getattr(reread, field), getattr(signal, field)
                if got != want:
                    errors.append(f"{subtype}: saved {field} {got!r} != {want!r}")
            if not np.array_equal(reread.samples, processed.samples):
                errors.append(f"{subtype}: saved samples differ from processed")
    return errors


def _check_level() -> list[str]:
    """On noise that does not depend on m the level drops by 10 log10 E[m^2]."""
    errors: list[str] = []
    fs = 8000
    noise = np.random.default_rng(4).uniform(-1.0, 1.0, 40 * fs)
    for waveform in Waveform:
        for depth in (1.0, 0.5):
            m = modulator(noise.size, fs, waveform, 2.0, depth)
            got = level_change_db(noise, m * noise)
            want = expected_level_db(waveform, depth)
            _expect(errors, f"{waveform.label} depth {depth:g}", got, want, 0.05)
    return errors


def _check_file(path: Path) -> list[str]:
    errors: list[str] = []
    signal = read_signal(path)
    n, fs = signal.n_samples, signal.sample_rate
    original = signal.real_amplitude()
    processed = modulate(signal, modulator(n, fs, Waveform.SINE, 2.0))
    if (processed.samples.shape, processed.samples.dtype) != (
        signal.samples.shape,
        signal.samples.dtype,
    ):
        errors.append("the processed samples changed shape or type")
    # float64 so that abs(-2**15) cannot overflow the integer type
    if np.any(
        np.abs(processed.real_amplitude().astype(np.float64))
        > np.abs(original.astype(np.float64))
    ):
        errors.append("|processed| exceeds |original| (clipping or overflow)")
    bypass = modulate(signal, modulator(n, fs, Waveform.SINE, 2.0, 0.0))
    if not np.array_equal(bypass.samples, signal.samples):
        errors.append("depth 0 must give back the source samples exactly")

    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / "processed.wav"
        write_signal(dst, processed)
        reread = read_signal(dst)
        for field in _FORMAT_FIELDS:
            got, want = getattr(reread, field), getattr(signal, field)
            if got != want:
                errors.append(f"saved {field} {got!r} != source {want!r}")
        if not np.array_equal(reread.samples, processed.samples):
            errors.append("saved samples differ from the processed ones")

    levels = []
    for waveform in Waveform:
        p = modulate(signal, modulator(n, fs, waveform, 2.0))
        levels.append(f"{level_change_db(original, p.real_amplitude()):+6.2f}")
    print(f"  {path.name:50s} {signal.n_channels}ch {fs:>6d}Hz  " + " ".join(levels))
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

    window._waveform.setCurrentIndex(2)
    window._rate.setValue(5.0)
    window._depth.setValue(60)
    window._channel.setCurrentIndex(3)
    signal = window._signal
    m = modulator(signal.n_samples, signal.sample_rate, Waveform.SQUARE, 5.0, 0.6)
    if not np.array_equal(window._processed.samples, modulate(signal, m).samples):
        errors.append("the settings were not applied to the processed signal")

    rendered = read_signal(window._player.render(window._processed))
    if not np.array_equal(rendered.samples, window._processed.samples):
        errors.append("the playback file differs from the processed signal")
    window.grab()
    window.close()
    app.processEvents()
    return errors


def main() -> int:
    failed = 0
    checks = {
        "shapes": _check_shapes,
        "plain loop": _check_loop,
        "encodings": _check_encodings,
        "level": _check_level,
    }
    for name, check in checks.items():
        for err in check():
            print(f"  {name} FAIL: {err}")
            failed += 1

    files = sorted(DATA_DIR.rglob("*.wav"))
    if not files:
        print(f"No .wav files found under {DATA_DIR}")
        return 2
    header = " ".join(f"{w.name.lower()[:6]:>6s}" for w in Waveform)
    print(f"Testing {len(files)} files under {DATA_DIR}")
    print(f"  {'RMS level change at 2 Hz, 100 % depth, dB:':64s} {header}")
    for path in files:
        try:
            errors = _check_file(path)
        except Exception as exc:
            print(f"  {path.name:50s} ERROR: {exc}")
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
    print("OK: shapes, plain loop, saving, level drop, files and GUI all verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
