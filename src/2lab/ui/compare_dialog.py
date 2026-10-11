from __future__ import annotations

import math

from PyQt6 import QtCore, QtWidgets

from analysis.entropy import BinRange
from analysis.summary import FileSummary

_COLUMNS = (
    "File",
    "Type",
    "Ch",
    "Rate, Hz",
    "Duration, s",
    "H, bits",
    "H / Hmax",
    "Local mean",
    "Local std",
    "Local min",
    "Local max",
    "H − local mean",
)

_NUMBER_ALIGN = (
    QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
)


def _row(summary: FileSummary) -> list:
    a = summary.analysis
    return [
        summary.path.name,
        summary.kind,
        summary.n_channels,
        summary.sample_rate,
        round(summary.duration_s, 2),
        a.entropy,
        a.entropy / a.h_max,
        a.local_mean,
        a.local_std,
        a.local_min,
        a.local_max,
        a.gap,
    ]


def _item(value) -> QtWidgets.QTableWidgetItem:
    item = QtWidgets.QTableWidgetItem()
    if isinstance(value, str):
        item.setText(value)
        return item
    if isinstance(value, float) and math.isnan(value):
        item.setText("–")
    else:
        rounded = round(value, 3) if isinstance(value, float) else value
        item.setData(QtCore.Qt.ItemDataRole.DisplayRole, rounded)
    item.setTextAlignment(_NUMBER_ALIGN)
    return item


class CompareDialog(QtWidgets.QDialog):
    """Global and local entropy of several files side by side (task part a)."""

    def __init__(
        self,
        summaries: list[FileSummary],
        frame_ms: int,
        bins: int,
        bin_range: BinRange,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Entropy comparison")
        self.resize(1180, 480)

        header = QtWidgets.QLabel(
            f"L = {bins} bins (H<sub>max</sub> = {math.log2(bins):.2f} bits) "
            f"&middot; {frame_ms} ms frames, 50 % overlap &middot; {bin_range.label}"
            " &middot; multi-channel files are mixed to mono &middot; the type comes"
            " from the file name &middot; click a column header to sort"
        )
        header.setWordWrap(True)

        self.table = QtWidgets.QTableWidget(len(summaries), len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.verticalHeader().setVisible(False)
        for row, summary in enumerate(summaries):
            for col, value in enumerate(_row(summary)):
                self.table.setItem(row, col, _item(value))
        # Keep the given order until a column header is clicked.
        self.table.horizontalHeader().setSortIndicator(
            -1, QtCore.Qt.SortOrder.AscendingOrder
        )
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Close
        )
        buttons.rejected.connect(self.close)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(header)
        layout.addWidget(self.table, stretch=1)
        layout.addWidget(buttons)
