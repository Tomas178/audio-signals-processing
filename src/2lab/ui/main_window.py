from __future__ import annotations

from pathlib import Path

import numpy as np
from PyQt6 import QtCore, QtWidgets

from analysis.entropy import (
    BINS_RANGE,
    DEFAULT_BINS,
    DEFAULT_FRAME_MS,
    FRAME_MS_RANGE,
    BinRange,
    EntropyAnalysis,
    analyze,
)
from analysis.summary import summarize_file
from audio.audio_signal import AudioSignal
from audio.wav_io import read_signal
from ui.compare_dialog import CompareDialog
from ui.entropy_view import EntropyView
from utils.timescale import format_duration

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
_WAV_FILTER = "WAV files (*.wav);;All files (*)"


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Entropy Analysis - Lab 2")
        self.resize(1280, 860)
        self._signal: AudioSignal | None = None
        self._samples: np.ndarray | None = None
        self._analysis: EntropyAnalysis | None = None
        self._span = (0, 0)  # selected segment, in samples
        self._compare: CompareDialog | None = None

        self._view = EntropyView()
        self._info = QtWidgets.QLabel("Open a .wav file to begin.")
        self._info.setWordWrap(True)
        self._info.setContentsMargins(8, 6, 8, 6)

        self._build_toolbar()
        settings_panel = self._build_settings_panel()
        segment_panel = self._build_segment_panel()

        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._info)
        layout.addWidget(self._view, stretch=1)
        layout.addWidget(settings_panel)
        layout.addWidget(segment_panel)
        self.setCentralWidget(central)
        self.statusBar().showMessage("Ready")

        self._view.segmentChanged.connect(self._on_region_moved)
        self._view.frameClicked.connect(self.select_frame)
        self._view.frameHovered.connect(self._show_frame)

    def _build_toolbar(self) -> None:
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        toolbar.addAction("Open .wav...").triggered.connect(self.open_file)
        toolbar.addSeparator()
        toolbar.addAction("Compare files...").triggered.connect(self.compare_files)
        toolbar.addAction("Compare folder...").triggered.connect(self.compare_folder)

    def _build_settings_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(panel)
        row.setContentsMargins(8, 4, 8, 0)

        self._channel = QtWidgets.QComboBox()
        self._channel.setEnabled(False)
        self._channel.setSizeAdjustPolicy(
            QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents
        )

        self._frame_ms = QtWidgets.QSpinBox()
        self._frame_ms.setRange(*FRAME_MS_RANGE)
        self._frame_ms.setValue(DEFAULT_FRAME_MS)
        self._frame_ms.setSuffix(" ms")
        self._frame_info = QtWidgets.QLabel()

        self._bins = QtWidgets.QSpinBox()
        self._bins.setRange(*BINS_RANGE)
        self._bins.setValue(DEFAULT_BINS)

        self._bin_range = QtWidgets.QComboBox()
        for mode in BinRange:
            self._bin_range.addItem(mode.label, mode)

        for box in (self._frame_ms, self._bins):
            box.setKeyboardTracking(False)
            box.valueChanged.connect(self._reanalyze)
        self._channel.currentIndexChanged.connect(self._reanalyze)
        self._bin_range.currentIndexChanged.connect(self._reanalyze)

        row.addWidget(QtWidgets.QLabel("Channel:"))
        row.addWidget(self._channel)
        row.addSpacing(12)
        row.addWidget(QtWidgets.QLabel("Frame length:"))
        row.addWidget(self._frame_ms)
        row.addWidget(self._frame_info)
        row.addSpacing(12)
        row.addWidget(QtWidgets.QLabel("Bins L:"))
        row.addWidget(self._bins)
        row.addSpacing(12)
        row.addWidget(QtWidgets.QLabel("Bin range:"))
        row.addWidget(self._bin_range)
        row.addStretch(1)
        return panel

    def _build_segment_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(panel)
        row.setContentsMargins(8, 4, 8, 8)

        self._start = QtWidgets.QDoubleSpinBox()
        self._duration = QtWidgets.QDoubleSpinBox()
        for box in (self._start, self._duration):
            box.setDecimals(3)
            box.setSuffix(" s")
            box.setMinimum(0.0)
            box.setSingleStep(0.1)
            box.setEnabled(False)
            box.setKeyboardTracking(False)
            box.valueChanged.connect(self._on_boxes_edited)
        self._segment_info = QtWidgets.QLabel()

        row.addWidget(QtWidgets.QLabel("Segment start:"))
        row.addWidget(self._start)
        row.addSpacing(12)
        row.addWidget(QtWidgets.QLabel("Duration:"))
        row.addWidget(self._duration)
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
        self._fill_channels(signal)
        self._set_boxes(0.0, min(1.0, signal.duration_s))
        self._span = (0, signal.sample_at_time(1.0))
        self._reanalyze()
        self.statusBar().showMessage(
            f"Loaded {signal.path.name} - drag the orange segment, "
            "or click a frame on the entropy plot to inspect it",
            8000,
        )

    def _fill_channels(self, signal: AudioSignal) -> None:
        self._channel.blockSignals(True)
        self._channel.clear()
        if signal.n_channels > 1:
            self._channel.addItem(f"Mix (mean of {signal.n_channels} channels)", None)
            for index, name in enumerate(signal.channel_names):
                self._channel.addItem(f"{index + 1}: {name}", index)
        else:
            self._channel.addItem(signal.channel_names[0], None)
        self._channel.setEnabled(signal.n_channels > 1)
        self._channel.blockSignals(False)

    def _reanalyze(self) -> None:
        signal = self._signal
        if signal is None:
            return
        self._samples = signal.channel_samples(self._channel.currentData())
        self._analysis = analyze(
            self._samples,
            signal.sample_rate,
            self._frame_ms.value(),
            self._bins.value(),
            self._bin_range.currentData(),
        )
        self._view.show_analysis(
            signal, self._samples, self._channel_label(), self._analysis
        )
        self._update_info()
        start, end = (s / signal.sample_rate for s in self._span)
        self._view.set_segment(start, end)
        self._update_segment()

    def _channel_label(self) -> str:
        channel = self._channel.currentData()
        if channel is not None:
            return self._signal.channel_names[channel]
        return "Mix" if self._signal.n_channels > 1 else self._signal.channel_names[0]

    def _update_info(self) -> None:
        signal, a = self._signal, self._analysis
        framing = a.framing
        self._frame_info.setText(
            f"= {framing.length} samples, hop {framing.hop} (50 % overlap)"
        )
        if a.n_frames:
            local = (
                f"Local H over {a.n_frames} frames: mean {a.local_mean:.3f} "
                f"&plusmn; {a.local_std:.3f}, min {a.local_min:.3f}, "
                f"max {a.local_max:.3f} bits"
            )
        else:
            local = "The signal is shorter than one frame"
        self._info.setText(
            f"<b>{signal.path.name}</b> &nbsp;|&nbsp; "
            f"Channels: {signal.n_channels} &nbsp;|&nbsp; "
            f"Sample rate: {signal.sample_rate:,} Hz &nbsp;|&nbsp; "
            f"Bit depth: {signal.valid_bits}-bit &nbsp;|&nbsp; "
            f"Format: {signal.format_name} &nbsp;|&nbsp; "
            f"Duration: {format_duration(signal.duration_s)}<br>"
            f"<b>Entropy H = {a.entropy:.3f} bits</b> "
            f"({a.entropy / a.h_max:.2f}&middot;H<sub>max</sub>, "
            f"H<sub>max</sub> = log<sub>2</sub>{a.bins} = {a.h_max:.2f} bits)"
            f" &nbsp;|&nbsp; {local}"
        )

    def _set_boxes(self, start: float, duration: float) -> None:
        for box in (self._start, self._duration):
            box.blockSignals(True)
            box.setEnabled(True)
            box.setMaximum(self._signal.duration_s)
        self._start.setValue(start)
        self._duration.setValue(duration)
        for box in (self._start, self._duration):
            box.blockSignals(False)

    def _on_boxes_edited(self) -> None:
        signal = self._signal
        if signal is None:
            return
        start = self._start.value()
        end = min(start + self._duration.value(), signal.duration_s)
        self._span = (signal.sample_at_time(start), signal.sample_at_time(end))
        self._view.set_segment(start, max(start, end))
        self._update_segment()

    def _on_region_moved(self, start: float, end: float) -> None:
        signal = self._signal
        self._set_boxes(start, end - start)
        self._span = (signal.sample_at_time(start), signal.sample_at_time(end))
        self._update_segment()

    def select_frame(self, k: int) -> None:
        signal, framing = self._signal, self._analysis.framing
        self._span = framing.span(k)
        start, end = (s / signal.sample_rate for s in self._span)
        self._set_boxes(start, end - start)
        self._view.set_segment(start, end)
        self._update_segment()
        self.statusBar().showMessage(
            f"Frame {k} selected: H = {self._analysis.frame_h[k]:.3f} bits", 6000
        )

    def _update_segment(self) -> None:
        s0, s1 = self._span
        if s1 <= s0:
            self._view.show_segment(None)
            self._segment_info.setText("The segment is empty.")
            return
        hist = self._analysis.segment_histogram(self._samples[s0:s1])
        self._view.show_segment(hist)
        fs = self._signal.sample_rate
        self._segment_info.setText(
            f"Segment {s0 / fs:.3f}–{s1 / fs:.3f} s ({s1 - s0:,} samples): "
            f"<b>H = {hist.entropy:.3f} bits</b> "
            f"({hist.entropy / self._analysis.h_max:.2f}&middot;H<sub>max</sub>)"
        )

    def _show_frame(self, k: int) -> None:
        a = self._analysis
        s0, s1 = a.framing.span(k)
        fs = a.framing.sample_rate
        self.statusBar().showMessage(
            f"Frame {k}: {s0 / fs:.3f}–{s1 / fs:.3f} s, H = {a.frame_h[k]:.3f} bits"
            " - click to inspect its histogram"
        )

    def compare_files(self) -> None:
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Compare WAV files", str(DATA_DIR / "Garsai1"), _WAV_FILTER
        )
        if paths:
            self.compare(paths)

    def compare_folder(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Compare every WAV file in a folder", str(DATA_DIR)
        )
        if not folder:
            return
        paths = sorted(Path(folder).rglob("*.wav"))
        if not paths:
            QtWidgets.QMessageBox.information(
                self, "No WAV files", f"There are no .wav files under {folder}."
            )
            return
        self.compare(paths)

    def compare(self, paths: list[str] | list[Path]) -> None:
        settings = (
            self._frame_ms.value(),
            self._bins.value(),
            self._bin_range.currentData(),
        )
        summaries, failures = [], []
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            for path in paths:
                try:
                    summaries.append(summarize_file(path, *settings))
                except Exception as exc:
                    failures.append(f"{Path(path).name}: {exc}")
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        if failures:
            QtWidgets.QMessageBox.warning(
                self, "Some files were skipped", "\n".join(failures)
            )
        if not summaries:
            return
        if self._compare is not None:
            self._compare.close()
        self._compare = CompareDialog(summaries, *settings, parent=self)
        self._compare.show()
