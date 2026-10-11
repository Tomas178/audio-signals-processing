"""Headless verification over the sample files (no GUI required).

Run as a module from ``src/1lab`` (or via ``make test1`` from the repo root):

    cd src/1lab && uv run python -m scripts.selftest

For each file in ``data/Garsai1/`` it checks that the parsed channel count and
sample rate match the name, that :meth:`AudioSignal.real_amplitude` stays within
the quantization range (with packed 24-bit files landing in the +/-2**23 range,
proving the down-shift), and that exporting a 0.5 s segment round-trips with the
same format and bit-identical samples. It also writes a half-scale sine in every
supported encoding (8-bit unsigned up to 64-bit float) and checks that it reads
back with the right depth, signed and on the real amplitude scale.
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from audio.wav_io import read_signal, write_segment
from utils.timescale import choose_time_unit, format_duration

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "Garsai1"


def _check_timescale() -> list[str]:
    """Verify the adaptive time-axis thresholds (requirement 4) and that
    durations just under a unit boundary roll over when formatted."""
    cases = {0.5: "ms", 5.0: "s", 59.0: "s", 300.0: "min", 7200.0: "h"}
    errors = []
    for duration, expected in cases.items():
        label = choose_time_unit(duration).label
        if label != expected:
            errors.append(f"choose_time_unit({duration}): {label!r} != {expected!r}")
    formats = {
        0.99996: "1.00 s",
        59.999: "1 min 0.0 s",
        119.96: "2 min 0.0 s",
        3599.96: "1 h 0 min",
        7199.0: "1 h 59 min",
    }
    for seconds, expected in formats.items():
        text = format_duration(seconds)
        if text != expected:
            errors.append(f"format_duration({seconds}): {text!r} != {expected!r}")
    return errors


_ENCODINGS = {
    "PCM_U8": 8,
    "PCM_16": 16,
    "PCM_24": 24,
    "PCM_32": 32,
    "FLOAT": 32,
    "DOUBLE": 64,
}


def _check_encodings() -> list[str]:
    """Write a half-scale sine in every supported encoding and verify that it
    reads back with the right depth, signed and on the real amplitude scale."""
    errors = []
    sine = 0.5 * np.sin(np.linspace(0, 20 * np.pi, 4800))
    with tempfile.TemporaryDirectory() as tmp:
        for subtype, bits in _ENCODINGS.items():
            path = Path(tmp) / f"{subtype}.wav"
            sf.write(path, sine, 48000, subtype=subtype)
            signal = read_signal(path)
            full_scale = 1.0 if signal.is_float else 2 ** (bits - 1)
            amp = signal.real_amplitude() / full_scale
            if signal.valid_bits != bits:
                errors.append(f"{subtype}: valid bits {signal.valid_bits} != {bits}")
            if abs(amp.max() - 0.5) > 0.01 or abs(amp.min() + 0.5) > 0.01:
                errors.append(
                    f"{subtype}: amplitude [{amp.min():.3f}, {amp.max():.3f}] "
                    "of full scale, expected +/-0.5"
                )
    return errors


_CHANNELS = {"mono": 1, "stereo": 2, "5.1": 6, "7.1": 8}
_FORMAT_FIELDS = (
    "file_format",
    "subtype",
    "sample_rate",
    "n_channels",
    "valid_bits",
    "channel_mask",
)


def _expected_from_name(name: str) -> tuple[int | None, int | None, int | None]:
    """Best-effort parse of ``[layout, rate kHz, depth-bit]`` from a file name.

    Uses targeted searches rather than splitting on commas, because the sample
    rates use a European decimal comma (e.g. ``44,1 kHz``).
    """
    match = re.search(r"\[([^\]]+)\]", name)
    if not match:
        return None, None, None
    text = match.group(1).lower()

    channels = next((v for k, v in _CHANNELS.items() if k in text), None)

    rate = None
    rate_match = re.search(r"(\d+(?:[.,]\d+)?)\s*khz", text)
    if rate_match:
        rate = int(round(float(rate_match.group(1).replace(",", ".")) * 1000))

    bits = None
    bits_match = re.search(r"(\d+)\s*-?\s*bit", text)
    if bits_match:
        bits = int(bits_match.group(1))
    return channels, rate, bits


def _check_file(path: Path) -> list[str]:
    errors: list[str] = []
    exp_ch, exp_rate, exp_bits = _expected_from_name(path.name)
    signal = read_signal(path)

    if exp_ch is not None and signal.n_channels != exp_ch:
        errors.append(f"channels {signal.n_channels} != expected {exp_ch}")
    if exp_rate is not None and signal.sample_rate != exp_rate:
        errors.append(f"sample rate {signal.sample_rate} != expected {exp_rate}")

    amp = signal.real_amplitude()
    if signal.is_float:
        peak = float(np.max(np.abs(amp))) if signal.n_frames else 0.0
        if peak > 8.0:
            errors.append(f"float peak {peak:.3f} implausibly large")
    else:
        peak = int(np.max(np.abs(amp.astype(np.int64)))) if signal.n_frames else 0
        limit = 2 ** (signal.valid_bits - 1)
        if peak > limit:
            errors.append(f"peak {peak} exceeds +/-2**{signal.valid_bits - 1}")
        # Packed 24-bit sources must be down-shifted into the 24-bit range.
        if signal.bits_per_sample == 24 and signal.valid_bits == 24 and peak >= 2**24:
            errors.append(f"24-bit peak {peak} not down-shifted (>= 2**24)")

    # Segment round-trip: export the first 0.5 s (or the whole file if shorter).
    end_frame = min(signal.n_frames, signal.sample_rate // 2) or signal.n_frames
    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / "segment.wav"
        frames = write_segment(dst, signal, 0, end_frame)
        if frames != end_frame:
            errors.append(f"wrote {frames} frames, expected {end_frame}")
        reread = read_signal(dst)
        if reread.n_frames != end_frame:
            errors.append(f"re-read {reread.n_frames} frames, expected {end_frame}")
        for field in _FORMAT_FIELDS:
            got, want = getattr(reread, field), getattr(signal, field)
            if got != want:
                errors.append(f"exported {field} {got!r} != source {want!r}")
        if not np.array_equal(reread.samples, signal.samples[:end_frame]):
            errors.append("exported samples differ from source")

    peak_unit = "of full scale" if signal.is_float else "levels"
    depth = f"{signal.valid_bits}-bit"
    if exp_bits is not None and exp_bits != signal.valid_bits:
        depth += f" (name says {exp_bits}-bit)"
    print(
        f"  {path.name:46s} {signal.n_channels}ch "
        f"{signal.sample_rate:>6d}Hz {depth:>16s} {signal.format_name:<10s} "
        f"peak={peak} {peak_unit}"
    )
    return errors


def main() -> int:
    files = sorted(DATA_DIR.glob("*.wav"))
    if not files:
        print(f"No .wav files found in {DATA_DIR}", file=sys.stderr)
        return 2
    print(f"Testing {len(files)} files in {DATA_DIR}:")
    failed = 0
    for err in _check_timescale():
        print(f"  time-axis FAIL: {err}")
        failed += 1
    for err in _check_encodings():
        print(f"  encoding FAIL: {err}")
        failed += 1
    for path in files:
        try:
            errors = _check_file(path)
        except Exception as exc:
            print(f"  {path.name:46s} ERROR: {exc}")
            failed += 1
            continue
        for err in errors:
            print(f"      FAIL: {err}")
        failed += 1 if errors else 0
    print("-" * 70)
    if failed:
        print(f"FAILED: {failed} file(s) had problems.")
        return 1
    print("OK: all files parsed, scaled and round-tripped correctly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
