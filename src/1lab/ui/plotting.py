"""pyqtgraph-based waveform view.

Draws one stacked, X-linked plot per channel, with the signal shown as a
continuous-time function (requirement 4), a Y axis in real quantization units
(requirement 5), a title carrying the file name and quality indicators
(requirement 6), and a highlighted segment overlay (requirement 7).

Peak downsampling plus clip-to-view keep rendering fast for very long signals
(requirement 8): no more than a couple of points are drawn per screen pixel,
whatever the length of the signal.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from pyqtgraph import LinearRegionItem, PlotItem

from audio.audio_signal import AudioSignal
from utils.timescale import choose_time_unit, format_duration

_CHANNEL_LAYOUTS = {
    1: ["Mono"],
    2: ["Left", "Right"],
    6: ["FL", "FR", "C", "LFE", "SL", "SR"],
    8: ["FL", "FR", "C", "LFE", "SL", "SR", "BL", "BR"],
}

_WAVE_PEN = pg.mkPen((30, 90, 200), width=1)
_REGION_BRUSH = pg.mkBrush(255, 140, 0, 70)
_REGION_PEN = pg.mkPen((230, 120, 0), width=1)


def _channel_names(n: int) -> list[str]:
    if n in _CHANNEL_LAYOUTS:
        return list(_CHANNEL_LAYOUTS[n])
    return [f"Ch {i + 1}" for i in range(n)]


def _title(signal: AudioSignal) -> str:
    return (
        f"<b>{signal.path.name}</b><br>"
        f"<span style='font-size:9pt'>"
        f"{signal.n_channels} ch &middot; {signal.sample_rate:,} Hz &middot; "
        f"{signal.valid_bits}-bit {signal.format_name} &middot; "
        f"{format_duration(signal.duration_s)}</span>"
    )


class WaveformView(pg.GraphicsLayoutWidget):
    """A stacked, X-linked multi-channel waveform plot."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackground("w")
        self._signal: AudioSignal | None = None
        self._plots: list[PlotItem] = []
        self._regions: list[LinearRegionItem] = []
        self._unit_scale = 1.0  # multiply seconds by this to get axis units

    def _reset(self) -> None:
        self.clear()
        self._plots = []
        self._regions = []

    def set_signal(self, signal: AudioSignal) -> None:
        """Display ``signal``, replacing whatever was shown before."""
        self._reset()
        self._signal = signal

        unit_label, seconds_per_unit = choose_time_unit(signal.duration_s)
        self._unit_scale = 1.0 / seconds_per_unit

        amplitude = signal.real_amplitude()
        n = signal.n_frames
        time_axis = (
            np.arange(n, dtype=np.float64) / signal.sample_rate
        ) * self._unit_scale
        amp_lo, amp_hi = signal.amplitude_range
        names = _channel_names(signal.n_channels)

        self.addLabel(_title(signal), row=0, col=0)

        base_plot = None
        for ch in range(signal.n_channels):
            plot = self.addPlot(row=ch + 1, col=0)
            plot.showGrid(x=True, y=True, alpha=0.25)
            plot.setDownsampling(auto=True, mode="peak")
            plot.setClipToView(True)
            plot.setLabel("left", names[ch])
            plot.setYRange(amp_lo, amp_hi, padding=0.05)
            plot.setMouseEnabled(x=True, y=False)

            ydata = amplitude[:, ch] if amplitude.ndim > 1 else amplitude
            plot.plot(time_axis, ydata, pen=_WAVE_PEN)

            if base_plot is None:
                base_plot = plot
            else:
                plot.setXLink(base_plot)

            if ch == signal.n_channels - 1:
                plot.setLabel("bottom", f"Time ({unit_label})")
            self._plots.append(plot)

        # A shared amplitude caption on the first plot's left axis area.
        if self._plots:
            self._plots[0].setTitle(signal.amplitude_label, size="9pt")

    def highlight_segment(self, start_s: float, end_s: float) -> None:
        """Draw a highlighted region spanning ``[start_s, end_s]`` seconds."""
        self.clear_regions()
        if not self._plots:
            return
        x0 = start_s * self._unit_scale
        x1 = end_s * self._unit_scale
        for plot in self._plots:
            region = pg.LinearRegionItem(
                values=(x0, x1),
                movable=False,
                brush=_REGION_BRUSH,
                pen=_REGION_PEN,
            )
            region.setZValue(-10)
            plot.addItem(region)
            self._regions.append(region)

    def clear_regions(self) -> None:
        for plot, region in zip(self._plots, self._regions, strict=False):
            plot.removeItem(region)
        self._regions = []
