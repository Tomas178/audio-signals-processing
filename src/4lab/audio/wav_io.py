from __future__ import annotations

import struct
from pathlib import Path

import soundfile as sf

from audio.audio_signal import AudioSignal
from audio.subtype import Subtype

FMT_EXTENSIBLE = 0xFFFE

_WAV_FORMATS = {"WAV", "WAVEX", "RF64"}


def _fmt_chunk_offset(f) -> int | None:
    header = f.read(12)
    if header[:4] not in (b"RIFF", b"RF64") or header[8:12] != b"WAVE":
        return None
    while len(chunk_header := f.read(8)) == 8:
        chunk_id, size = struct.unpack("<4sI", chunk_header)
        if chunk_id == b"fmt ":
            return f.tell()
        f.seek(size + (size & 1), 1)
    return None


def _extensible_fields(path: Path, default_bits: int) -> tuple[int, int]:
    with open(path, "rb") as f:
        if _fmt_chunk_offset(f) is None:
            return default_bits, 0
        body = f.read(24)
        tag = struct.unpack("<H", body[:2])[0]
        if tag != FMT_EXTENSIBLE or len(body) < 24:
            return default_bits, 0
        valid_bits, channel_mask = struct.unpack("<HI", body[18:24])
        return valid_bits or default_bits, channel_mask


def read_signal(path: str | Path) -> AudioSignal:
    path = Path(path)
    info = sf.info(path)
    if info.format not in _WAV_FORMATS:
        raise ValueError(f"Not a WAV file: {info.format_info}")
    if info.subtype not in Subtype.__members__:
        raise ValueError(f"Unsupported WAV encoding: {info.subtype_info}")

    subtype = Subtype[info.subtype]
    samples, sample_rate = sf.read(path, dtype=subtype.dtype)
    valid_bits, channel_mask = _extensible_fields(path, subtype.bits)
    return AudioSignal(
        path=path,
        samples=samples,
        sample_rate=sample_rate,
        n_channels=info.channels,
        bits_per_sample=subtype.bits,
        valid_bits=valid_bits,
        subtype=info.subtype,
        file_format=info.format,
        channel_mask=channel_mask,
    )
