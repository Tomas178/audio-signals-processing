# Lab 2 — Entropy-based Signal Analysis

Task variant 8 (*Entropija grįsta signalų analizė*). A desktop tool (PyQt6 +
pyqtgraph) that opens a `*.wav` file and analyses it through the entropy of its
value histogram:

$$H = -\sum_{i=1}^{L} f_i \log_2 f_i ,$$

where $f_i$ is the share of samples that fall into the $i$-th of $L$
equal-width histogram bins. The tool shows the waveform, the entropy of the
whole signal, the local (segmental) entropy of 20–30 ms overlapping frames, and
the histograms behind both. Any segment or single frame can be inspected, and
many files can be compared in one table.

## Running

```bash
make setup      # uv sync (installs numpy, soundfile, PyQt6, pyqtgraph)
make run2       # launch the GUI  (uv run python src/2lab/main.py)
make test2      # headless self-test: formula, framing, all files, GUI offscreen
make signals2   # write the reference signals to data/Generated/
make report2    # print the result tables of this README (Markdown)
```

Open a file with **Open .wav…**; sample files live in `data/Garsai1/`, and
`make signals2` adds three reference signals in `data/Generated/`.

## Modules

| File | Responsibility |
|------|----------------|
| `main.py` | Entry point. |
| **`analysis/`** | **Entropy analysis (numpy only, no Qt)** |
| `analysis/entropy.py` | Equal-width binning, `entropy_bits`, `Framing` (frames of 2 × hop, i.e. exactly 50 % overlap), vectorised `frame_entropies`, `analyze()` → `EntropyAnalysis` (global H, local H of every frame, segment histograms). |
| `analysis/summary.py` | `summarize_file()` for whole-file comparisons; signal type from the file name. |
| **`audio/`** | **Signal model + WAV reading (lab 1's read path)** |
| `audio/audio_signal.py` | `AudioSignal`: samples + metadata, real amplitude, channel names, `channel_samples()` (one channel or the mix). |
| `audio/subtype.py` | `Subtype` enum of the WAV encodings the tool reads. |
| `audio/wav_io.py` | `read_signal()` with `soundfile`; a small RIFF walk reads the valid bits and channel mask of extensible headers. |
| **`ui/`** | **PyQt6 / pyqtgraph interface** |
| `ui/main_window.py` | Window: file dialogs, settings (channel, frame length, L, bin range), segment controls, info bar. |
| `ui/entropy_view.py` | `EntropyView`: waveform and local-entropy plots, each with its histogram on a shared Y axis; segment region; frame hover/click. |
| `ui/compare_dialog.py` | Sortable table of global and local entropy for many files. |
| **`utils/`** | **Small pure helpers (from lab 1)** |
| `utils/time_unit.py`, `utils/timescale.py` | Adaptive time-axis unit and duration formatting. |
| **`scripts/`** | **Runnable dev tools (not imported by the app)** |
| `scripts/selftest.py` | Headless verification (`make test2`). |
| `scripts/make_signals.py` | Reference signals with a known entropy (`make signals2`). |
| `scripts/report.py` | The result tables below (`make report2`). |

As in lab 1, `ui` and `scripts` import from `analysis`, `audio` and `utils`;
`analysis` and `audio` never import Qt. Imports are absolute and resolve
because `src/2lab` is on `sys.path`.

## Method

- **Histogram.** $L$ equal-width bins (default 16, so $H_{max} = \log_2 16 = 4$
  bits; 2–256 selectable). A value goes to bin
  $\lfloor (x - lo) \cdot L / (hi - lo) \rfloor$, with the maximum in the last
  bin (as `np.histogram` does). Empty bins add nothing ($0 \log 0 := 0$), so
  $0 \le H \le \log_2 L$: 0 when every value falls in one bin, $\log_2 L$ when
  all bins are equally full.
- **Bin range.** By default the bins span the whole signal's min–max and every
  frame and segment is counted in **these same bins**, so local values are
  comparable with each other and with the global one, and silence (all values
  in the zero bin) gives ≈ 0. The alternative, **own range**, bins each frame
  or segment over its own min–max: it ignores the level and keeps only the
  shape of the distribution.
- **Frames.** hop = round(frame_ms · fs / 2000) samples and frame = 2 · hop, so
  the overlap is exactly half a frame at every sample rate (20 ms at 22 050 Hz
  → 440 samples = 19.95 ms). Frame *k* covers samples [k·hop, k·hop + 2·hop);
  only whole frames are used. The frame length is limited to 20–30 ms as the
  task requires.
- **Channels.** Multi-channel files are analysed as their mono mix (mean of
  the channels) by default; any single channel can be chosen instead.
- **Implementation.** Frames are a strided `sliding_window_view` (no copy);
  each block of frames is binned at once and counted with a single
  `np.bincount`, so a 30 s, 96 kHz file is analysed in ≈ 50 ms with bounded
  memory. The global histogram, the segment histogram and the frames all use
  the same binning rule, so a clicked frame's histogram reproduces its local H
  exactly.

## How the task items are met

- **File dialog** — **Open .wav…** uses `QFileDialog.getOpenFileName`
  filtered to `*.wav`.
- **Different recordings and segments** — drag the orange segment on the
  waveform (or type its start and duration) to get its histogram and entropy.
  Click a frame on the entropy plot to snap the segment to that frame, and
  hover to read frame number, time and H. **Compare files…** / **Compare
  folder…** list the global and local entropy of many recordings in a
  sortable table.
- **(a) Entropy of different signal types** — the info bar and plot title show
  H of the open file (in bits and as a share of $H_{max}$). The comparison
  table and [Table 1](#results) give it for periodic, pseudo-periodic and
  random signals; see the [conclusions](#conclusions).
- **(b) Segmental (local) entropy** — 20–30 ms frames with 50 % overlap, H of
  every frame plotted against time (frame centres). The frame number is shown
  on hover.
- **(c) Visualisation** — four linked plots:

  | Plot | Content |
  |------|---------|
  | top left | Waveform with the segment region. |
  | top right | The value histogram ($f_i$) that H is computed from, on the waveform's amplitude axis: grey = whole signal, orange = segment. |
  | bottom left | Local entropy per frame, with the global H (dashed red) and $H_{max}$ (dotted). |
  | bottom right | Distribution of the local entropies, with its mean. |

  The global H value is also in the info bar and the plot title.

## Results

Recordings, grouped as the task asks:
- **Periodic:**
  - `Sinus_125Hz`, `Sinus_500Hz`: pure sines.
  - `Pure_tones`: 250 Hz … 8 kHz octave tones of ~3 s, separated by low-level noise.
  - `Multitone`: a stationary multi-tone test signal, 350–530 Hz, low peak-to-RMS ratio.
  - `DTMF_tones`: dual-tone digits with short digital-silence gaps.
  - `Square_440Hz`: generated.
- **Pseudo-periodic:**
  - `Speech#1`, `Speech#2`: 5.1 and 7.1. Each channel carries one short utterance, so a single channel is ~90 % digital silence.
  - `Music#1`, `Music#2`: the same music at 48 and 96 kHz.
- **Random:**
  - `Pink_noise`, `Brown_noise`.
  - `White_noise_uniform`, `White_noise_gaussian`: generated.

Unless a table says otherwise, the settings are: L = 16, bins shared over the
whole signal, 20 ms frames, and channels mixed. All tables come from
`make report2`.

#### Table 1. Global and local entropy (L = 16, 20 ms frames, shared bins)

| Signal | Type | H, bits | H / Hmax | Local H | Local min – max | H − local mean |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| DTMF_tones | periodic | 3.05 | 0.76 | 2.47 ± 1.74 | 0.00 – 3.93 | 0.59 |
| Multitone | periodic | 3.88 | 0.97 | 3.88 ± 0.01 | 3.87 – 3.88 | 0.00 |
| Pure_tones | periodic | 3.29 | 0.82 | 2.52 ± 1.65 | 0.37 – 3.88 | 0.77 |
| Sinus_125Hz | periodic | 3.79 | 0.95 | 3.78 ± 0.01 | 3.76 – 3.79 | 0.01 |
| Sinus_500Hz | periodic | 3.79 | 0.95 | 3.79 ± 0.00 | 3.79 – 3.79 | 0.00 |
| Square_440Hz | periodic | 1.00 | 0.25 | 1.00 ± 0.00 | 1.00 – 1.00 | 0.00 |
| Music#1 | pseudo-periodic | 2.58 | 0.64 | 2.13 ± 0.69 | 0.00 – 3.89 | 0.45 |
| Music#2 | pseudo-periodic | 2.58 | 0.64 | 2.13 ± 0.69 | 0.00 – 3.89 | 0.45 |
| Speech#1 | pseudo-periodic | 1.05 | 0.26 | 0.51 ± 0.99 | 0.00 – 3.80 | 0.54 |
| Speech#2 | pseudo-periodic | 1.24 | 0.31 | 0.65 ± 1.05 | 0.00 – 3.80 | 0.59 |
| Brown_noise | random | 3.74 | 0.93 | 2.26 ± 0.39 | 0.98 – 3.49 | 1.48 |
| Pink_noise | random | 3.21 | 0.80 | 2.96 ± 0.16 | 2.64 – 3.43 | 0.26 |
| White_noise_gaussian | random | 2.86 | 0.71 | 2.85 ± 0.03 | 2.74 – 2.94 | 0.01 |
| White_noise_uniform | random | 4.00 | 1.00 | 3.99 ± 0.00 | 3.97 – 4.00 | 0.01 |

#### Table 2. Global entropy H, bits (and H / Hmax) for different numbers of bins

| Signal | L = 8 | L = 16 | L = 32 | L = 64 |
|---|:-:|:-:|:-:|:-:|
| DTMF_tones | 2.34 (0.78) | 3.05 (0.76) | 3.77 (0.75) | 4.46 (0.74) |
| Multitone | 2.91 (0.97) | 3.88 (0.97) | 4.81 (0.96) | 5.76 (0.96) |
| Pure_tones | 2.59 (0.86) | 3.29 (0.82) | 3.96 (0.79) | 4.55 (0.76) |
| Sinus_125Hz | 2.85 (0.95) | 3.79 (0.95) | 4.75 (0.95) | 5.72 (0.95) |
| Sinus_500Hz | 2.85 (0.95) | 3.79 (0.95) | 4.75 (0.95) | 5.72 (0.95) |
| Square_440Hz | 1.00 (0.33) | 1.00 (0.25) | 1.00 (0.20) | 1.00 (0.17) |
| Music#1 | 1.70 (0.57) | 2.58 (0.64) | 3.54 (0.71) | 4.53 (0.76) |
| Music#2 | 1.70 (0.57) | 2.58 (0.64) | 3.54 (0.71) | 4.53 (0.76) |
| Speech#1 | 0.82 (0.27) | 1.05 (0.26) | 1.33 (0.27) | 1.66 (0.28) |
| Speech#2 | 0.95 (0.32) | 1.24 (0.31) | 1.59 (0.32) | 2.02 (0.34) |
| Brown_noise | 2.75 (0.92) | 3.74 (0.93) | 4.73 (0.95) | 5.73 (0.96) |
| Pink_noise | 2.25 (0.75) | 3.21 (0.80) | 4.21 (0.84) | 5.20 (0.87) |
| White_noise_gaussian | 1.91 (0.64) | 2.86 (0.71) | 3.84 (0.77) | 4.84 (0.81) |
| White_noise_uniform | 3.00 (1.00) | 4.00 (1.00) | 5.00 (1.00) | 6.00 (1.00) |

#### Table 3. Local entropy (mean ± std, bits) by bin range and frame length

| Signal | shared, 20 ms | shared, 30 ms | own, 20 ms | own, 30 ms |
|---|:-:|:-:|:-:|:-:|
| DTMF_tones | 2.47 ± 1.74 | 2.56 ± 1.61 | 2.80 ± 1.28 | 2.80 ± 1.25 |
| Multitone | 3.88 ± 0.01 | 3.88 ± 0.00 | 3.88 ± 0.01 | 3.88 ± 0.00 |
| Pure_tones | 2.52 ± 1.65 | 2.52 ± 1.65 | 3.49 ± 0.37 | 3.49 ± 0.39 |
| Sinus_125Hz | 3.78 ± 0.01 | 3.79 ± 0.03 | 3.78 ± 0.01 | 3.79 ± 0.03 |
| Sinus_500Hz | 3.79 ± 0.00 | 3.79 ± 0.00 | 3.79 ± 0.00 | 3.79 ± 0.00 |
| Square_440Hz | 1.00 ± 0.00 | 1.00 ± 0.00 | 1.00 ± 0.00 | 1.00 ± 0.00 |
| Music#1 | 2.13 ± 0.69 | 2.17 ± 0.69 | 3.76 ± 0.22 | 3.74 ± 0.25 |
| Music#2 | 2.13 ± 0.69 | 2.17 ± 0.69 | 3.76 ± 0.22 | 3.74 ± 0.25 |
| Speech#1 | 0.51 ± 0.99 | 0.52 ± 1.00 | 1.42 ± 1.64 | 1.38 ± 1.58 |
| Speech#2 | 0.65 ± 1.05 | 0.66 ± 1.05 | 2.03 ± 1.59 | 1.97 ± 1.53 |
| Brown_noise | 2.26 ± 0.39 | 2.49 ± 0.38 | 3.69 ± 0.13 | 3.69 ± 0.13 |
| Pink_noise | 2.96 ± 0.16 | 3.01 ± 0.13 | 3.55 ± 0.09 | 3.50 ± 0.09 |
| White_noise_gaussian | 2.85 ± 0.03 | 2.85 ± 0.03 | 3.36 ± 0.10 | 3.32 ± 0.10 |
| White_noise_uniform | 3.99 ± 0.00 | 3.99 ± 0.00 | 3.99 ± 0.00 | 3.99 ± 0.00 |

#### Table 4. Multi-channel recordings: single channels vs the mix

| Signal | Channels | H of one channel (min – max) | H of the mix |
|---|:-:|:-:|:-:|
| Multitone | 2 | 3.85 – 3.87 | 3.88 |
| Music#1 | 2 | 2.57 – 2.67 | 2.58 |
| Music#2 | 2 | 2.57 – 2.67 | 2.58 |
| Speech#1 | 6 | 0.12 – 0.36 | 1.05 |
| Speech#2 | 8 | 0.12 – 0.36 | 1.24 |

#### Table 5. Whole recording vs its longest non-silent segment (shared bins)

| Signal | H of the whole file | Segment, s | H of the segment |
|---|:-:|:-:|:-:|
| DTMF_tones | 3.05 | 0.15 – 0.27 | 3.60 |
| Speech#1 | 1.05 | 3.16 – 3.64 | 2.52 |
| Speech#2 | 1.24 | 7.11 – 7.64 | 1.84 |

## Conclusions

**1. Signal type and entropy (a).** Histogram entropy measures how evenly the
sample values spread over their range. It says nothing about their order in
time: shuffling the samples of a sine leaves H unchanged (the self-test checks
this; `Sinus_500Hz` stays at 3.791 bits). So "periodic → low entropy, random →
high entropy" does
**not** hold for this measure. The ranking at L = 16 is:

- **uniform white noise 4.00 (the maximum)**
- multitone 3.88
- sines 3.79
- brown noise 3.74
- pure tones 3.29
- pink noise 3.21
- DTMF 3.05
- **Gaussian white noise 2.86**
- music 2.58
- speech 1.05–1.24
- square wave 1.00

- **Periodic** signals range from 1 to 3.9 bits, depending on the shape of the
  waveform:
  - A sine spends most of its time near its peaks (the arcsine law), yet still
    covers every bin, so it scores 0.95 of the maximum.
  - The frequency of the sine doesn't matter: every tone in `Pure_tones`, from
    250 Hz to 8 kHz, gives the same local H of ≈ 3.88.
  - A square wave takes only two values, so it gives exactly 1 bit for any L.
  - DTMF (a sum of two tones, with gaps) is lower, at 3.05.
- **Random** signals depend on their amplitude distribution:
  - Uniform noise fills every bin equally, so it gives exactly $\log_2 L$.
  - Gaussian noise crowds its values around zero, while its min–max range is
    set by rare extremes, so it scores only 0.71 of the maximum. That range
    grows with the signal's length, so H falls as the recording gets longer:
    3.25 for 0.1 s, 3.02 for 1 s and 2.86 for 5 s of the same noise.
  - Brown noise is a slow random walk. Over a minute it visits its whole range
    fairly evenly, so its global H is high (3.74).
- **Pseudo-periodic** signals are the lowest:
  - Music and speech have peaked, heavy-tailed distributions: many quiet
    samples and few loud peaks.
  - Speech also has long pauses. A single channel of `Speech#1` is ~90 % digital
    silence and has H = 0.12–0.36. The mix of all channels gives 1.05, and its
    active part alone (3.16–3.64 s) gives 2.52 (Tables 4, 5). The value for
    speech therefore depends heavily on which segment is analysed.

**2. Local entropy (b, c).**
- **Stationary signals** give a flat curve, with local H ≈ global H: sines at
  3.79 ± 0.00, uniform noise at 3.99 ± 0.00.
- **Sound and silence** separate sharply:
  - Speech, DTMF and the pure-tone sequence drop to ≈ 0 in pauses, because all
    values fall into the zero bin. The `Pure_tones` gaps sit at 0.49.
  - During sound they rise to 3–4 bits.
  - The local-entropy curve therefore segments the recording into sound and
    pauses, and could be used for voice-activity or endpoint detection. Like an
    energy envelope, it is bounded (0…$H_{max}$) and doesn't depend on the
    absolute level.
- **Std of local H** measures how much a signal changes:
  - ≤ 0.03 for steady tones and white noise;
  - 0.69 for music;
  - 1.0–1.7 for speech, DTMF and the tone sequence.
- **The distribution of local H** (bottom-right plot) makes this visible:
  - Speech is bimodal, with a large peak at 0 (72 % of `Speech#1` frames) and a
    spread of speech frames up to 3.8.
  - A sine is a single narrow line.

**3. Global vs mean local entropy.**
- With shared bins, the global histogram is almost exactly the average of the
  frame histograms. Entropy is concave, so the global H is at least the mean
  local H.
- The gap (last column of Table 1) works as a measure of non-stationarity:
  - ≈ 0 for sines, multitone, square and white noise;
  - 0.26 for pink noise and 0.45 for music;
  - 0.54–0.77 for speech, DTMF and the tone sequence;
  - 1.48 for brown noise, whose 20 ms frames each see only a narrow slice of
    the slowly wandering value range.
- With own-range bins the inequality doesn't hold. Each frame is binned more
  finely, so the mean local H can exceed the global H.

**4. Effect of the parameters.**
- **Number of bins L (Table 2).**
  - For continuous-valued signals, H grows by about 1 bit for every doubling of
    L (sine: 2.85 → 3.79 → 4.75 → 5.72). Absolute values are only comparable at
    the same L.
  - H / Hmax is much more stable (0.95 for a sine at every L).
  - Discrete signals don't grow: the square wave stays at 1 bit.
  - Speech grows slowly, because most of its samples stay in the central bin.
- **Frame length (Table 3).**
  - 20 vs 30 ms changes the mean local H by at most 0.23 bits (brown noise,
    because a longer frame sees more of the slow wander).
  - At 125 Hz a 20 ms frame holds only 2.5 periods, which causes a small
    ripple (std 0.01–0.03).
- **Bias of short frames.**
  - With N samples per frame, entropy is underestimated by about
    (L − 1) / (2N ln 2).
  - For uniform noise in 882-sample frames this is 0.012, matching the
    observed 4.000 vs 3.987.
  - A much larger L would need longer frames, so L = 10–16 suits 20–30 ms.
- **Bin range (Table 3).**
  - Own-range bins remove the level and keep only the shape. Music frames then
    look sine-like on average (3.76 ± 0.22), and quiet noise is inflated: the
    gaps in `Pure_tones` rise from 0.49 to 3.06 bits.
  - Shared bins keep frames comparable and show silence as ≈ 0, which is why
    they are the default.

**Summary.** Value-histogram entropy is a cheap, level-independent descriptor
of the amplitude distribution.
- It separates signals that use only a few levels (square wave), signals that
  stay near their peaks (sines, multitones), Gaussian-like noise, and peaked,
  impulsive signals (music, speech).
- Computed frame by frame, it detects sound and silence and measures how
  stationary a signal is.
- It doesn't capture temporal structure or predictability. Telling a sine from
  its own shuffled samples would need, for example, spectral entropy or
  permutation entropy.
