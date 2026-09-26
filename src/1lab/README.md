# Lab 1 — Audio Signal Reading and Visualization

A desktop tool (PyQt6 + pyqtgraph) that opens a `*.wav` file, reads the whole
signal into memory, and draws it as a continuous-time waveform with real,
per-quantization-depth amplitude. Any channel count, sample rate and bit depth
is supported. A segment can be selected by start time and duration and exported
to a new WAV file with the exact original format.

## Running

```bash
make setup      # uv sync (installs numpy, soundfile, PyQt6, pyqtgraph)
make run1       # launch the GUI  (uv run python src/1lab/main.py)
make test1      # headless self-test over data/Garsai1 (no display needed)
```

Open a file with **Open .wav…**. Sample files live in `data/Garsai1/`.

## Modules

| File | Responsibility |
|------|----------------|
| `main.py` | Entry point. |
| **`audio/`** | **Signal model + WAV file format (no Qt)** |
| `audio/audio_signal.py` | `AudioSignal` dataclass: in-memory samples + metadata, `real_amplitude()`, amplitude range/label, time↔frame conversion. |
| `audio/subtype.py` | `Subtype` enum of the WAV encodings the tool reads (`PCM_U8` … `DOUBLE`), each with the numpy `dtype` it is decoded into and its `bits`. |
| `audio/wav_io.py` | WAV reading and segment writing with `soundfile` (libsndfile); a small RIFF walk reads the valid bits of WAVE_FORMAT_EXTENSIBLE headers. |
| **`ui/`** | **PyQt6 / pyqtgraph interface** |
| `ui/main_window.py` | Window: file dialog, metadata info bar, segment controls, save dialog. |
| `ui/plotting.py` | `WaveformView`: stacked X-linked per-channel plots, peak downsampling, segment highlight overlay. |
| **`utils/`** | **Small pure helpers** |
| `utils/time_unit.py` | `TimeUnit` enum (ms / s / min / h) with a `label` and `seconds` per unit. |
| `utils/timescale.py` | Adaptive time-axis unit (ms / s / min / h) and duration formatting. |
| **`scripts/`** | **Runnable dev tools (not imported by the app)** |
| `scripts/selftest.py` | Headless verification over the sample set (`make test1`). |
| `scripts/bench_large.py` | Large-signal render/interaction benchmark (requirement 8). |

Dependencies flow one way: `ui` and `scripts` import from `audio` and `utils`;
`audio` never imports Qt, so the self-test runs headless. Imports are absolute
(`from audio.wav_io import read_signal`) and resolve because `src/1lab` is on
`sys.path` — as the script directory for `main.py`, and as the working directory
when the scripts run as modules from `src/1lab` (`python -m scripts.selftest`,
`python -m scripts.bench_large`).

## How the requirements are met

1. **File dialog** — `QFileDialog.getOpenFileName` filtered to `*.wav`.
2. **Read into memory, render from memory** — `read_signal` loads the full
   sample array (`AudioSignal.samples`); all drawing and export work from that
   in-memory copy, and the source file is never read again.
3. **Any quality** — verified on 1 / 2 / 6 / 8 channels, 16–96 kHz, 16-bit,
   packed 24-bit, 32-bit and 32-bit float (see table below); the self-test also
   round-trips 8-bit unsigned, 16/24/32-bit PCM and 32/64-bit float.
   `soundfile` (libsndfile) decodes the samples and names the encoding
   (`PCM_U8`, `PCM_16`, `PCM_24`, `PCM_32`, `FLOAT`, `DOUBLE`) for plain WAV,
   WAVE_FORMAT_EXTENSIBLE and RF64 (> 4 GB) files. The one field it does not
   expose — the valid bits of an extensible header, e.g. 24 valid bits in a
   32-bit container — is read by a small RIFF walk.
4. **Continuous-time function, adaptive axis** — line plot; the X-axis unit is
   chosen from the duration: `< 1 s → ms`, `< 90 s → s`, `< 1 h → min`, else `h`.
5. **Real amplitude per quantization depth** — `real_amplitude()` returns the
   integer sample values on the true bit-depth scale (±2⁷, ±2¹⁵, ±2²³, ±2³¹;
   float is shown natively). libsndfile left-justifies samples into the integer
   type they are read into (24-bit into `int32`, ×256; unsigned 8-bit into a
   signed `int16`, ×256), so the samples are shifted back down by
   `container_bits − valid_bits` — a 24-bit signal lands in the ±2²³ range, not
   ±2³¹, and an 8-bit one in −128…127.
6. **On-graph quality indicators** — the plot title and info bar show the file
   name, channel count, sample rate and bit depth.
7. **Segment select + export** — type a start time and duration; the range is
   highlighted on every channel. **Save segment…** writes the selected frames
   with `soundfile`, using the source's container (WAV / WAVEX / RF64) and
   encoding, so the export keeps the exact format (a 24-bit source stays 24-bit,
   float stays float) and its samples are bit-identical to the source.
   libsndfile always declares valid bits = container width, so a rare
   24-in-32-bit source is exported as plain 32-bit with the same sample bytes.
8. **Very long signals** — see the evaluation below.

## Sample files (`data/Garsai1/`)

| File | Channels | Sample rate | Bit depth (header) | Format |
|------|:--------:|:-----------:|:------------------:|--------|
| Sinus_125Hz / Sinus_500Hz | 1 | 22 050 Hz | 16-bit | PCM |
| DTMF_tones | 1 | 16 000 Hz | 16-bit | PCM |
| Brown_noise | 1 | 48 000 Hz | 16-bit | PCM |
| Pure_tones | 1 | 44 100 Hz | 16-bit | PCM |
| Multitone | 2 | 44 100 Hz | 16-bit | PCM |
| Pink_noise | 1 | 32 000 Hz | 32-bit | **IEEE float** |
| Music#1 | 2 | 48 000 Hz | 32-bit* | PCM (extensible) |
| Music#2 | 2 | 96 000 Hz | 32-bit* | PCM (extensible) |
| Speech#1 | 6 (5.1) | 48 000 Hz | 24-bit | PCM (extensible) |
| Speech#2 | 8 (7.1) | 48 000 Hz | 24-bit | PCM (extensible) |

\* The Music files are named "24-bit" but their `fmt ` header declares 32 valid
bits and the data fills the full 32-bit range, so the tool reports 32-bit (the
header is authoritative). The packed 24-bit Speech files correctly report and
scale as 24-bit.

## Requirement 8 — rendering very long signals

**Strategy.** Every channel plot uses pyqtgraph peak downsampling
(`setDownsampling(auto=True, mode="peak")`) with `setClipToView(True)`. Together
they draw at most a couple of min/max points per horizontal pixel, and only for
the portion of the signal currently visible — so cost tracks the window on
screen, not the total length.

**Measured** (`cd src/1lab && QT_QPA_PLATFORM=offscreen uv run python -m
scripts.bench_large`, 1200×700 view; times are machine-dependent):

| Signal | Metric | Downsampled | Naive (all points) | Speed-up |
|--------|--------|:-----------:|:-------------------:|:--------:|
| Music#2 (5.76M samples, 30 s) | initial render | 127 ms | 121 ms | 1.0× |
| Music#2 | repaint while panning | 3.6 ms/frame | 45 ms/frame | ~13× |
| Synthetic 10 min mono (28.8M samples) | initial render | 129 ms | 936 ms | ~7× |
| Synthetic 10 min mono | repaint while panning | 2.2 ms/frame | 198 ms/frame | ~90× |

**Reading of the results.** For a one-off render of a few million points the two
approaches are similar (the downsampling pass roughly cancels the smaller draw).
The difference grows with length — ~7× on the 10-minute signal — and is decisive
during **interaction**: panning/zooming stays smooth (2–4 ms/frame ≈ 250+ fps)
regardless of duration, whereas the naive path reprocesses every sample each
frame and drops to ~5 fps on the long signal.

**Memory.** The signal is kept once, as the numpy sample array that both drawing
and export use (24-bit sources take 4/3 of their data-chunk size because
libsndfile widens them to `int32`). While a file is shown, the plot also holds
the time axis (8 bytes per frame) and, for 8- and 24-bit sources, the
down-shifted amplitude array. For the bundled files this is tens of MB.
