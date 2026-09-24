"""Entry point for Lab 1 - audio signal reading and visualization.

Run with the project's virtual environment, e.g. ``uv run python src/1lab/main.py``
(or ``make run1``).
"""

import sys

from PyQt6 import QtWidgets

from ui.main_window import MainWindow


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
