# Architecture

## Overview (Hexagonal, pragmatic)

**Inside the hexagon** (no I/O): AppState, ComposeCommands, chords, phrase, waveform, file_input, mix
**Outside the hexagon** (I/O): Textual UI, sounddevice, librosa, pretty_midi

AppState.snapshot() is the read contract. AppState.update() is the write contract. No formal port interfaces — AppState IS the port.

```
Audio callback (sounddevice) → Queue(maxsize=64) → AudioAnalyzer thread
AudioAnalyzer → AppState.update() + AppState.add_chord() (COMPOSE mode only)
Textual MainScreen → AppState.snapshot() → widgets @ 20fps via set_interval
MainScreen.BINDINGS → ComposeCommands / AppState methods
```

---

## File map

```
riff/
├── main.py                   ← Entry point: launches RiffApp
├── core/
│   ├── state.py              ← AppState: thread-safe shared state, MODES, TIMBRES
│   └── commands.py           ← ComposeCommands: application logic (load, generate, save, play)
├── audio/
│   ├── capture.py            ← AudioCapture: sounddevice InputStream
│   ├── analyzer.py           ← AudioAnalyzer: pitch (pyin), BPM, dB, chords
│   ├── song.py               ← SongData, SongNote, SongPlayer, SongTracker
│   ├── chords.py             ← Chord dataclass, parse_progression(), detect_chord()
│   ├── midi_feeder.py        ← MidiFeeder: feeds loaded MIDI into YOU panel
│   └── mix.py                ← mix_audio(), save_wav()
├── ai/
│   ├── engine.py             ← MelodyEngine protocol + plug & play registry
│   ├── phrase.py             ← PhraseEngine: phrase-based melody generation
│   └── generate.py           ← generate_song(): progression string → SongData
├── ui/
│   ├── app.py                ← RiffApp(textual.App): owns state + commands, screen transitions
│   ├── palette.py            ← Shared color constants, LOGO, note_color()
│   ├── waveform.py           ← Pure ASCII waveform rendering functions
│   ├── file_input.py         ← InputBuffer, complete_path(): path input
│   ├── welcome.py            ← WelcomeScreen model + fake_waveform (domain logic)
│   ├── screens/
│   │   ├── welcome.py        ← Textual WelcomeScreen: mode selector + animated waveform
│   │   └── main.py           ← Textual MainScreen: key bindings, 20fps polling, layout
│   └── widgets/
│       ├── header.py         ← LogoHeader: ASCII logo
│       ├── you_panel.py      ← YouPanel: note, waveform, chords, meta
│       ├── riff_panel.py     ← RiffPanel: mode-aware bottom panel (FREE/COMPOSE)
│       ├── status_bar.py     ← StatusBar: device, listening, mode dots
│       ├── controls_bar.py   ← ControlsBar: context-aware keyboard hints
│       └── waveform_display.py ← WaveformDisplay: animated bars widget
├── assets/
│   └── zombie.mid            ← Bundled MIDI for welcome screen animation
└── (legacy)
    └── display.py            ← Old rich.Live UI — delegates to ComposeCommands, to be removed
```

---

## Thread model

| Thread | Name | Responsibility |
|---|---|---|
| Main | — | Textual event loop (async) |
| Audio | sounddevice internal | `AudioCapture._callback()` |
| Analysis | `riff-analyzer` | `AudioAnalyzer._loop()` |
| Generation | `riff-generate` | Generation + playback (spawned by ComposeCommands) |
| Listen | `riff-listen-midi` / `riff-listen-audio` | File playback + chord detection |

All auxiliary threads are `daemon=True`. Textual's `set_interval(1/20)` polls AppState — no keyboard thread needed.

---

## Data pipeline

```
Scarlett Solo
     │  USB audio
     ▼
AudioCapture._callback()      ← audio thread (sounddevice)
     │  queue.Queue (maxsize=64)
     ▼
AudioAnalyzer._loop()         ← analysis thread (daemon)
  ├─ every block (~23ms)    → RMS/dB + waveform
  ├─ every 4 blocks (~93ms) → pitch (librosa.pyin)
  └─ every 3s               → BPM (librosa.beat_track)
     │  AppState.update()
     ▼
MainScreen._poll_state()      ← Textual set_interval @ 20fps
  └─ widgets.update_from_snapshot(snap)
```

---

## AppState

The single source of truth. All threads write via `state.update(**kwargs)` or the atomic helpers. The UI reads via `snapshot()` only — a full copy taken once per frame under lock.

| Field | Type | Description |
|---|---|---|
| `note` | `str` | Detected note, e.g. `"E"` |
| `octave` | `int` | Octave, e.g. `4` |
| `frequency` | `float` | Fundamental frequency in Hz |
| `bpm` | `float` | Estimated tempo |
| `db` | `float` | Signal level in dBFS |
| `waveform` | `list[float]` | 48 amplitude points for display |
| `chords` | `list[str]` | Chord suggestions for current note |
| `captured_chords` | `list[str]` | Accumulated progression in COMPOSE |
| `gen_status` | `str` | Generation state: `""`, `"generating..."`, `"playing"`, `"done"` |
| `engine` | `str` | Active engine name |
| `mode` | `str` | Active mode: FREE / COMPOSE |
| `muted` | `bool` | True when user mutes |

---

## ComposeCommands

Application logic extracted from the old KeyboardHandler. UI-independent, testable without Textual.

| Method | Description |
|---|---|
| `load_file(path)` | Load MIDI/audio, auto-listen |
| `clear()` | Reset all compose state |
| `generate()` | Generate melody from captured chords |
| `generate_from_file()` | Generate from timed chords (MIDI) |
| `listen_source()` | Play source file + detect chords |
| `save()` | Save mix as WAV |
| `play_mix()` | Play source + generated synchronized |

---

## Mode system

Modes cycle with `m`. Engines cycle with `e`. Each mode renders different content in the RiffPanel widget.

---

## Engine system (plug & play)

Engines implement the `MelodyEngine` protocol in `riff/ai/engine.py`:

```python
class MelodyEngine(Protocol):
    name: str
    def generate(self, chords: list[Chord], bars: int = 4, bpm: int = 120) -> list[SongNote]: ...
```

To add a new engine:
1. Create `riff/ai/your_engine.py` with a class implementing the protocol
2. Call `register_engine(YourEngine())` at module level
3. Import the module in `riff/ai/engine.py`
4. It appears automatically when cycling with `e`

---

## Color palette

Defined in `riff/ui/palette.py`. Do not change without reason.

```python
YOU_COLOR   = "#b388ff"   # YOU panel text/waveform (light purple)
YOU_BORDER  = "#7c4dff"   # YOU panel border (medium purple)
YOU_BG      = "#0e0a17"   # YOU panel background

RIFF_COLOR  = "#69f0ae"   # RIFF panel text/waveform (light green)
RIFF_BORDER = "#00bfa5"   # RIFF panel border (teal)
RIFF_BG     = "#090f0d"   # RIFF panel background
```

`NOTE_COLORS` maps each note to a color on the chromatic wheel.

For the full design system including layout principles and interaction design,
see [docs/design-system.md](docs/design-system.md).

---

## Analyzer buffer sizes

| Buffer | Duration | Purpose |
|---|---|---|
| `_pitch_buf` (4 blocks) | ~93ms | Accumulate audio for `pyin` |
| `_waveform_buf` (deque) | ~300ms | Waveform display |
| `_bpm_buf` (deque) | ~4s | `beat_track` |
