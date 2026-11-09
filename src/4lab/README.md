# Lab 4 — Spectrum Analysis of Audio Signals

Task _Spektro garso signalų analizė_. A desktop tool (PyQt6 + pyqtgraph) that
opens a `*.wav` file and computes the short-time spectrum of a selected
segment, as defined in the lecture slides (slide 14):

$$
X(k) = \sum_{n=0}^{N-1} x(n) \cdot l(n) \cdot e^{-j 2\pi n k / N},
\qquad 0 \le k \le N-1,
$$

where $x(n)$ is the segment of $N$ samples and $l(n)$ is the window function.
The tool shows the two spectrum variants the task asks for in one diagram:

- the **amplitude spectrum** $|X(k)|$ (slide 14);
- the **spectral density function** (periodogram)
  $S(k) = X(k) \cdot X^*(k) = |X(k)|^2$ (slides 24–25). It shows how the
  energy of the segment is distributed over frequency.

## Running

```bash
make setup      # uv sync (installs numpy, soundfile, PyQt6, pyqtgraph)
make run4       # launch the GUI  (uv run python src/4lab/main.py)
make report4    # print the result tables of this README (Markdown)
```

Open a file with **Open .wav…**. Sample files live in `data/Garsai1/`, and
lab 2's `make signals2` adds three generated signals in `data/Generated/`.

## Modules

| File                                       | Responsibility                                                                                                                                                       |
| ------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `main.py`                                  | Entry point.                                                                                                                                                         |
| **`analysis/`**                            | **Spectrum analysis (numpy only, no Qt)**                                                                                                                            |
| `analysis/spectrum.py`                     | `Window` (rectangular, Hanning, Hamming, Blackman) and `window()` → l(n); `spectrum()` → `Spectrum` (frequencies, \|X\|, S, Δf); `loudest_start()` for the default segment. |
| **`audio/`**                               | **Signal model + WAV reading (from lab 3)**                                                                                                                          |
| `audio/audio_signal.py`                    | `AudioSignal`: samples + metadata, real amplitude, channel names, `channel_samples()` (the mix of all channels).                                                    |
| `audio/subtype.py`                         | `Subtype` enum of the WAV encodings the tool reads.                                                                                                                  |
| `audio/wav_io.py`                          | `read_signal()` with `soundfile`; a small RIFF walk reads the valid bits and channel mask of extensible headers.                                                     |
| **`ui/`**                                  | **PyQt6 / pyqtgraph interface**                                                                                                                                      |
| `ui/main_window.py`                        | Window: file dialog, window function, segment start and length, info bar.                                                                                            |
| `ui/spectrum_view.py`                      | `SpectrumView`: the signal with the draggable segment, the segment, and its spectrum (\|X\| and S together).                                                         |
| **`utils/`**                               | **Small pure helpers (from lab 1)**                                                                                                                                  |
| `utils/time_unit.py`, `utils/timescale.py` | Adaptive time-axis unit and duration formatting.                                                                                                                     |
| **`scripts/`**                             | **Runnable dev tools (not imported by the app)**                                                                                                                     |
| `scripts/report.py`                        | The result tables below (`make report4`).                                                                                                                            |

As in the earlier labs, `ui` and `scripts` import from `analysis`, `audio`
and `utils`; `analysis` and `audio` never import Qt. Imports are absolute and
resolve because `src/4lab` is on `sys.path`.

## Method

- **Segment.** $N$ consecutive samples of the recording. Multi-channel files
  are analysed as their mix (the mean of the channels), as in lab 3. The
  segment is chosen by dragging the orange region (or its edges) on the signal
  plot, or by typing its start (s) and length (ms). When a file is opened, a
  30 ms segment (slide 8: speech is analysed in 15–30 ms frames) is placed on
  the loudest part of the recording.
- **Window functions** (slides 11–12). The segment is multiplied by $l(n)$,
  which tapers its ends to zero, so the DFT does not see a jump where the
  segment is cut out. Three windows and the rectangular one (no window), in
  the symmetric form of numpy's `hanning`, `hamming` and `blackman`,
  $n = 0 \dots N-1$:

  | Window                  | $l(n)$                                                                 |
  | ----------------------- | ---------------------------------------------------------------------- |
  | Rectangular (no window) | $1$                                                                    |
  | Hanning                 | $0.5 - 0.5 \cos\frac{2\pi n}{N-1}$                                     |
  | Hamming                 | $0.54 - 0.46 \cos\frac{2\pi n}{N-1}$                                   |
  | Blackman                | $0.42 - 0.5 \cos\frac{2\pi n}{N-1} + 0.08 \cos\frac{4\pi n}{N-1}$      |

- **DFT.** The sum above is computed with the FFT (`numpy.fft.rfft`; the
  slides allow "DFT arba FFT"), which gives the same $X(k)$ in
  $O(N \log N)$ operations. For a real signal $|X(N-k)| = |X(k)|$, so only
  $k = 0 \dots N/2$ are shown, at the frequencies $f_k = k \cdot f_s / N$ from 0
  to $f_s/2$.
- **Frequency resolution.** Neighbouring values are $\Delta f = f_s / N = 1/T$
  apart, where $T$ is the segment's duration. It depends only on the duration:
  30 ms gives 33.3 Hz at any sample rate.
- **Both spectra in one diagram.** $|X|$ and $S$ have different units, so each
  is divided by its own maximum, the way the slides plot the periodogram
  (slide 26, maximum = 1). On this scale $S_{rel} = |X|_{rel}^2$. In decibels
  the two would be the same curve ($10 \lg S = 20 \lg |X|$), so the diagram is
  linear. Zooming (mouse wheel or right-drag) shows the small values, and the
  status bar shows f, |X| and S under the mouse.
- **Low level.** The windows, the spectra and the measurements are computed
  from their formulas with numpy arrays; only the FFT itself is numpy's.
  `soundfile` only reads the files, and PyQt6 and pyqtgraph build the
  interface and the plots.

## How the task items are met

1. **Selecting and reading a `*.wav` file.** **Open .wav…** uses
   `QFileDialog.getOpenFileName` filtered to `*.wav`. `read_signal()` reads
   8-, 16-, 24- and 32-bit PCM and float files, from mono to 7.1.
2. **Spectrum analysis of the selected segment.** For the segment chosen on
   the signal plot, the tool computes (a) the amplitude spectrum $|X(k)|$ and
   (b) the spectral density $S(k) = |X(k)|^2$, with the window chosen in the
   **Window** box.
3. **Diagrams**, from top to bottom:
   - (a) the time diagram of the whole signal, with the orange segment;
   - (b) the time diagram of the segment: $x(n)$ in blue, and the windowed
     $x(n) \cdot l(n)$ that the DFT is computed from in orange (as on slides 13
     and 15);
   - (c) the spectrum diagram with both variants: $|X|$ in blue and $S$ in
     red. Its title gives the window, $N$ and $\Delta f$.

For the analysis, the **Window** box changes the window (item 3), the
**Length** box or the region's edges change the segment length (item 2), and
the **Segment start** arrows move the segment in 1 ms steps (item 4; any
start can be typed, to 0.1 ms).

## Results

The recordings, grouped by origin:

- **Voice:** `Speech#1` (5.1) and `Speech#2` (7.1), the same utterances.
- **Music (instruments):** `Music#1` (48 kHz) and `Music#2` (96 kHz), the same
  music.
- **Technical signals:** `DTMF_tones` (telephone dialling tones), `Multitone`
  (a test signal: lines every 10 Hz at 290–590 Hz and 950–2780 Hz),
  `Pure_tones` (octave test tones, 250 Hz – 8 kHz), `Sinus_125Hz`,
  `Sinus_500Hz`.
- **Generated** (lab 2): `Square_440Hz`, `White_noise_uniform`,
  `White_noise_gaussian`.
- **Noises:** `Pink_noise`, `Brown_noise` and the two white noises.

There is no nature recording in `data/`. Any `.wav` file added there appears
in Tables 1 and 6 after `make report4`.

All tables come from `make report4`. Unless a table says otherwise, the
segment starts where the loudest 100 ms of the recording begins, the window
is Hanning, and the values are relative to the largest one, as in the tool.
A **peak** is a value of at least 10 % of the largest one that is also the
largest within the window's main lobe: ±1 bin for the rectangular window, ±2
for Hanning and Hamming, ±3 for Blackman. Multitone lines are counted as peaks
within ±1 bin in 290–590 Hz.

#### Table 1. Frequency content (loudest 100 ms, Δf = 10 Hz, Hanning window)

| Signal               |      Origin     | Start, s |           Dominant frequencies, Hz (relative \|X\|)            | Highest f with \|X\| ≥ 1 %, Hz | … ≥ 0.1 %, Hz |
| -------------------- | :-------------: | :------: | :------------------------------------------------------------: | :----------------------------: | :-----------: |
| Brown_noise          |      noise      |  33.28   |                            0 (1.00)                            |              470               |      6670     |
| DTMF_tones           | telephone tones |   2.24   |                    700 (1.00), 1340 (0.96)                     |              1360              |      1420     |
| Multitone            |   test signal   |   0.46   |                     none (27 peaks ≥ 10 %)                     |              2780              |      2820     |
| Music#1              |      music      |  25.50   |               60 (1.00), 120 (0.47), 290 (0.18)                |              880               |      3850     |
| Music#2              |      music      |  25.50   |               60 (1.00), 120 (0.47), 290 (0.18)                |              880               |      3850     |
| Pink_noise           |      noise      |   0.46   |     0 (1.00), 40 (0.41), 190 (0.24), 310 (0.21), 90 (0.17)     |             16000              |     16000     |
| Pure_tones           |    test tones   |  30.01   |                          8000 (1.00)                           |              8010              |      8010     |
| Sinus_125Hz          |    test tone    |   3.13   |                           120 (1.00)                           |              150               |      190      |
| Sinus_500Hz          |    test tone    |   5.74   |                           500 (1.00)                           |              510               |      510      |
| Speech#1             |      voice      |   2.26   |               150 (1.00), 310 (0.95), 460 (0.26)               |              3340              |      8090     |
| Speech#2             |      voice      |   2.26   |               150 (1.00), 310 (0.95), 460 (0.26)               |              3340              |      8090     |
| Square_440Hz         |    generated    |   0.00   | 440 (1.00), 1320 (0.33), 2200 (0.20), 3080 (0.14), 3960 (0.11) |             21670              |     22040     |
| White_noise_gaussian |      noise      |   1.79   |                    none (406 peaks ≥ 10 %)                     |             22050              |     22050     |
| White_noise_uniform  |      noise      |   4.28   |                    none (406 peaks ≥ 10 %)                     |             22050              |     22050     |

#### Table 2. Noises: spectral density at 100–200 Hz vs 1–2 kHz (whole file, up to 10 s)

| Signal               | Drop per decade, dB | S ∝ f^α, α | Slides: α |
| -------------------- | :-----------------: | :--------: | :-------: |
| White_noise_uniform  |         -0.2        |    0.02    |  0 (flat) |
| White_noise_gaussian |         0.0         |    0.00    |  0 (flat) |
| Pink_noise           |         10.4        |   -1.04    |  −1 (1/f) |
| Brown_noise          |         19.9        |   -1.99    | −2 (1/f²) |

#### Table 3. Segment length T (Hanning window)

| T, ms | Δf = 1/T, Hz | Sinus_125Hz: peak at, Hz | Multitone: lines seen in 290–590 Hz (of 23) | DTMF_tones from a tone onset: peaks ≥ 10 % | Speech#1: peaks ≥ 10 % (lowest, Hz) |
| ----- | :----------: | :----------------------: | :-----------------------------------------: | :----------------------------------------: | :---------------------------------: |
| 10    |     100      |          100.2           |                      1                      |                     2                      |               1 (200)               |
| 20    |      50      |          100.0           |                      1                      |                     2                      |               2 (150)               |
| 30    |     33.3     |          133.2           |                      1                      |                     2                      |               4 (167)               |
| 50    |      20      |          120.1           |                      1                      |                     2                      |               3 (160)               |
| 100   |      10      |          120.0           |                      7                      |                     2                      |               3 (150)               |
| 200   |      5       |          125.0           |                      15                     |                     3                      |               3 (145)               |
| 300   |     3.33     |          123.3           |                      23                     |                     7                      |               10 (143)              |
| 500   |      2       |          124.0           |                      23                     |                     10                     |               24 (138)              |
| 1000  |      1       |          125.0           |                      23                     |                     16                     |               36 (138)              |

#### Table 4. Window functions

| Window                  | Main lobe at −3 dB, bins | Main lobe to first zero, ± bins | Highest side lobe, dB | Coherent gain Σl/N | Multitone, 200 ms: lines seen (of 23) | Sinus_500Hz, 30 ms: leakage > 10 Δf from the peak, dB |
| ----------------------- | :----------------------: | :-----------------------------: | :-------------------: | :----------------: | :-----------------------------------: | :---------------------------------------------------: |
| Rectangular (no window) |           0.91           |               1.00              |         -13.3         |        1.00        |                   23                  |                         -57.0                         |
| Hanning                 |           1.47           |               2.00              |         -31.5         |        0.50        |                   15                  |                         -93.7                         |
| Hamming                 |           1.31           |               2.00              |         -42.7         |        0.54        |                   18                  |                         -73.3                         |
| Blackman                |           1.66           |               3.00              |         -58.1         |        0.42        |                   13                  |                         -102.2                        |

#### Table 5. Change of the amplitude spectrum when a 30 ms segment is moved, ‖ΔX‖ / ‖X‖, %

| Signal               | 1 sample: Rect. | 1 sample: Hanning | 1 ms: Rect. | 1 ms: Hanning | 5 ms: Rect. | 5 ms: Hanning |
| -------------------- | :-------------: | :---------------: | :---------: | :-----------: | :---------: | :-----------: |
| Sinus_500Hz          |       0.1       |        0.0        |     0.0     |      0.0      |     0.0     |      0.0      |
| Square_440Hz         |       0.0       |        0.0        |     9.4     |      0.8      |     8.3     |      3.7      |
| DTMF_tones           |       0.3       |        0.1        |     3.4     |      1.2      |     17.2    |      2.5      |
| Speech#1             |       0.3       |        0.1        |     6.4     |      3.3      |     18.9    |      13.0     |
| Music#1              |       0.6       |        0.1        |     16.5    |      6.6      |     31.4    |      36.2     |
| White_noise_gaussian |       3.7       |        0.2        |     15.7    |      8.1      |     36.0    |      35.5     |

#### Table 6. Amplitude spectrum |X| vs spectral density S = |X|² (loudest 100 ms, Hanning window)

| Signal               | Peaks ≥ 10 %: \|X\| | Peaks ≥ 10 %: S | Highest f ≥ 1 %: \|X\|, Hz | Highest f ≥ 1 %: S, Hz | Centroid of \|X\|, Hz | Centroid of S, Hz |
| -------------------- | :-----------------: | :-------------: | :------------------------: | :--------------------: | :-------------------: | :---------------: |
| Brown_noise          |          1          |        1        |            470             |           10           |          2316         |         6         |
| DTMF_tones           |          2          |        2        |            1360            |          1350          |          1020         |        1016       |
| Multitone            |          27         |        15       |            2780            |          2740          |          1577         |        1418       |
| Music#1              |          3          |        2        |            880             |          300           |          490          |         81        |
| Music#2              |          3          |        2        |            880             |          300           |          490          |         81        |
| Pink_noise           |          8          |        2        |           16000            |          470           |          4892         |        976        |
| Pure_tones           |          1          |        1        |            8010            |          8010          |          8019         |        8000       |
| Sinus_125Hz          |          1          |        1        |            150             |          140           |          128          |        125        |
| Sinus_500Hz          |          1          |        1        |            510             |          510           |          503          |        500        |
| Speech#1             |          3          |        2        |            3340            |          480           |          1278         |        293        |
| Speech#2             |          3          |        2        |            3340            |          480           |          1278         |        293        |
| Square_440Hz         |          5          |        2        |           21670            |          3960          |          7140         |        1022       |
| White_noise_gaussian |         406         |       363       |           22050            |         22050          |         10900         |       10880       |
| White_noise_uniform  |         406         |       361       |           22050            |         22050          |         11131         |       11205       |

## Conclusions

**1. Frequency content (Tables 1, 2).**

- **Test tones** give a single line: `Sinus_500Hz` at 500 Hz, `Pure_tones`
  at 8 kHz (its loudest tone). Nothing else reaches 0.1 % of the line, so the
  highest observed frequency is the tone itself. `Sinus_125Hz` appears at
  120 Hz, because a 100 ms segment has values only every 10 Hz (item 2).
- **The square wave** has a periodic line spectrum: only the odd harmonics of
  440 Hz (440, 1320, 2200, 3080, 3960 Hz), with relative amplitudes 1, 0.33,
  0.20, 0.14, 0.11 = 1/n, as the Fourier series of a square wave predicts. Its
  sharp edges make the harmonics fall slowly, so the spectrum reaches 21.7 kHz
  at 1 % (harmonics above $f_s/2$ fold back into the band).
- **DTMF** gives two lines that are not harmonics of each other: 700 and
  1340 Hz, i.e. 697 + 1336 Hz, the digit "2" (one tone from the low group and
  one from the high group). There is nothing above 1.42 kHz: a narrow-band
  technical signal.
- **The voice** is a harmonic series: 150, 310 and 460 Hz are the
  fundamental $f_0 \approx 150$ Hz and its 2nd and 3rd harmonics. The lines
  repeat every $f_0$, so their spacing is the pitch. Weaker components
  (formants, fricatives) reach 3.3 kHz at 1 % and 8.1 kHz at 0.1 %.
- **Music** is dominated by the bass: 60 Hz, its 2nd harmonic at 120 Hz, and
  290 Hz. Above 880 Hz everything is below 1 % of the bass, and above 3.85 kHz
  below 0.1 %. `Music#2` (96 kHz) gives the same numbers as `Music#1`
  (48 kHz): the extra range up to 48 kHz adds nothing above 0.1 %.
- **Multitone** has no single dominant line. At 100 ms its lines, 10 Hz
  apart, merge into 27 broad peaks; they separate only in longer segments
  (Table 3).
- **Noises** have no dominant frequencies.
  - White noise has 406 random peaks spread up to $f_s/2$: a flat, continuous
    spectrum.
  - Pink and brown noise are strongest at the lowest frequencies (the 0 Hz
    bin).
  - Table 2 measures the slopes. The spectral density falls by 0 dB (white),
    10.4 dB (pink) and 19.9 dB (brown) per decade, i.e. $S \propto f^0$,
    $f^{-1.04}$ and $f^{-1.99}$: the white, $1/F$ and $1/F^2$ noises of
    slide 29.
- **The highest observed frequency** depends on how weak a component still
  counts. At 1 % and 0.1 % of the maximum (40 and 60 dB below it) it is
  470 Hz and 6.7 kHz for brown noise, and 3.3 and 8.1 kHz for speech.
- **By origin:**
  - synthetic and technical signals consist of a few exact lines: one tone, a
    harmonic series, or a non-harmonic pair;
  - the voice is a harmonic series whose $f_0$ changes over time;
  - music combines several harmonic series (notes) over a strong bass;
  - noise has no lines, only a continuous spectrum with a characteristic
    slope.

**2. Segment length (Table 3).**

- **Resolution.** $\Delta f = f_s/N = 1/T$ depends only on the segment's
  duration: 100 Hz for 10 ms, 1 Hz for 1 s.
- **Frequency accuracy.** A line is shown at the nearest available frequency,
  so its frequency is known only to $\pm\Delta f/2$. The 125 Hz sine appears
  at 100, 133 or 120 Hz in segments up to 100 ms, and exactly at 125 Hz only
  when 125 is a multiple of $\Delta f$ (200 ms, 1 s).
- **Separating close lines.** With the Hanning window, two lines separate only
  when they are about $3\Delta f$ apart.
  - `Multitone`'s lines, 10 Hz apart, form one lump up to 50 ms. 7 of the 23
    lines are seen at 100 ms (1 bin apart), 15 at 200 ms (2 bins), and all 23
    from 300 ms (3 bins).
  - Speech harmonics, 150 Hz apart, need $\Delta f$ of about 50 Hz. A 10 ms
    segment shows one broad peak, the envelope of the harmonics; from 20 ms on
    the harmonics are separate.
- **Longer is not always better.** A long segment averages everything that
  happens inside it.
  - DTMF: up to 100 ms (the length of one tone) the segment shows the digit's
    two tones. At 200 ms it also covers the pause and the start of the next
    digit, and a third peak appears. At 300 ms – 1 s it shows 7–16 peaks: the
    tones of several digits (e.g. 1209 Hz of the next one), plus side peaks
    caused by switching the tones on and off.
  - Speech: the analysed word lasts from 2.18 to 2.49 s, and its pitch falls
    towards the end. As the segment grows, the lowest peak moves from 167 Hz
    (30 ms) to 138 Hz (1 s), and from 300 ms on each harmonic smears into
    several peaks (10–36 in total).
- **So** a segment should be as short as the signal's changes require, but
  long enough for the needed resolution. 20–30 ms suits speech (slide 8): at
  30 ms, $\Delta f = 33$ Hz separates the harmonics of $f_0 \gtrsim 100$ Hz.
  Close lines of a stationary signal need hundreds of milliseconds.

**3. Window functions (Table 4).**

- **Why a window.** Cutting a segment out of a signal is itself a rectangular
  window: the segment starts and ends with a jump. In the spectrum, every line
  then becomes a copy of the window's own spectrum, a main lobe plus side
  lobes (leakage). The windows taper the ends to zero (the orange curve in the
  segment plot) and trade a wider main lobe for lower side lobes:

  | Window      | Main lobe | Highest side lobe |
  | ----------- | :-------: | :---------------: |
  | Rectangular |  ±1 bin   |     −13.3 dB      |
  | Hanning     |  ±2 bins  |     −31.5 dB      |
  | Hamming     |  ±2 bins  |     −42.7 dB      |
  | Blackman    |  ±3 bins  |     −58.1 dB      |

- **Resolution follows the main lobe.** At 200 ms (lines 2 bins apart) the
  rectangular window separates all 23 `Multitone` lines, Hamming 18, Hanning 15
  and Blackman 13.
- **Leakage follows the side lobes.** 10 Δf away from the 500 Hz line, the
  rectangular window still leaks at −57 dB, Hamming at −73 dB, Hanning at
  −94 dB and Blackman at −102 dB.
  - Hamming has the lower first side lobe of the two cosine windows, but it
    does not reach zero at the ends, so its far side lobes fall slowly. Far
    from a line, Hanning is cleaner.
  - In the tool this is easy to see on `Square_440Hz`. With the rectangular
    window every harmonic has a wide skirt and the gaps between the harmonics
    are filled (slide 15, "be lango funkcijos"). With Hanning the lines are
    clean.
- **Amplitude.** A window also lowers $|X|$ by its coherent gain $\sum l / N$:
  0.50 for Hanning, 0.54 for Hamming and 0.42 for Blackman (on slide 15, the
  peak drops from about 1070 to about 570). The tool divides by the maximum,
  so it compares only relative values.
- **Choice.**
  - Hanning (the default) or Hamming for general analysis.
  - The rectangular window to separate very close lines of similar level.
  - Blackman to see weak components next to strong ones.

**4. Segment boundaries (Table 5).**

- **A pure sine does not change** (at most 0.1 % for any shift and window).
  Moving the segment only changes the sine's phase, which affects the phase
  spectrum, not $|X|$.
- **Even one sample matters with the rectangular window.** It changes the
  spectrum by up to 3.7 % (white noise), because the sample that leaves at one
  end and the one that enters at the other have full weight. A tapered window
  gives them almost no weight: 0.2 % at most.
- **Several components and the rectangular window.**
  - A 1 ms shift changes the square wave's spectrum by 9.4 % with the
    rectangular window, but only 0.8 % with Hanning.
  - The leakage tails of the components overlap and add up with phases that
    depend on where the segment starts, so the pattern between the lines
    changes. Hanning's side lobes are 18 dB lower next to a line and about
    37 dB lower 10 Δf away (Table 4), so its tails hardly overlap.
  - The change is not proportional to the shift. It rises and falls as the
    shift changes the components' phases relative to each other. For the DTMF
    digit it is 3.4 % at 1 ms and 17 % at 5 ms with the rectangular window,
    against 1.2 % and 2.5 % with Hanning.
- **Non-stationary signals change because their content changes.** A 5 ms
  shift (1/6 of the segment) changes speech by 13–19 %, music by 31–36 % and
  noise by 36 %, with either window. Noise changes most, because each
  segment's periodogram is a random estimate.
- **So** a tapered window makes the spectrum robust to small changes of the
  bounds. With the rectangular window, the result depends on exactly where the
  segment is cut.

**5. Amplitude spectrum vs spectral density (Table 6).**

- **Similarities.**
  - Both come from the same DFT, $S = |X|^2$. The peaks are at the same
    frequencies, with the same resolution and the same effect of the window.
  - On a dB scale they are the same curve ($10 \lg S = 20 \lg |X|$).
  - For single tones (sines, pure tones, DTMF) the numbers barely differ.
- **Differences.** Squaring emphasises strong components and suppresses weak
  ones: a component at 30 % of the maximum in $|X|$ is at 9 % in $S$.
  - Peaks ≥ 10 %: the square wave shows 5 harmonics in $|X|$ ($1/n$) but 2
    in $S$ ($1/n^2$); speech 3 vs 2, pink noise 8 vs 2, `Multitone` 27 vs 15.
  - The highest frequency at ≥ 1 % falls: speech 3.3 kHz → 480 Hz, square
    wave 21.7 → 4.0 kHz, pink noise 16 → 0.47 kHz.
  - The centroid (the spectrum's centre of gravity) moves towards the strong
    low frequencies: speech 1278 → 293 Hz, music 490 → 81 Hz, brown noise
    2316 → 6 Hz.
- **Use.**
  - $|X|$ shows the amplitudes of the sinusoidal components (e.g. harmonics as
    $1/n$). Weak components and the full extent of the spectrum, up to the
    highest frequency, are easier to see in it.
  - $S$ shows how the energy is distributed over frequency (slide 25). Its
    centroid ranks the recordings from low-frequency (brown noise 6 Hz, music
    81 Hz, speech 293 Hz) to broadband (white noise ≈ 11 kHz), the
    classification of slides 27–28, and its slope gives the colour of a noise
    (Table 2, slide 29).

**Summary.**

- The tool computes the short-time spectrum of any segment of a recording and
  shows the amplitude spectrum and the spectral density together. The window,
  the length and the position of the segment are the three choices that shape
  the result.
- Sounds of different origin differ clearly:
  - technical and test signals are a few exact lines;
  - voice and music are harmonic series whose spacing is the pitch, and music
    has a strong bass;
  - noises are continuous spectra with a slope of 0, −1 or −2.
- The length sets the resolution ($\Delta f = 1/T$), but it must not exceed the
  time during which the signal stays the same.
- The window trades resolution for less leakage and for robustness to the
  exact segment bounds.
- $|X|$ is the better choice for reading the amplitudes of components and for
  seeing weak ones; $S$ for the distribution of energy over frequency.
