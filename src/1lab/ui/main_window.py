from __future__ import annotations

from pathlib import Path

from PyQt6 import QtWidgets

from audio.audio_signal import AudioSignal
from audio.wav_io import read_signal, write_segment
from ui.plotting import WaveformView
from utils.timescale import format_duration


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Signal Viewer - Lab 1")
        self.resize(1100, 720)
        self._signal: AudioSignal | None = None

        self._view = WaveformView()
        self._info = QtWidgets.QLabel("Open a .wav file to begin.")
        self._info.setWordWrap(True)
        self._info.setContentsMargins(8, 6, 8, 6)

        self._build_toolbar()
        segment_panel = self._build_segment_panel()

        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._info)
        layout.addWidget(self._view, stretch=1)
        layout.addWidget(segment_panel)
        self.setCentralWidget(central)
        self.statusBar().showMessage("Ready")

    # -- construction -------------------------------------------------------

    def _build_toolbar(self) -> None:
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        open_action = toolbar.addAction("Open .wav...")
        open_action.triggered.connect(self.open_file)

    def _build_segment_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(panel)
        row.setContentsMargins(8, 4, 8, 8)

        self._start = QtWidgets.QDoubleSpinBox()
        self._start.setDecimals(3)
        self._start.setSuffix(" s")
        self._start.setMinimum(0.0)
        self._start.setEnabled(False)

        self._duration = QtWidgets.QDoubleSpinBox()
        self._duration.setDecimals(3)
        self._duration.setSuffix(" s")
        self._duration.setMinimum(0.0)
        self._duration.setEnabled(False)

        self._save_btn = QtWidgets.QPushButton("Save segment...")
        self._save_btn.setEnabled(False)

        self._save_btn.clicked.connect(self._save_segment)
        self._start.valueChanged.connect(self._highlight)
        self._duration.valueChanged.connect(self._highlight)

        row.addWidget(QtWidgets.QLabel("Segment start:"))
        row.addWidget(self._start)
        row.addSpacing(12)
        row.addWidget(QtWidgets.QLabel("Duration:"))
        row.addWidget(self._duration)
        row.addStretch(1)
        row.addWidget(self._save_btn)
        return panel

    def open_file(self) -> None:
        start_dir = Path.cwd() / "data" / "Garsai1"
        if not start_dir.exists():
            start_dir = Path.cwd()
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open WAV file",
            str(start_dir),
            "WAV files (*.wav);;All files (*)",
        )
        if not path:
            return
        try:
            signal = read_signal(path)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Cannot read file", str(exc))
            return

        self._signal = signal
        self._view.set_signal(signal)
        self._update_info(signal)
        self._configure_segment_controls(signal)
        self.statusBar().showMessage(f"Loaded {signal.path.name}", 5000)

    def _update_info(self, signal: AudioSignal) -> None:
        self._info.setText(
            f"<b>{signal.path.name}</b> &nbsp;|&nbsp; "
            f"Channels: {signal.n_channels} &nbsp;|&nbsp; "
            f"Sample rate: {signal.sample_rate:,} Hz &nbsp;|&nbsp; "
            f"Bit depth: {signal.valid_bits}-bit &nbsp;|&nbsp; "
            f"Format: {signal.format_name} &nbsp;|&nbsp; "
            f"Duration: {format_duration(signal.duration_s)}"
        )

    def _configure_segment_controls(self, signal: AudioSignal) -> None:
        duration = signal.duration_s
        for box in (self._start, self._duration):
            box.setEnabled(True)
            box.setMaximum(duration)
        self._start.blockSignals(True)
        self._duration.blockSignals(True)
        self._start.setValue(0.0)
        self._duration.setValue(min(1.0, duration))
        self._start.blockSignals(False)
        self._duration.blockSignals(False)
        self._save_btn.setEnabled(True)
        self._highlight()

    def _current_range(self) -> tuple[float, float]:
        start = self._start.value()
        end = min(start + self._duration.value(), self._signal.duration_s)
        return start, end

    def _highlight(self) -> None:
        if self._signal is None:
            return
        start, end = self._current_range()
        if end <= start:
            self.statusBar().showMessage("Duration must be greater than 0", 4000)
            self._view.clear_regions()
            return
        self._view.highlight_segment(start, end)
        self.statusBar().showMessage(
            f"Segment: {start:.3f} s -> {end:.3f} s ({end - start:.3f} s)", 4000
        )

    def _save_segment(self) -> None:
        if self._signal is None:
            return
        signal = self._signal
        start, end = self._current_range()
        start_frame = signal.frame_at_time(start)
        end_frame = signal.frame_at_time(end)
        if end_frame <= start_frame:
            QtWidgets.QMessageBox.warning(
                self, "Invalid segment", "The selected segment is empty."
            )
            return
        default = str(signal.path.with_name(f"{signal.path.stem}_segment.wav"))
        dst, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save segment", default, "WAV files (*.wav)"
        )
        if not dst:
            return
        try:
            frames = write_segment(dst, signal, start_frame, end_frame)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Cannot save segment", str(exc))
            return
        self.statusBar().showMessage(
            f"Saved {frames} frames ({frames / signal.sample_rate:.3f} s) "
            f"to {Path(dst).name}",
            6000,
        )
