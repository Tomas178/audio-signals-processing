from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore

from analysis.spectrum import Spectrum
from audio.audio_signal import AudioSignal
from utils.timescale import choose_time_unit

_WAVE_PEN = pg.mkPen((30, 90, 200), width=1)
_WINDOWED_PEN = pg.mkPen((230, 120, 0), width=1)
_AMPLITUDE_PEN = pg.mkPen((30, 90, 200), width=1.5)
_DENSITY_PEN = pg.mkPen((200, 40, 40), width=1.5)
_REGION_BRUSH = pg.mkBrush(255, 140, 0, 70)
_REGION_PEN = pg.mkPen((230, 120, 0), width=1)
_LEGEND_BRUSH = pg.mkBrush(255, 255, 255, 220)


class SpectrumView(pg.GraphicsLayoutWidget):
    """The signal with the selected segment, the segment itself, and the
    segment's spectrum: amplitude spectrum and spectral density together."""

    segmentChanged = QtCore.pyqtSignal(float, float)  # start, end in seconds
    spectrumHovered = QtCore.pyqtSignal(int)  # frequency index k

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackground("w")
        self._spectrum: Spectrum | None = None
        self._unit_scale = 1.0  # multiply seconds by this to get axis units

        self._title = self.addLabel("Open a .wav file to begin.", row=0, col=0)
        self._wave = self.addPlot(row=1, col=0)
        self._segment = self.addPlot(row=2, col=0)
        self._freq = self.addPlot(row=3, col=0)
        for row, stretch in ((1, 2), (2, 2), (3, 3)):
            self.ci.layout.setRowStretchFactor(row, stretch)

        for plot in (self._wave, self._segment, self._freq):
            plot.showGrid(x=True, y=True, alpha=0.25)
            plot.setDownsampling(auto=True, mode="peak")
            plot.setClipToView(True)
        for plot in (self._wave, self._segment):
            plot.setMouseEnabled(x=True, y=False)
            plot.getAxis("left").enableAutoSIPrefix(False)  # integer PCM levels

        self._wave_curve = self._wave.plot(pen=_WAVE_PEN)
        self._region = pg.LinearRegionItem(brush=_REGION_BRUSH, pen=_REGION_PEN)
        self._region.setZValue(-10)
        self._region.hide()
        self._wave.addItem(self._region)

        self._segment_curve = self._segment.plot(pen=_WAVE_PEN)
        self._windowed_curve = self._segment.plot(pen=_WINDOWED_PEN)

        self._freq.addLegend(offset=(-10, 5), brush=_LEGEND_BRUSH)
        self._amplitude_curve = self._freq.plot(
            pen=_AMPLITUDE_PEN, name="Amplitude spectrum |X(f)|"
        )
        self._density_curve = self._freq.plot(
            pen=_DENSITY_PEN, name="Spectral density S(f) = |X(f)|²"
        )
        self._freq.setLabel("bottom", "Frequency", units="Hz")
        self._freq.setLabel("left", "Relative value (max = 1)")
        self._freq.setYRange(0.0, 1.0, padding=0.05)

        self._region.sigRegionChanged.connect(self._on_region_changed)
        self.scene().sigMouseMoved.connect(self._on_mouse_moved)

    def show_signal(
        self, signal: AudioSignal, samples: np.ndarray, channel: str
    ) -> None:
        unit = choose_time_unit(signal.duration_s)
        self._unit_scale = 1.0 / unit.seconds
        time = np.arange(samples.size) * (self._unit_scale / signal.sample_rate)
        self._wave_curve.setData(time, samples)
        self._wave.enableAutoRange(x=True)
        peak = float(np.max(np.abs(samples))) if samples.size else 0.0
        peak = peak if peak > 0 else 1.0
        self._wave.setYRange(-peak, peak, padding=0.05)
        self._wave.setLabel("left", channel)
        self._wave.setLabel("bottom", f"Time ({unit.label})")
        self._wave.setTitle(
            f"Signal &middot; {signal.amplitude_label} &middot; "
            "drag the orange segment or its edges",
            size="9pt",
        )
        self._region.blockSignals(True)  # clamping to new bounds is not a user edit
        self._region.setBounds((0, signal.duration_s * self._unit_scale))
        self._region.blockSignals(False)
        self._region.show()
        self._freq.setXRange(0.0, signal.sample_rate / 2, padding=0.0)
        self._freq.setYRange(0.0, 1.0, padding=0.05)
        self._title.setText(f"<b>{signal.path.name}</b> &middot; {channel}")

    def set_segment(self, start_s: float, end_s: float) -> None:
        self._region.blockSignals(True)
        self._region.setRegion((start_s * self._unit_scale, end_s * self._unit_scale))
        self._region.blockSignals(False)

    def show_segment(
        self,
        start_s: float,
        sample_rate: int,
        segment: np.ndarray,
        windowed: np.ndarray,
    ) -> None:
        duration = segment.size / sample_rate
        unit = choose_time_unit(duration)
        time = np.arange(segment.size) / sample_rate / unit.seconds
        self._segment_curve.setData(time, segment)
        self._windowed_curve.setData(time, windowed)
        self._segment.enableAutoRange()
        self._segment.setLabel("bottom", f"Time from the segment start ({unit.label})")
        self._segment.setTitle(
            f"Selected segment {start_s:.4f} – {start_s + duration:.4f} s "
            f"({segment.size:,} samples): "
            f"<span style='color:{_WAVE_PEN.color().name()}'>x(n)</span> and "
            f"<span style='color:{_WINDOWED_PEN.color().name()}'>"
            "x(n)&middot;l(n)</span>, the windowed segment the DFT is computed from",
            size="9pt",
        )

    def show_spectrum(self, spectrum: Spectrum) -> None:
        self._spectrum = spectrum
        self._amplitude_curve.setData(spectrum.frequencies, spectrum.relative_amplitude)
        self._density_curve.setData(spectrum.frequencies, spectrum.relative_density)
        silent = " &middot; silent segment" if not spectrum.amplitude.any() else ""
        self._freq.setTitle(
            f"Spectrum of the segment &middot; window: {spectrum.window.label} "
            f"&middot; N = {spectrum.n:,} &middot; "
            f"&Delta;f = f<sub>s</sub>/N = {spectrum.resolution_hz:.2f} Hz{silent}",
            size="9pt",
        )

    def clear_segment(self, message: str) -> None:
        self._spectrum = None
        for curve in (
            self._segment_curve,
            self._windowed_curve,
            self._amplitude_curve,
            self._density_curve,
        ):
            curve.clear()
        self._segment.setTitle(message, size="9pt")
        self._freq.setTitle(message, size="9pt")

    def _on_region_changed(self) -> None:
        lo, hi = self._region.getRegion()
        self.segmentChanged.emit(lo / self._unit_scale, hi / self._unit_scale)

    def _on_mouse_moved(self, pos) -> None:
        spectrum = self._spectrum
        vb = self._freq.vb
        if spectrum is None or not vb.sceneBoundingRect().contains(pos):
            return
        k = round(vb.mapSceneToView(pos).x() / spectrum.resolution_hz)
        if 0 <= k < spectrum.frequencies.size:
            self.spectrumHovered.emit(k)
