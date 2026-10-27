# Lab 3 — Audio Effects: Modulation

Task variant c) (_Moduliacijos efektas_). A desktop tool (PyQt6 + pyqtgraph)
that opens a `*.wav` file, plays it, and gives it a "waving" effect, where the
level keeps moving between silence and full volume:

$$
\tilde{s}[k] = m[k] \cdot s[k] ,
$$

where $m$ is a low-frequency modulating signal. Three modulating signals are
available (sine, triangle and square), with an adjustable rate and depth. The tool plots the original signal, $m(t)$ and the processed signal,
plays both, and saves the result in the source's format.

## Running

```bash
make setup      # uv sync (installs numpy, soundfile, PyQt6, pyqtgraph)
make run3       # launch the GUI  (uv run python src/3lab/main.py)
make report3    # print the result tables of this README (Markdown)
```

Open a file with **Open .wav…**. Sample files live in `data/Garsai1/`, and
lab 2's `make signals2` adds three generated signals in `data/Generated/`.

## Modules

| File                                       | Responsibility                                                                                                                                                    |
| ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `main.py`                                  | Entry point.                                                                                                                                                      |
| **`effects/`**                             | **The effect (numpy only, no Qt)**                                                                                                                                |
| `effects/modulation.py`                    | `Waveform` (sine, triangle, square), `modulator()` → m[k], `modulate()` → m · s on every channel, measured and expected level change.                             |
| **`audio/`**                               | **Signal model + WAV I/O (from labs 1 and 2)**                                                                                                                    |
| `audio/audio_signal.py`                    | `AudioSignal`: samples + metadata, real amplitude, channel names, `channel_samples()`. New: `with_amplitude()` stores processed values at the source's bit depth. |
| `audio/subtype.py`                         | `Subtype` enum of the WAV encodings the tool reads.                                                                                                               |
| `audio/wav_io.py`                          | `read_signal()` (lab 2) and `write_signal()` (lab 1's export, for the whole signal) with `soundfile`; a small RIFF walk handles extensible headers.               |
| **`ui/`**                                  | **PyQt6 / pyqtgraph interface**                                                                                                                                   |
| `ui/main_window.py`                        | Window: file dialogs, play / stop / save actions, modulating-signal settings, info bar.                                                                           |
| `ui/effect_view.py`                        | `EffectView`: original signal, m(t) and processed signal on three X-linked plots, with the envelope and a playback cursor.                                        |
| `ui/player.py`                             | `Player`: playback with Qt Multimedia; the processed signal plays from a temporary WAV.                                                                           |
| **`utils/`**                               | **Small pure helpers (from lab 1)**                                                                                                                               |
| `utils/time_unit.py`, `utils/timescale.py` | Adaptive time-axis unit and duration formatting.                                                                                                                  |
| **`scripts/`**                             | **Runnable dev tools (not imported by the app)**                                                                                                                  |
| `scripts/report.py`                        | The result tables below (`make report3`).                                                                                                                         |

As in labs 1 and 2, `ui` and `scripts` import from `effects`, `audio` and
`utils`; `effects` and `audio` never import Qt. Imports are absolute and
resolve because `src/3lab` is on `sys.path`.

## Method

- **Modulating signal.** The phase of sample $k$, in periods, is
  $\varphi_k = (k \cdot f_m / f_s) \bmod 1$. It is taken from the absolute
  sample index, so $m$ runs without a break over the whole recording. A
  unipolar shape $u(\varphi) \in [0, 1]$ starts at full level, $u(0) = 1$:

  | Modulating signal | $u(\varphi)$                                |
  | ----------------- | ------------------------------------------- |
  | Sine              | $\tfrac12 (1 + \cos 2\pi\varphi)$           |
  | Triangle          | $\lvert 1 - 2\varphi \rvert$                |
  | Square            | $1$ for $\varphi < \tfrac12$, otherwise $0$ |

- **Depth.** $m = 1 - d \, (1 - u)$, so $m$ swings between $1 - d$ and $1$. At
  the default $d = 100\,\%$ the level goes from silence to full volume, as the
  task asks. At $d = 0$ the signal is left unchanged.
- **Rate.** $f_m$ is 0.1–50 Hz (default 2 Hz). The range goes past the point
  where the level change stops sounding like "waving", so you can find that
  point.
- **The effect.** Every channel is multiplied by the same $m[k]$, on lab 1's
  real-amplitude scale (integer levels of the true bit depth). The result is
  rounded to the nearest quantization level. Since $0 \le m \le 1$,
  $|\tilde{s}| \le |s|$, so nothing can clip. The processed signal keeps the
  source's encoding, so it is saved bit-exactly in the same format (a 24-bit
  source stays 24-bit, float stays float). The file you play is the file you
  save.
- **Level change.** If the signal does not depend on $m$, its power is
  multiplied by $E[m^2] = 1 - d + d^2 E[u^2]$ (every shape has
  $E[u] = \tfrac12$). The level therefore changes by $10 \log_{10} E[m^2]$ dB.
  The info bar shows the measured RMS change of the shown channel next to this
  value.
- **Playback.** Qt Multimedia (`QMediaPlayer`) plays the source file directly
  and the processed signal from a temporary WAV. It downmixes 5.1 and 7.1
  files and resamples for the output device.
- **Low level.** The modulating signals are computed from their formulas, and
  the effect is a per-sample multiplication. numpy only does the array
  arithmetic, and no DSP library is used. `soundfile` only reads and writes
  the files, Qt Multimedia only plays them, and PyQt6 and pyqtgraph build the
  interface and the plots.

## How the task items are met

1. **File dialog, waveform, listening.** **Open .wav…** uses
   `QFileDialog.getOpenFileName` filtered to `*.wav`. The top plot shows the
   original signal, and **Play original** plays it.
2. **(c) Modulation effect.** The settings row below the plots chooses the
   modulating signal (sine, triangle or square), its rate and its
   depth. The window shows time diagrams of the original signal, the
   intermediate signal $m(t)$ and the processed signal, with the envelope
   $\pm\,\text{peak} \cdot m(t)$ drawn over the last one. The three plots zoom
   and pan together. For multi-channel files the plots show the mix or any
   single channel, and the effect is applied to every channel.
3. **Listening and saving.** **Play processed** plays the result while an
   orange cursor moves across all three plots. **Save processed…** saves it
   under a chosen name (`QFileDialog.getSaveFileName`) in the source's format.

## Results

All tables come from `make report3`. Levels are the RMS over all channels of a
recording.

#### Table 1. Modulating signals (100 % depth; step at 2 Hz, 44.1 kHz)

| Modulating signal |        u(φ)        | E[m²] | Level change | Largest step of m per sample | Sidebands at f₀ ± n·f_m |
| ----------------- | :----------------: | :---: | :----------: | :--------------------------: | :---------------------: |
| Sine              |   ½(1 + cos 2πφ)   | 0.375 |   -4.26 dB   |           0.00014            |        n = 1 only       |
| Triangle          |     \|1 − 2φ\|     | 0.333 |   -4.77 dB   |           9.1e-05            |      odd n, ∝ 1/n²      |
| Square            | 1 if φ < ½, else 0 | 0.500 |   -3.01 dB   |              1               |       odd n, ∝ 1/n      |

#### Table 2. Measured RMS level change, dB (2 Hz, 100 % depth)

| Signal               | Channels |  Sine | Triangle | Square |
| -------------------- | :------: | :---: | :------: | :----: |
| **Expected**         |          | -4.26 |  -4.77   | -3.01  |
| Brown_noise          |    1     | -4.23 |  -4.73   | -2.97  |
| DTMF_tones           |    1     | -4.31 |  -4.80   | -2.80  |
| Multitone            |    2     | -4.57 |  -5.05   | -2.55  |
| Music#1              |    2     | -3.33 |  -3.98   | -2.62  |
| Music#2              |    2     | -3.33 |  -3.98   | -2.62  |
| Pink_noise           |    1     | -3.81 |  -4.29   | -3.05  |
| Pure_tones           |    1     | -4.26 |  -4.77   | -3.01  |
| Sinus_125Hz          |    1     | -4.26 |  -4.77   | -3.01  |
| Sinus_500Hz          |    1     | -4.26 |  -4.77   | -3.01  |
| Speech#1             |    6     | -5.55 |  -5.91   | -9.29  |
| Speech#2             |    8     | -5.82 |  -6.12   | -9.76  |
| Square_440Hz         |    1     | -4.26 |  -4.77   | -3.01  |
| White_noise_gaussian |    1     | -4.25 |  -4.76   | -3.01  |
| White_noise_uniform  |    1     | -4.27 |  -4.78   | -2.99  |

#### Table 3. Expected level change, dB, by depth

| Modulating signal |  25%  |  50%  |  75%  |  100% |
| ----------------- | :---: | :---: | :---: | :---: |
| Sine              | -1.12 | -2.26 | -3.36 | -4.26 |
| Triangle          | -1.13 | -2.34 | -3.59 | -4.77 |
| Square            | -1.07 | -2.04 | -2.75 | -3.01 |

#### Table 4. Measured RMS level change, dB, by rate (100 % depth)

| Signal     | Modulating signal | 0.5 Hz |  1 Hz  |  2 Hz |  5 Hz | 10 Hz | 20 Hz | 40 Hz |
| ---------- | :---------------: | :----: | :----: | :---: | :---: | :---: | :---: | :---: |
| Speech#1   |        Sine       | -5.21  | -11.20 | -5.55 | -4.57 | -3.51 | -4.11 | -4.23 |
| Speech#1   |       Square      | -3.42  | -0.29  | -9.29 | -3.24 | -3.36 | -3.25 | -2.99 |
| Music#1    |        Sine       | -4.57  | -5.17  | -3.33 | -4.07 | -4.33 | -4.32 | -4.42 |
| Music#1    |       Square      | -3.30  | -3.32  | -2.62 | -3.16 | -2.79 | -2.95 | -2.95 |
| DTMF_tones |        Sine       | -4.16  | -4.32  | -4.31 | -4.26 | -4.28 | -4.28 | -4.27 |
| DTMF_tones |       Square      | -2.23  | -2.95  | -2.80 | -2.77 | -3.01 | -3.00 | -3.02 |

## Listening notes

_Fill in after listening with **Play processed** (100 % depth unless noted).
Try at least `Sinus_500Hz`, `Music#1` and `Speech#1`._

| Modulating signal | 0.5 Hz | 2 Hz | 5 Hz | 10 Hz | 20 Hz | 40 Hz |
| ----------------- | ------ | ---- | ---- | ----- | ----- | ----- |
| Sine              |        |      |      |       |       |       |
| Triangle          |        |      |      |       |       |       |
| Square            |        |      |      |       |       |       |

- The rate at which the "waving" stops sounding like level movement and turns
  into roughness or a buzz: …
- The smoothest or most natural modulating signal, and the most striking one: …
- Where the clicks of the square signal are most audible, and on which
  recordings: …
- The effect of a smaller depth (e.g. 50 %): …

## Conclusions

**1. Level (Tables 2, 3).** Multiplying by $m \le 1$ always makes the sound
quieter. On average the loss is $10 \log_{10} E[m^2]$: −4.26 dB for the sine,
−4.77 dB for the triangle and −3.01 dB for the square. The square loses least
because it spends half of every period at full level.

- Recordings whose loudness is constant and that last many periods match
  theory to within 0.02 dB. These are the sines, `Square_440Hz`, `Pure_tones`
  and both white noises.
- The two shortest recordings cover only 2–3 periods at 2 Hz: `Multitone`
  (1.35 s) and `Pink_noise` (1.04 s). Their own level variations and the
  incomplete last period therefore shift the result by up to 0.5 dB.
- At 50 % depth every modulating signal costs about 2 dB.

**2. Smoothness and clicks (Table 1).**

- At 2 Hz and 44.1 kHz, the sine and triangle change $m$ by at most
  1.4·10⁻⁴ and 9.1·10⁻⁵ of full scale per sample. The gain therefore moves
  smoothly.
- The square jumps between silence and full level from one sample to the
  next (step 1). This makes the processed waveform discontinuous, unless the
  signal happens to be near zero at that moment, and such a discontinuity is
  heard as a click.
- The square has two such jumps per period (cut and restart).

**3. Spectrum (Table 1).** Multiplying by $m$ is amplitude modulation. A tone
$f_0$ is replaced by the tone plus sidebands at $f_0 \pm n f_m$, weighted by
the Fourier coefficients of $u$:

- the sine adds only $f_0 \pm f_m$;
- the triangle adds odd $n$, falling as $1/n^2$, so it is spectrally almost
  as clean as the sine;
- the square adds odd $n$, falling only as $1/n$.

The square therefore spreads the most energy away from the original
components. The faster the rate, the further from $f_0$ that energy
lands.

**4. Uneven recordings depend on the phase (Tables 2, 4).**

- For speech and music the level change depends on where the loud parts fall
  within the period of $m$. With the square signal, `Speech#1` loses only
  0.29 dB at 1 Hz, because its words fall in the "on" halves, but 9.29 dB at
  2 Hz, where they fall in the "off" halves.
- At slow rates, the square signal can therefore keep or mute whole words. At
  2 Hz the loud moments of `Music#1` happen to coincide with high values of
  $m$, so it loses less than expected (3.33 dB with the sine instead of
  4.26 dB).
- The deviations shrink as the rate grows, because each sound then spans
  more periods of $m$. From 20 Hz on, every recording in Table 4 is within
  0.25 dB of the expected value. `DTMF_tones`, whose tones are short, is
  within 0.02 dB from 5 Hz on with the sine.
- `Music#1` and `Music#2` (the same music at 48 and 96 kHz) give identical
  numbers. The effect does not depend on the sample rate.

**Summary.** All three modulating signals produce the required waving between
silence and full volume.

- The sine and triangle do it smoothly. The triangle's linear ramps spend
  less time near full level, so it loses 0.5 dB more.
- The square cuts the sound on and off. It keeps the most level but clicks
  twice per period.
- What the effect does to a recording depends on the rate relative to the
  length of its sounds. At slow rates $m$ can keep or mute whole words; at
  fast rates every sound spans many periods and is modulated evenly.
