from __future__ import annotations

import tempfile
from pathlib import Path

from PyQt6 import QtCore, QtMultimedia

from audio.audio_signal import AudioSignal
from audio.wav_io import write_signal

_STOPPED = QtMultimedia.QMediaPlayer.PlaybackState.StoppedState


class Player(QtCore.QObject):
    """Plays WAV files through Qt Multimedia, which also downmixes channels and
    resamples for the output device. A processed signal is first written to a
    temporary WAV, so what is heard is exactly what Save writes."""

    positionChanged = QtCore.pyqtSignal(float)  # seconds
    stopped = QtCore.pyqtSignal()
    errorOccurred = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.label: str | None = None  # what is playing, None when stopped
        self._output = QtMultimedia.QAudioOutput(self)
        self._player = QtMultimedia.QMediaPlayer(self)
        self._player.setAudioOutput(self._output)
        self._tmp = tempfile.TemporaryDirectory(prefix="lab3-")
        self._renders = 0
        self._last_render: Path | None = None

        self._player.positionChanged.connect(self._on_position)
        self._player.playbackStateChanged.connect(self._on_state)
        self._player.errorOccurred.connect(self._on_error)

    def play(self, path: str | Path, label: str) -> None:
        self._player.stop()
        self._player.setSource(QtCore.QUrl.fromLocalFile(str(Path(path).resolve())))
        self._player.play()
        self.label = label

    def render(self, signal: AudioSignal) -> Path:
        """Write ``signal`` to a new temporary WAV and delete the previous one.
        Every render gets a fresh name, so the player never reuses a cached
        file."""
        self.stop()
        self._player.setSource(QtCore.QUrl())
        if self._last_render is not None:
            self._last_render.unlink(missing_ok=True)
        self._renders += 1
        path = Path(self._tmp.name) / f"processed_{self._renders}.wav"
        write_signal(path, signal)
        self._last_render = path
        return path

    def stop(self) -> None:
        self._player.stop()

    def close(self) -> None:
        self.stop()
        self._player.setSource(QtCore.QUrl())
        self._tmp.cleanup()

    def _on_position(self, ms: int) -> None:
        if self.label is not None:
            self.positionChanged.emit(ms / 1000)

    def _on_state(self, state) -> None:
        # A stop that is reported late, after the next play() began, is ignored.
        if state == _STOPPED and self._player.playbackState() == _STOPPED:
            self.label = None
            self.stopped.emit()

    def _on_error(self, _error, message: str) -> None:
        self.errorOccurred.emit(message)
