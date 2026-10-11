from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore

from analysis.entropy import EntropyAnalysis, Histogram
from audio.audio_signal import AudioSignal
from utils.timescale import choose_time_unit

_WAVE_PEN = pg.mkPen((30, 90, 200), width=1)
_LOCAL_PEN = pg.mkPen((20, 130, 90), width=1.5)
_LOCAL_BRUSH = pg.mkBrush(20, 130, 90, 45)
_GLOBAL_PEN = pg.mkPen((200, 40, 40), width=1.5, style=QtCore.Qt.PenStyle.DashLine)
_MAX_PEN = pg.mkPen((110, 110, 110), width=1, style=QtCore.Qt.PenStyle.DotLine)
_REGION_BRUSH = pg.mkBrush(255, 140, 0, 70)
_REGION_PEN = pg.mkPen((230, 120, 0), width=1)
_WHOLE_BRUSH = pg.mkBrush(150, 150, 150, 170)
_SEGMENT_BRUSH = pg.mkBrush(255, 140, 0, 210)
_SPREAD_BRUSH = pg.mkBrush(20, 130, 90, 150)
_SPREAD_BINS = 40


def _bars(brush) -> pg.BarGraphItem:
    empty = np.zeros(0)
    return pg.BarGraphItem(
        x0=0, width=empty, y=empty, height=empty, brush=brush, pen=pg.mkPen(None)
    )


def _set_bars(bars: pg.BarGraphItem, hist: Histogram, thickness: float) -> None:
    widths = np.diff(hist.edges)
    centers = hist.edges[:-1] + widths / 2
    bars.setOpts(x0=0, width=hist.frequencies, y=centers, height=widths * thickness)


def _level_line(pen, label: str, position: float, **label_opts) -> pg.InfiniteLine:
    return pg.InfiniteLine(
        angle=0,
        pen=pen,
        label=label,
        labelOpts={
            "position": position,
            "color": pen.color(),
            "fill": (255, 255, 255, 200),
            **label_opts,
        },
    )


class EntropyView(pg.GraphicsLayoutWidget):
    """Waveform and local entropy (left column, X-linked), each with the
    histogram of its values on a shared Y axis (right column)."""

    segmentChanged = QtCore.pyqtSignal(float, float)
    frameClicked = QtCore.pyqtSignal(int)
    frameHovered = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackground("w")
        self._signal: AudioSignal | None = None
        self._analysis: EntropyAnalysis | None = None
        self._unit_scale = 1.0  # multiply seconds by this to get axis units

        self._title = self.addLabel(
            "Open a .wav file to begin.", row=0, col=0, colspan=2
        )
        self._wave = self.addPlot(row=1, col=0)
        self._values = self.addPlot(row=1, col=1)
        self._local = self.addPlot(row=2, col=0)
        self._spread = self.addPlot(row=2, col=1)
        self.ci.layout.setColumnStretchFactor(0, 4)
        self.ci.layout.setColumnStretchFactor(1, 1)

        for plot in (self._wave, self._local):
            plot.showGrid(x=True, y=True, alpha=0.25)
            plot.setMouseEnabled(x=True, y=False)
        for plot in (self._values, self._spread):
            plot.showGrid(x=True, y=True, alpha=0.25)
            plot.setMouseEnabled(x=False, y=False)
            plot.hideButtons()
            plot.getAxis("bottom").enableAutoSIPrefix(False)
        self._local.setXLink(self._wave)
        self._values.setYLink(self._wave)
        self._spread.setYLink(self._local)
        self._wave.getAxis("left").enableAutoSIPrefix(False)  # same units as values

        self._wave.setDownsampling(auto=True, mode="peak")
        self._wave.setClipToView(True)
        self._wave_curve = self._wave.plot(pen=_WAVE_PEN)
        self._local_curve = self._local.plot(
            pen=_LOCAL_PEN, stepMode="center", fillLevel=0, brush=_LOCAL_BRUSH
        )
        self._local.setLabel("left", "Local H, bits")
        self._local.setTitle("Local (segmental) entropy per frame", size="9pt")
        self._global_line = _level_line(_GLOBAL_PEN, "H = {value:.2f}", 0.92)
        self._max_line = _level_line(
            _MAX_PEN, "Hmax = {value:.2f}", 0.01, anchors=[(0, 1), (0, 1)]
        )
        self._local.addItem(self._global_line)
        self._local.addItem(self._max_line)

        self._whole_bars = _bars(_WHOLE_BRUSH)
        self._segment_bars = _bars(_SEGMENT_BRUSH)
        self._values.addItem(self._whole_bars)
        self._values.addItem(self._segment_bars)
        self._values.setLabel("bottom", "f<sub>i</sub> (share of samples)")

        self._spread_bars = _bars(_SPREAD_BRUSH)
        self._spread_mean = _level_line(_LOCAL_PEN, "mean", 0.85)
        self._spread_global = pg.InfiniteLine(angle=0, pen=_GLOBAL_PEN)
        self._spread.addItem(self._spread_bars)
        self._spread.addItem(self._spread_mean)
        self._spread.addItem(self._spread_global)
        self._spread.setLabel("bottom", "Frames")

        self._region = pg.LinearRegionItem(brush=_REGION_BRUSH, pen=_REGION_PEN)
        self._mirror = pg.LinearRegionItem(
            movable=False, brush=_REGION_BRUSH, pen=_REGION_PEN
        )
        for plot, region in ((self._wave, self._region), (self._local, self._mirror)):
            region.setZValue(-10)
            region.hide()
            plot.addItem(region)

        self._region.sigRegionChanged.connect(self._on_region_changed)
        self.scene().sigMouseMoved.connect(self._on_mouse_moved)
        self.scene().sigMouseClicked.connect(self._on_mouse_clicked)

    def show_analysis(
        self,
        signal: AudioSignal,
        samples: np.ndarray,
        channel: str,
        analysis: EntropyAnalysis,
    ) -> None:
        if signal is not self._signal:
            self._wave.enableAutoRange(x=True)
        self._signal = signal
        self._analysis = analysis
        unit = choose_time_unit(signal.duration_s)
        self._unit_scale = 1.0 / unit.seconds
        to_axis = self._unit_scale / signal.sample_rate

        self._wave_curve.setData(np.arange(samples.size) * to_axis, samples)
        # Fit the histogram's value range, so its bins line up with the waveform.
        value_edges = analysis.whole.edges
        self._wave.setYRange(value_edges[0], value_edges[-1], padding=0.05)
        self._wave.setLabel("left", channel)
        self._wave.setTitle(signal.amplitude_label, size="9pt")
        self._local.setLabel("bottom", f"Time ({unit.label})")
        self._region.blockSignals(True)  # clamping to new bounds is not a user edit
        self._region.setBounds((0, signal.duration_s * self._unit_scale))
        self._region.blockSignals(False)
        self._region.show()
        self._mirror.show()

        framing = analysis.framing
        if analysis.n_frames:
            # Each frame is drawn over the hop centred on it.
            steps = (np.arange(analysis.n_frames + 1) + 0.5) * framing.hop * to_axis
            self._local_curve.setData(steps, analysis.frame_h)
        else:
            self._local_curve.clear()
        self._local.setYRange(0, analysis.h_max, padding=0.1)
        self._global_line.setValue(analysis.entropy)
        self._max_line.setValue(analysis.h_max)

        _set_bars(self._whole_bars, analysis.whole, 0.9)
        counts, edges = np.histogram(
            analysis.frame_h, bins=_SPREAD_BINS, range=(0, analysis.h_max)
        )
        self._spread_bars.setOpts(
            x0=0, width=counts, y=(edges[:-1] + edges[1:]) / 2, height=np.diff(edges)
        )
        self._spread_global.setValue(analysis.entropy)
        self._spread_mean.setVisible(analysis.n_frames > 0)
        if analysis.n_frames:
            self._spread_mean.setValue(analysis.local_mean)
            spread_title = (
                f"Local H: mean {analysis.local_mean:.2f}, std {analysis.local_std:.2f}"
            )
        else:
            spread_title = "Local H: signal shorter than one frame"
        self._spread.setTitle(spread_title, size="9pt")

        self._title.setText(
            f"<b>{signal.path.name}</b> &middot; {channel}<br>"
            f"<span style='font-size:9pt'>"
            f"H = {analysis.entropy:.3f} bits "
            f"({analysis.entropy / analysis.h_max:.2f}&middot;H<sub>max</sub>, "
            f"L = {analysis.bins}) &middot; "
            f"{analysis.n_frames} frames &times; {framing.length_ms:.1f} ms, "
            f"hop {framing.hop_ms:.1f} ms &middot; {analysis.bin_range.label}</span>"
        )

    def show_segment(self, hist: Histogram | None) -> None:
        if hist is None:
            empty = np.zeros(0)
            self._segment_bars.setOpts(width=empty, y=empty, height=empty)
            self._values.setTitle("Value histogram (empty segment)", size="9pt")
            return
        _set_bars(self._segment_bars, hist, 0.45)
        self._values.setTitle(
            f"Values: whole H = {self._analysis.entropy:.2f}, "
            f"<span style='color:#e08000'>segment H = {hist.entropy:.2f}</span>",
            size="9pt",
        )

    def set_segment(self, start_s: float, end_s: float) -> None:
        region = (start_s * self._unit_scale, end_s * self._unit_scale)
        self._region.blockSignals(True)
        self._region.setRegion(region)
        self._region.blockSignals(False)
        self._mirror.setRegion(region)

    def _on_region_changed(self) -> None:
        lo, hi = self._region.getRegion()
        self._mirror.setRegion((lo, hi))
        self.segmentChanged.emit(lo / self._unit_scale, hi / self._unit_scale)

    def _frame_at(self, plot: pg.PlotItem, scene_pos) -> int:
        analysis = self._analysis
        if analysis is None or analysis.n_frames == 0:
            return -1
        t = plot.vb.mapSceneToView(scene_pos).x() / self._unit_scale
        framing = analysis.framing
        k = round(t * framing.sample_rate / framing.hop) - 1  # centre = (k+1)*hop
        return min(max(k, 0), analysis.n_frames - 1)

    def _on_mouse_moved(self, pos) -> None:
        for plot in (self._wave, self._local):
            if plot.vb.sceneBoundingRect().contains(pos):
                k = self._frame_at(plot, pos)
                if k >= 0:
                    self.frameHovered.emit(k)
                return

    def _on_mouse_clicked(self, event) -> None:
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        pos = event.scenePos()
        if self._local.vb.sceneBoundingRect().contains(pos):
            k = self._frame_at(self._local, pos)
            if k >= 0:
                self.frameClicked.emit(k)
