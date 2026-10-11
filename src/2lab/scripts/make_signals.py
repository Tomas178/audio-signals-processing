"""Write reference signals with a known entropy into ``data/Generated``.

Run as a module from ``src/2lab`` (or via ``make signals2`` from the repo root):

    cd src/2lab && uv run python -m scripts.make_signals

Uniform white noise fills every histogram bin equally (the maximum entropy,
log2 L), Gaussian white noise is the usual model of a random signal, and a
square wave takes only two values (exactly 1 bit). The files use the naming
of ``data/Garsai1`` and a fixed seed, so they are reproducible.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

OUT_DIR = Path(__file__).resolve().parents[3] / "data" / "Generated"
SAMPLE_RATE = 44100
SECONDS = 5.0


def _signals() -> dict[str, np.ndarray]:
    rng = np.random.default_rng(2026)
    t = np.arange(int(SAMPLE_RATE * SECONDS)) / SAMPLE_RATE
    return {
        "White_noise_uniform": rng.uniform(-0.5, 0.5, t.size),
        "White_noise_gaussian": np.clip(rng.normal(0.0, 0.125, t.size), -1.0, 1.0),
        "Square_440Hz": np.where(np.sin(2 * np.pi * 440.0 * t) >= 0, 0.5, -0.5),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, wave in _signals().items():
        path = OUT_DIR / f"{name} [mono, 44,1 kHz, 16-bit].wav"
        sf.write(path, wave, SAMPLE_RATE, subtype="PCM_16")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
