from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PyQt6 import QtWidgets

from audio.audio_signal import AudioSignal
from audio.wav_io import read_signal, write_signal
from effects.modulation import (
    DEFAULT_RATE_HZ,
    RATE_RANGE_HZ,
    Waveform,
    expected_level_db,
    level_change_db,
    modulate,
    modulator,
)
from ui.effect_view import EffectView
from ui.player import Player
from utils.timescale import format_duration

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
_WAV_FILTER = "WAV files (*.wav);;All files (*)"


def _db(value: float) -> str:
    return "–" if math.isnan(value) else f"{value:+.2f} dB"


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modulation Effect - Lab 3")
        self.resize(1280, 860)
        self._signal: AudioSignal | None = None
        self._m: np.ndarray | None = None
        self._processed: AudioSignal | None = None
        self._render: Path | None = None  # temporary WAV of the processed signal

        self._view = EffectView()
        self._player = Player(self)
        self._info = QtWidgets.QLabel("Open a .wav file to begin.")
        self._info.setWordWrap(True)
        self._info.setContentsMargins(8, 6, 8, 6)

        self._build_toolbar()
        settings_panel = self._build_settings_panel()

        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._info)
        layout.addWidget(self._view, stretch=1)
        layout.addWidget(settings_panel)
        self.setCentralWidget(central)
        self.statusBar().showMessage("Ready")

        self._player.positionChanged.connect(self._on_position)
        self._player.stopped.connect(self._on_stopped)
        self._player.errorOccurred.connect(self._on_player_error)

    def _build_toolbar(self) -> None:
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        toolbar.addAction("Open .wav...").triggered.connect(self.open_file)
        toolbar.addSeparator()
        play_original = toolbar.addAction("Play original")
        play_processed = toolbar.addAction("Play processed")
        stop = toolbar.addAction("Stop")
        toolbar.addSeparator()
        save = toolbar.addAction("Save processed...")
        play_original.triggered.connect(self.play_original)
        play_processed.triggered.connect(self.play_processed)
        stop.triggered.connect(self._player.stop)
        save.triggered.connect(self.save_processed)
        # Enabled once a file is loaded.
        self._file_actions = (play_original, play_processed, stop, save)
        for action in self._file_actions:
            action.setEnabled(False)

    def _build_settings_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(panel)
        row.setContentsMargins(8, 4, 8, 8)

        self._waveform = QtWidgets.QComboBox()
        for waveform in Waveform:
            self._waveform.addItem(waveform.label, waveform)

        self._rate = QtWidgets.QDoubleSpinBox()
        self._rate.setRange(*RATE_RANGE_HZ)
        self._rate.setDecimals(2)
        self._rate.setStepType(
            QtWidgets.QAbstractSpinBox.StepType.AdaptiveDecimalStepType
        )
        self._rate.setValue(DEFAULT_RATE_HZ)
        self._rate.setSuffix(" Hz")
        self._period = QtWidgets.QLabel()

        self._rate.setKeyboardTracking(False)
        self._rate.valueChanged.connect(self._update_period)
        self._rate.valueChanged.connect(self._reprocess)
        self._waveform.currentIndexChanged.connect(self._reprocess)
        self._update_period()

        row.addWidget(QtWidgets.QLabel("Modulating signal:"))
        row.addWidget(self._waveform)
        row.addSpacing(12)
        row.addWidget(QtWidgets.QLabel("Rate:"))
        row.addWidget(self._rate)
        row.addWidget(self._period)
        row.addStretch(1)
        return panel

    def _update_period(self) -> None:
        self._period.setText(f"(period {format_duration(1 / self._rate.value())})")

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
        self._player.stop()
        self._signal = signal
        for action in self._file_actions:
            action.setEnabled(True)
        self._reprocess()
        self.statusBar().showMessage(
            f"Loaded {signal.path.name} - choose the modulating signal, "
            "then Play processed to hear the effect",
            8000,
        )

    def _channel_label(self) -> str:
        signal = self._signal
        if signal.n_channels > 1:
            return f"Mix of {signal.n_channels} channels"
        return signal.channel_names[0]

    def _effect_label(self) -> str:
        return f"{self._waveform.currentData().label}, {self._rate.value():.2f} Hz"

    def _reprocess(self) -> None:
        signal = self._signal
        if signal is None:
            return
        if self._player.label == "processed":
            self._player.stop()
        self._m = modulator(
            signal.n_samples,
            signal.sample_rate,
            self._waveform.currentData(),
            self._rate.value(),
        )
        self._processed = modulate(signal, self._m)
        self._render = None
        self._redraw()

    def _redraw(self) -> None:
        signal = self._signal
        if signal is None or self._processed is None:
            return
        original = signal.channel_samples()
        processed = self._processed.channel_samples()
        self._view.show_signal(signal, original, self._channel_label())
        self._view.show_effect(self._m, processed, self._effect_label())
        self._update_info(original, processed)

    def _update_info(self, original: np.ndarray, processed: np.ndarray) -> None:
        signal = self._signal
        waveform = self._waveform.currentData()
        expected = expected_level_db(waveform)
        self._info.setText(
            f"<b>{signal.path.name}</b> &nbsp;|&nbsp; "
            f"Channels: {signal.n_channels} &nbsp;|&nbsp; "
            f"Sample rate: {signal.sample_rate:,} Hz &nbsp;|&nbsp; "
            f"Bit depth: {signal.valid_bits}-bit &nbsp;|&nbsp; "
            f"Format: {signal.format_name} &nbsp;|&nbsp; "
            f"Duration: {format_duration(signal.duration_s)}<br>"
            f"<b>m(t)</b>: {self._effect_label()} "
            f"{self._period.text()} &nbsp;|&nbsp; "
            f"<b>RMS level change {_db(level_change_db(original, processed))}</b>"
            f" ({self._channel_label()}; {_db(expected)} expected for a signal "
            "independent of m)"
        )

    def play_original(self) -> None:
        if self._signal is not None:
            self._player.play(self._signal.path, "original")

    def play_processed(self) -> None:
        if self._processed is None:
            return
        if self._render is None:
            try:
                self._render = self._player.render(self._processed)
            except Exception as exc:
                QtWidgets.QMessageBox.critical(self, "Cannot play", str(exc))
                return
        self._player.play(self._render, "processed")

    def _on_position(self, seconds: float) -> None:
        self._view.set_cursor(seconds)
        self.statusBar().showMessage(
            f"Playing {self._player.label}: {seconds:.2f} / "
            f"{self._signal.duration_s:.2f} s"
        )

    def _on_stopped(self) -> None:
        self._view.set_cursor(None)
        self.statusBar().showMessage("Stopped", 3000)

    def _on_player_error(self, message: str) -> None:
        self.statusBar().showMessage(f"Playback error: {message}", 8000)

    def save_processed(self) -> None:
        processed = self._processed
        if processed is None:
            return
        name = (
            f"{processed.path.stem}_{self._waveform.currentData().name.lower()}"
            f"_{self._rate.value():g}Hz.wav"
        )
        dst, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save processed signal",
            str(processed.path.with_name(name)),
            "WAV files (*.wav)",
        )
        if not dst:
            return
        dst = Path(dst)
        if dst.suffix.lower() != ".wav":
            dst = dst.with_name(dst.name + ".wav")
        try:
            samples = write_signal(dst, processed)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Cannot save file", str(exc))
            return
        self.statusBar().showMessage(
            f"Saved {samples:,} samples "
            f"({format_duration(samples / processed.sample_rate)}) to {dst.name}",
            6000,
        )

    def closeEvent(self, event) -> None:
        self._player.close()
        super().closeEvent(event)
