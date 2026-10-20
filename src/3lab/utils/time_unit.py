from __future__ import annotations

from enum import Enum


class TimeUnit(Enum):
    MILLISECOND = ("ms", 1e-3)
    SECOND = ("s", 1.0)
    MINUTE = ("min", 60.0)
    HOUR = ("h", 3600.0)

    def __init__(self, label: str, seconds: float) -> None:
        self.label = label
        self.seconds = seconds
