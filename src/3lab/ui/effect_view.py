from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore

from audio.audio_signal import AudioSignal
from utils.timescale import choose_time_unit

_WAVE_PEN = pg.mkPen((30, 90, 200), width=1)
_MOD_PEN = pg.mkPen((20, 130, 90), width=1.5)
_ENVELOPE_PEN = pg.mkPen((200, 40, 40), width=1, style=QtCore.Qt.PenStyle.DashLine)
_CURSOR_PEN = pg.mkPen((230, 120, 0), width=1.5)


class EffectView(pg.GraphicsLayoutWidget):
    """Original signal, modulating signal m(t) and processed signal
    m(t) * s(t) on three X-linked plots, with a playback cursor across all."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackground("w")
        self._signal: AudioSignal | None = None
        self._unit_scale = 1.0  # multiply seconds by this to get axis units
        self._time = np.zeros(0)  # axis position of every sample
        self._peak = 1.0  # of the shown original, for the envelope

        self._title = self.addLabel("Open a .wav file to begin.", row=0, col=0)
        self._original = self.addPlot(row=1, col=0)
        self._modulator = self.addPlot(row=2, col=0)
        self._processed = self.addPlot(row=3, col=0)
        for row, stretch in ((1, 3), (2, 2), (3, 3)):
            self.ci.layout.setRowStretchFactor(row, stretch)

        self._cursors: list[pg.InfiniteLine] = []
        for plot in (self._original, self._modulator, self._processed):
            plot.showGrid(x=True, y=True, alpha=0.25)
            plot.setMouseEnabled(x=True, y=False)
            plot.setDownsampling(auto=True, mode="peak")
            plot.setClipToView(True)
            if plot is not self._original:
                plot.setXLink(self._original)
            cursor = pg.InfiniteLine(angle=90, pen=_CURSOR_PEN)
            cursor.setZValue(10)
            cursor.hide()
            plot.addItem(cursor)
            self._cursors.append(cursor)
        for plot in (self._original, self._processed):
            plot.getAxis("left").enableAutoSIPrefix(False)  # integer PCM levels

        self._modulator.setYRange(0.0, 1.0, padding=0.05)
        self._modulator.setLabel("left", "m(t)")
        self._modulator.setTitle("Modulating signal m(t)", size="9pt")
        self._processed.setTitle("Processed signal m(t) · s(t)", size="9pt")

        self._original_curve = self._original.plot(pen=_WAVE_PEN)
        self._modulator_curve = self._modulator.plot(pen=_MOD_PEN)
        self._processed_curve = self._processed.plot(pen=_WAVE_PEN)
        self._envelope = (
            self._processed.plot(pen=_ENVELOPE_PEN),
            self._processed.plot(pen=_ENVELOPE_PEN),
        )

    def show_signal(
        self, signal: AudioSignal, samples: np.ndarray, channel: str
    ) -> None:
        if signal is not self._signal:
            self._original.enableAutoRange(x=True)
        self._signal = signal
        unit = choose_time_unit(signal.duration_s)
        self._unit_scale = 1.0 / unit.seconds
        self._time = np.arange(samples.size) * (self._unit_scale / signal.sample_rate)

        self._original_curve.setData(self._time, samples)
        peak = float(np.max(np.abs(samples))) if samples.size else 0.0
        self._peak = peak if peak > 0 else signal.amplitude_range[1]
        # Both signals share the original's scale, so the level drop is visible.
        for plot in (self._original, self._processed):
            plot.setYRange(-self._peak, self._peak, padding=0.05)
            plot.setLabel("left", channel)
        self._original.setTitle(
            f"Original signal s(t) &middot; {signal.amplitude_label}", size="9pt"
        )
        self._processed.setLabel("bottom", f"Time ({unit.label})")
        self._title.setText(f"<b>{signal.path.name}</b> &middot; {channel}")

    def show_effect(
        self, m: np.ndarray, processed: np.ndarray, description: str
    ) -> None:
        self._modulator_curve.setData(self._time, m)
        self._processed_curve.setData(self._time, processed)
        top, bottom = self._envelope
        top.setData(self._time, self._peak * m)
        bottom.setData(self._time, -self._peak * m)
        self._modulator.setTitle(f"Modulating signal m(t): {description}", size="9pt")

    def set_cursor(self, seconds: float | None) -> None:
        for cursor in self._cursors:
            if seconds is None:
                cursor.hide()
            else:
                cursor.setValue(seconds * self._unit_scale)
                cursor.show()
