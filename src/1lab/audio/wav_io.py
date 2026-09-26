"""WAV reading (metadata + samples) and faithful segment writing.

Reading combines two sources:

* ``scipy.io.wavfile.read`` decodes the samples into a numpy array. It handles
  every format in the data set (16-bit int, packed 24-bit, 24-in-32-bit
  containers and 32-bit float), but it hides the declared bit depth.
* A small manual walk of the RIFF ``fmt `` chunk recovers the authoritative
  metadata (channel count, sample rate, container bit depth and the valid bits
  per sample) needed for the on-graph quality indicators (requirement 6).

Writing preserves the source format byte-for-byte: the original ``fmt `` chunk
is copied verbatim and the exported ``data`` chunk is a slice of the original
data bytes, so a 24-bit file stays 24-bit, float stays float, and so on.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from scipy.io import wavfile

from audio.audio_signal import AudioSignal

FMT_EXTENSIBLE = 0xFFFE


@dataclass
class WavFormat:
    """Metadata parsed directly from the RIFF ``fmt `` and ``data`` chunks."""

    channels: int
    sample_rate: int
    bits_per_sample: int  # container width in the file (wBitsPerSample)
    valid_bits: int  # valid bits per sample (real quantization depth)
    block_align: int  # bytes per frame (all channels)
    data_offset: int  # byte offset of the data-chunk payload
    data_size: int  # data-chunk payload size in bytes
    fmt_chunk: bytes  # verbatim fmt-chunk body bytes


def _parse_fmt(body: bytes) -> dict:
    tag, channels, sample_rate, _byte_rate, block_align, bits = struct.unpack(
        "<HHIIHH", body[:16]
    )
    valid_bits = bits
    if tag == FMT_EXTENSIBLE and len(body) >= 20:
        # WAVEFORMATEXTENSIBLE: wValidBitsPerSample at +18.
        valid_bits = struct.unpack("<H", body[18:20])[0] or bits
    return {
        "channels": channels,
        "sample_rate": sample_rate,
        "bits_per_sample": bits,
        "valid_bits": valid_bits,
        "block_align": block_align,
    }


def parse_wav_format(path: str | Path) -> WavFormat:
    """Walk the RIFF chunks of ``path`` and return its :class:`WavFormat`."""
    with open(path, "rb") as f:
        header = f.read(12)
        if header[:4] != b"RIFF" or header[8:12] != b"WAVE":
            raise ValueError(f"Not a RIFF/WAVE file: {path}")
        fmt: dict | None = None
        fmt_chunk = b""
        data_offset: int | None = None
        data_size = 0
        while True:
            chunk_header = f.read(8)
            if len(chunk_header) < 8:
                break
            chunk_id, size = struct.unpack("<4sI", chunk_header)
            if chunk_id == b"fmt ":
                fmt_chunk = f.read(size)
                fmt = _parse_fmt(fmt_chunk)
                if size & 1:
                    f.seek(1, 1)  # chunks are padded to an even size
            elif chunk_id == b"data":
                data_offset = f.tell()
                data_size = size
                f.seek(size + (size & 1), 1)
            else:
                f.seek(size + (size & 1), 1)
    if fmt is None or data_offset is None:
        raise ValueError(f"Missing fmt/data chunk in {path}")
    block_align = fmt["block_align"] or (
        fmt["channels"] * ((fmt["bits_per_sample"] + 7) // 8)
    )
    return WavFormat(
        channels=fmt["channels"],
        sample_rate=fmt["sample_rate"],
        bits_per_sample=fmt["bits_per_sample"],
        valid_bits=fmt["valid_bits"],
        block_align=block_align,
        data_offset=data_offset,
        data_size=data_size,
        fmt_chunk=fmt_chunk,
    )


def read_signal(path: str | Path) -> AudioSignal:
    """Read a WAV file fully into memory as an :class:`AudioSignal`."""
    path = Path(path)
    fmt = parse_wav_format(path)
    _, samples = wavfile.read(path)
    with open(path, "rb") as f:
        f.seek(fmt.data_offset)
        raw_data = f.read(fmt.data_size)
    return AudioSignal(
        path=path,
        samples=samples,
        sample_rate=fmt.sample_rate,
        n_channels=fmt.channels,
        bits_per_sample=fmt.bits_per_sample,
        valid_bits=fmt.valid_bits,
        raw_data=raw_data,
        frame_size=fmt.block_align,
        fmt_chunk=fmt.fmt_chunk,
    )


def _write_wav(dst: str | Path, fmt_chunk: bytes, data: bytes) -> None:
    fmt_pad = b"\x00" if len(fmt_chunk) & 1 else b""
    data_pad = b"\x00" if len(data) & 1 else b""
    riff_size = (
        4 + (8 + len(fmt_chunk) + len(fmt_pad)) + (8 + len(data) + len(data_pad))
    )
    with open(dst, "wb") as f:
        f.write(b"RIFF")
        f.write(struct.pack("<I", riff_size))
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write(struct.pack("<I", len(fmt_chunk)))
        f.write(fmt_chunk)
        f.write(fmt_pad)
        f.write(b"data")
        f.write(struct.pack("<I", len(data)))
        f.write(data)
        f.write(data_pad)


def write_segment(
    dst: str | Path, signal: AudioSignal, start_frame: int, end_frame: int
) -> int:
    """Write frames ``[start_frame, end_frame)`` of ``signal`` to ``dst``.

    The source ``fmt `` chunk is copied verbatim and the payload is sliced from
    the original data bytes, so the exported file keeps the exact channel count,
    sample rate and bit depth of the source. Returns the number of frames
    written.
    """
    start_frame = max(0, min(start_frame, signal.n_frames))
    end_frame = max(start_frame, min(end_frame, signal.n_frames))
    fs = signal.frame_size
    segment = signal.raw_data[start_frame * fs : end_frame * fs]
    _write_wav(dst, signal.fmt_chunk, segment)
    return end_frame - start_frame
