from __future__ import annotations

from pathlib import Path

import numpy as np
from PyQt6 import QtWidgets

from analysis.spectrum import (
    DEFAULT_LENGTH_MS,
    MIN_LENGTH_MS,
    Spectrum,
    Window,
    loudest_start,
    spectrum,
    window,
)
from audio.audio_signal import AudioSignal
from audio.wav_io import read_signal
from ui.spectrum_view import SpectrumView
from utils.timescale import format_duration

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
_WAV_FILTER = "WAV files (*.wav);;All files (*)"


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spectrum Analysis - Lab 4")
        self.resize(1280, 900)
        self._signal: AudioSignal | None = None
        self._samples: np.ndarray | None = None
        self._spectrum: Spectrum | None = None
        self._span = (0, 0)  # selected segment, in samples

        self._view = SpectrumView()
        self._info = QtWidgets.QLabel("Open a .wav file to begin.")
        self._info.setWordWrap(True)
        self._info.setContentsMargins(8, 6, 8, 6)

        self._build_toolbar()
        controls = self._build_controls()

        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._info)
        layout.addWidget(self._view, stretch=1)
        layout.addWidget(controls)
        self.setCentralWidget(central)
        self.statusBar().showMessage("Ready")

        self._view.segmentChanged.connect(self._on_region_moved)
        self._view.spectrumHovered.connect(self._show_frequency)

    def _build_toolbar(self) -> None:
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        toolbar.addAction("Open .wav...").triggered.connect(self.open_file)

    def _build_controls(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(panel)
        row.setContentsMargins(8, 4, 8, 8)

        self._window = QtWidgets.QComboBox()
        for kind in Window:
            self._window.addItem(kind.label, kind)
        self._window.setCurrentIndex(list(Window).index(Window.HANNING))
        self._window.currentIndexChanged.connect(self._update)

        self._start = QtWidgets.QDoubleSpinBox()
        self._start.setDecimals(4)
        self._start.setSuffix(" s")
        self._start.setSingleStep(0.001)
        self._length = QtWidgets.QDoubleSpinBox()
        self._length.setDecimals(1)
        self._length.setSuffix(" ms")
        self._length.setSingleStep(1.0)
        self._length.setMinimum(MIN_LENGTH_MS)
        for box in (self._start, self._length):
            box.setEnabled(False)
            box.setKeyboardTracking(False)
            box.valueChanged.connect(self._on_boxes_edited)
        self._segment_info = QtWidgets.QLabel()

        row.addWidget(QtWidgets.QLabel("Window:"))
        row.addWidget(self._window)
        row.addSpacing(16)
        row.addWidget(QtWidgets.QLabel("Segment start:"))
        row.addWidget(self._start)
        row.addSpacing(12)
        row.addWidget(QtWidgets.QLabel("Length:"))
        row.addWidget(self._length)
        row.addSpacing(12)
        row.addWidget(self._segment_info, stretch=1)
        return panel

    def open_file(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open WAV file", str(DATA_DIR / "Garsai1"), _WAV_FILTER
        )
        if not path:
            return
        try:
            self.load(path)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Cannot read file", str(exc))

    def load(self, path: str | Path) -> None:
        signal = read_signal(path)
        self._signal = signal
        self._samples = signal.channel_samples()
        self._view.show_signal(signal, self._samples, self._channel_label())
        self._update_info()

        n = signal.sample_at_time(DEFAULT_LENGTH_MS / 1000)
        start = loudest_start(self._samples, n)
        self._select(start, start + n)
        self.statusBar().showMessage(
            f"Loaded {signal.path.name} - the segment starts on the loudest part; "
            "drag it, or type its start and length",
            8000,
        )

    def _channel_label(self) -> str:
        signal = self._signal
        if signal.n_channels > 1:
            return f"Mix of {signal.n_channels} channels"
        return signal.channel_names[0]

    def _update_info(self) -> None:
        signal = self._signal
        self._info.setText(
            f"<b>{signal.path.name}</b> &nbsp;|&nbsp; "
            f"Channels: {signal.n_channels} &nbsp;|&nbsp; "
            f"Sample rate: {signal.sample_rate:,} Hz &nbsp;|&nbsp; "
            f"Bit depth: {signal.valid_bits}-bit &nbsp;|&nbsp; "
            f"Format: {signal.format_name} &nbsp;|&nbsp; "
            f"Duration: {format_duration(signal.duration_s)} &nbsp;|&nbsp; "
            f"Analysed: {self._channel_label()}"
        )

    def _select(self, s0: int, s1: int) -> None:
        """Select samples [s0, s1) and update the boxes, the region and the plots."""
        fs = self._signal.sample_rate
        self._span = (s0, s1)
        self._set_boxes(s0 / fs, 1000 * (s1 - s0) / fs)
        self._view.set_segment(s0 / fs, s1 / fs)
        self._update()

    def _set_boxes(self, start: float, length_ms: float) -> None:
        duration = self._signal.duration_s
        for box in (self._start, self._length):
            box.blockSignals(True)
            box.setEnabled(True)
        self._start.setMaximum(duration)
        self._length.setMaximum(1000 * duration)
        self._start.setValue(start)
        self._length.setValue(length_ms)
        for box in (self._start, self._length):
            box.blockSignals(False)

    def _on_boxes_edited(self) -> None:
        signal = self._signal
        if signal is None:
            return
        n = signal.sample_at_time(self._length.value() / 1000)
        if self._length.value() >= self._length.maximum():
            n = signal.n_samples  # the box rounds to 0.1 ms; its maximum is the file
        # Keep the whole length inside the file: move the start back if needed.
        s0 = min(signal.sample_at_time(self._start.value()), signal.n_samples - n)
        self._select(s0, s0 + n)

    def _on_region_moved(self, start: float, end: float) -> None:
        signal = self._signal
        n = signal.sample_at_time(end - start)  # the same N while the region moves
        s0 = signal.sample_at_time(start)
        self._span = (s0, min(s0 + n, signal.n_samples))
        s0, s1 = self._span
        self._set_boxes(s0 / signal.sample_rate, 1000 * (s1 - s0) / signal.sample_rate)
        self._update()

    def _update(self) -> None:
        signal = self._signal
        if signal is None:
            return
        s0, s1 = self._span
        segment = self._samples[s0:s1]
        if segment.size < 2:
            self._spectrum = None
            self._view.clear_segment("The segment is too short.")
            self._segment_info.setText("The segment is too short.")
            return
        kind = self._window.currentData()
        fs = signal.sample_rate
        self._spectrum = spectrum(segment, fs, kind)
        windowed = segment * window(kind, segment.size)
        self._view.show_segment(s0 / fs, fs, segment, windowed)
        self._view.show_spectrum(self._spectrum)
        self._segment_info.setText(
            f"N = {segment.size:,} samples  ·  "
            f"Δf = fs/N = {self._spectrum.resolution_hz:.2f} Hz"
        )

    def _show_frequency(self, k: int) -> None:
        spec = self._spectrum
        if spec is None:
            return
        self.statusBar().showMessage(
            f"f = {spec.frequencies[k]:.1f} Hz:  "
            f"|X| = {spec.relative_amplitude[k]:.3f},  "
            f"S = {spec.relative_density[k]:.3f}  (relative to the maximum)"
        )
