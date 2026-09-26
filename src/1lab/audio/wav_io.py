from __future__ import annotations

import struct
from pathlib import Path

import soundfile as sf

from audio.audio_signal import AudioSignal
from audio.subtype import Subtype

FMT_EXTENSIBLE = 0xFFFE

_WAV_FORMATS = {"WAV", "WAVEX", "RF64"}


def _valid_bits(path: Path, default: int) -> int:
    with open(path, "rb") as f:
        header = f.read(12)
        if header[:4] not in (b"RIFF", b"RF64") or header[8:12] != b"WAVE":
            return default
        while len(chunk_header := f.read(8)) == 8:
            chunk_id, size = struct.unpack("<4sI", chunk_header)
            if chunk_id == b"fmt ":
                body = f.read(size)
                tag = struct.unpack("<H", body[:2])[0]
                if tag == FMT_EXTENSIBLE and len(body) >= 20:
                    return struct.unpack("<H", body[18:20])[0] or default
                return default
            f.seek(size + (size & 1), 1)
    return default


def read_signal(path: str | Path) -> AudioSignal:
    path = Path(path)
    info = sf.info(path)
    if info.format not in _WAV_FORMATS:
        raise ValueError(f"Not a WAV file: {info.format_info}")
    if info.subtype not in Subtype.__members__:
        raise ValueError(f"Unsupported WAV encoding: {info.subtype_info}")

    subtype = Subtype[info.subtype]
    samples, sample_rate = sf.read(path, dtype=subtype.dtype)
    return AudioSignal(
        path=path,
        samples=samples,
        sample_rate=sample_rate,
        n_channels=info.channels,
        bits_per_sample=subtype.bits,
        valid_bits=_valid_bits(path, subtype.bits),
        subtype=info.subtype,
        file_format=info.format,
    )


def write_segment(
    dst: str | Path, signal: AudioSignal, start_frame: int, end_frame: int
) -> int:
    start_frame = max(0, min(start_frame, signal.n_frames))
    end_frame = max(start_frame, min(end_frame, signal.n_frames))
    sf.write(
        dst,
        signal.samples[start_frame:end_frame],
        signal.sample_rate,
        subtype=signal.subtype,
        format=signal.file_format,
    )
    return end_frame - start_frame
