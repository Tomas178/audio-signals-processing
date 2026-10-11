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
    8: ["FL", "FR", "C", "LFE", "BL", "BR", "SL", "SR"],
}

_WAVE_PEN = pg.mkPen((30, 90, 200), width=1)
_REGION_BRUSH = pg.mkBrush(255, 140, 0, 70)
_REGION_PEN = pg.mkPen((230, 120, 0), width=1)


# WAVE_FORMAT_EXTENSIBLE speaker bits; channels appear in the file in bit order.
_SPEAKER_BITS = [
    "FL", "FR", "C", "LFE", "BL", "BR", "FLC", "FRC", "BC",
    "SL", "SR", "TC", "TFL", "TFC", "TFR", "TBL", "TBC", "TBR",
]


def _channel_names(n: int, channel_mask: int = 0) -> list[str]:
    if channel_mask:
        names = [
            name for bit, name in enumerate(_SPEAKER_BITS) if channel_mask >> bit & 1
        ]
        names = names[:n]
        return names + [f"Ch {i + 1}" for i in range(len(names), n)]
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
        self._plots: list[PlotItem] = []
        self._regions: list[LinearRegionItem] = []
        self._unit_scale = 1.0  # multiply seconds by this to get axis units

    def _reset(self) -> None:
        self.clear()
        self._plots = []
        self._regions = []

    def set_signal(self, signal: AudioSignal) -> None:
        self._reset()

        unit = choose_time_unit(signal.duration_s)
        self._unit_scale = 1.0 / unit.seconds

        amplitude = signal.real_amplitude()
        n = signal.n_frames
        time_axis = (
            np.arange(n, dtype=np.float64) / signal.sample_rate
        ) * self._unit_scale
        amp_lo, amp_hi = signal.amplitude_range
        names = _channel_names(signal.n_channels, signal.channel_mask)

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
                plot.setLabel("bottom", f"Time ({unit.label})")
            self._plots.append(plot)

        if self._plots:
            self._plots[0].setTitle(signal.amplitude_label, size="9pt")

    def highlight_segment(self, start_s: float, end_s: float) -> None:
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
