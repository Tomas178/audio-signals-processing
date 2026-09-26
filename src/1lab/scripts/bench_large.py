"""Benchmark waveform rendering for very long signals (requirement 8).

Compares full render time with peak downsampling + clip-to-view (what the app
uses) against a naive render of every sample, on the largest bundled file and on
a synthesized multi-minute signal. Run headless as a module from ``src/1lab``:

    cd src/1lab && QT_QPA_PLATFORM=offscreen uv run python -m scripts.bench_large

Numbers are approximate (they depend on the machine) but show the order of
magnitude difference the downsampling makes.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PyQt6 import QtWidgets

from audio.audio_signal import AudioSignal
from audio.wav_io import read_signal

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "Garsai1"
WIDTH, HEIGHT = 1200, 700


def _synth(minutes: float, sample_rate: int = 48000) -> AudioSignal:
    n = int(minutes * 60 * sample_rate)
    t = np.arange(n, dtype=np.float64) / sample_rate
    wave = 0.6 * np.sin(2 * np.pi * 440.0 * t) + 0.2 * np.sin(2 * np.pi * 3.0 * t)
    samples = (wave * 32767).astype(np.int16)
    return AudioSignal(
        path=Path(f"synthetic_{minutes:g}min.wav"),
        samples=samples,
        sample_rate=sample_rate,
        n_channels=1,
        bits_per_sample=16,
        valid_bits=16,
        raw_data=samples.tobytes(),
        frame_size=2,
        fmt_chunk=b"",
    )


def _build(signal: AudioSignal, downsample: bool):
    amp = signal.real_amplitude()
    time_axis = np.arange(signal.n_frames, dtype=np.float64) / signal.sample_rate
    widget = pg.GraphicsLayoutWidget()
    widget.resize(WIDTH, HEIGHT)
    plots = []
    for ch in range(signal.n_channels):
        plot = widget.addPlot(row=ch, col=0)
        if downsample:
            plot.setDownsampling(auto=True, mode="peak")
            plot.setClipToView(True)
        else:
            plot.setDownsampling(auto=False, ds=1)
            plot.setClipToView(False)
        ydata = amp[:, ch] if amp.ndim > 1 else amp
        plot.plot(time_axis, ydata, pen=pg.mkPen((30, 90, 200), width=1))
        plots.append(plot)
    return widget, plots


def _render(
    app: QtWidgets.QApplication, signal: AudioSignal, downsample: bool
) -> float:
    start = time.perf_counter()
    widget, _ = _build(signal, downsample)
    widget.grab()  # force a synchronous paint of the curves
    app.processEvents()
    elapsed = time.perf_counter() - start
    widget.deleteLater()
    return elapsed


def _pan(app: QtWidgets.QApplication, signal: AudioSignal, downsample: bool) -> float:
    """Time repeated repaints while panning a 1 s window across the signal."""
    widget, plots = _build(signal, downsample)
    widget.grab()
    window = 1.0  # seconds visible
    steps = 20
    step = max((signal.duration_s - window) / steps, 0.0)
    start = time.perf_counter()
    for i in range(steps):
        x0 = i * step
        for plot in plots:
            plot.setXRange(x0, x0 + window, padding=0)
        widget.grab()
        app.processEvents()
    elapsed = (time.perf_counter() - start) / steps
    widget.deleteLater()
    return elapsed


def _report(app, label: str, signal: AudioSignal) -> None:
    total_samples = signal.n_frames * signal.n_channels
    mem_mb = (signal.samples.nbytes + len(signal.raw_data)) / 1e6
    print(f"\n{label}")
    print(
        f"  {signal.n_frames:,} frames x {signal.n_channels} ch "
        f"= {total_samples:,} samples, {signal.duration_s:.1f} s, "
        f"~{mem_mb:.0f} MB in memory (numpy + raw bytes)"
    )
    down = _render(app, signal, downsample=True)
    naive = _render(app, signal, downsample=False)
    print("  initial full render:")
    print(f"    peak downsampling + clip-to-view : {down * 1000:8.1f} ms")
    print(f"    naive (every sample)             : {naive * 1000:8.1f} ms")
    if down > 0:
        print(f"    speed-up                         : {naive / down:8.1f}x")

    pan_down = _pan(app, signal, downsample=True)
    pan_naive = _pan(app, signal, downsample=False)
    print("  per-frame repaint while panning a 1 s window:")
    print(f"    peak downsampling + clip-to-view : {pan_down * 1000:8.1f} ms/frame")
    print(f"    naive (every sample)             : {pan_naive * 1000:8.1f} ms/frame")
    if pan_down > 0:
        print(f"    speed-up                         : {pan_naive / pan_down:8.1f}x")


def main() -> None:
    app = QtWidgets.QApplication([])

    music = sorted(DATA_DIR.glob("Music#2*.wav"))
    if music:
        t0 = time.perf_counter()
        signal = read_signal(music[0])
        print(f"read {music[0].name} in {(time.perf_counter() - t0) * 1000:.0f} ms")
        _report(app, "Largest bundled file (Music#2, stereo 96 kHz)", signal)

    _report(app, "Synthetic 10-minute mono 48 kHz", _synth(10.0))


if __name__ == "__main__":
    main()
