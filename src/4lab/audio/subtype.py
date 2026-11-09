from __future__ import annotations

from enum import Enum


class Subtype(Enum):
    PCM_U8 = ("int16", 8)
    PCM_16 = ("int16", 16)
    PCM_24 = ("int32", 24)
    PCM_32 = ("int32", 32)
    FLOAT = ("float32", 32)
    DOUBLE = ("float64", 64)

    def __init__(self, dtype: str, bits: int) -> None:
        self.dtype = dtype
        self.bits = bits
