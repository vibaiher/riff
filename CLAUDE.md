# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

RIFF (Real-time Intelligent Frequency Follower) is a CLI Python app for learning and improving your instrument playing. It listens to a live instrument (guitar, uke, darbuka) via a Focusrite Scarlett Solo, analyzes pitch/tempo/dynamics in real time, and provides visual feedback through a fullscreen TUI.

Two modes: FREE (see what you play), COMPOSE (accumulate chords + generate melodies). A welcome screen lets you pick the mode at startup. See `ROADMAP.md` for future plans.

## Commands

```bash
uv sync                  # install dependencies
uv run riff              # run the app
uv run pytest            # run all tests
uv run pytest tests/test_modes.py -k test_phase_1  # run a single test
```

## Architecture

Three threads communicate through `AppState` (single source of truth in `riff/core/state.py`):

```
Audio callback (sounddevice) → Queue(maxsize=64) → AudioAnalyzer thread
AudioAnalyzer → AppState.update() + AppState.add_chord() (in COMPOSE mode)
RiffDisplay (main thread) → AppState.snapshot() → rich.Live @ 20fps
KeyboardHandler thread → AppState.toggle_mute() / next_mode() / next_engine()
```

Key files:
- `riff/main.py` — entry point, wiring, signal handling
- `riff/core/state.py` — `AppState`: thread-safe shared state, `MODES`, `TIMBRES`
- `riff/audio/capture.py` — `AudioCapture`: sounddevice InputStream
- `riff/audio/analyzer.py` — `AudioAnalyzer`: pitch (pyin), BPM, dB, chords + chord accumulation
- `riff/audio/song.py` — `SongData`, `SongNote`, `SongPlayer`, `SongTracker`
- `riff/audio/chords.py` — `Chord` dataclass, `parse_progression()`, `detect_chord()`
- `riff/audio/midi_feeder.py` — `MidiFeeder`: feeds loaded MIDI into YOU panel + chord accumulation
- `riff/audio/mix.py` — `mix_audio()`, `save_wav()`: audio mixing and WAV export
- `riff/ui/file_input.py` — `InputBuffer`, `complete_path()`: TUI file path input with tab-completion
- `riff/ai/engine.py` — `MelodyEngine` protocol + plug & play registry
- `riff/ai/phrase.py` — `PhraseEngine`: phrase-based melody generation with motifs, rests, and chord resolution
- `riff/ai/generate.py` — `generate_song()`: progression string → playable `SongData`
- `riff/ui/welcome.py` — welcome screen: mode selector + animated waveform from bundled MIDI
- `riff/ui/display.py` — `RiffDisplay` + `KeyboardHandler` + mode-aware panel rendering
- `riff/ui/waveform.py` — waveform rendering functions
- `riff/assets/zombie.mid` — bundled MIDI for welcome screen waveform animation

## Mode system

Modes cycle with `m` key: FREE → COMPOSE → FREE. Engines cycle with `e`. The bottom panel renders different content per mode via `_mode_content()` in `display.py`.

- **FREE**: Shows what the user is playing (note, octave, BPM). No accumulation.
- **COMPOSE**: Accumulates detected chords into `captured_chords`. Keys `g` (generate), `c` (clear), `f` (load MIDI/audio file), `s` (save WAV), and `p` (play mix) only work in this mode. `f` opens a path input with tab-completion — the loaded file auto-plays while RIFF detects chords. `s` saves the mix (source + generated) as WAV. `p` plays both audios synchronized. Generation runs in a background thread.

## Engine system (plug & play)

Engines implement the `MelodyEngine` protocol (`riff/ai/engine.py`): `name: str` + `generate(chords, bars, bpm) -> list[SongNote]`. To add a new engine:
1. Create `riff/ai/your_engine.py` with a class implementing the protocol
2. Call `register_engine(YourEngine())` at module level
3. Import the module in `riff/ai/engine.py`
4. It appears automatically when cycling with `e`

## Critical rules

- **Never write AppState fields directly** — always use `state.update(**kwargs)` or the atomic helpers (`toggle_mute`, `next_mode`, `next_engine`, `add_chord`, `clear_chords`). Display reads via `snapshot()` only.
- **Never block the audio callback** — `AudioCapture._callback` runs in PortAudio's thread. Only `queue.put_nowait()`. No I/O, no slow locks.
- **Layout must fit exactly on screen, no scroll** — `_panel_content_params(term_height)` computes `wf_height` and `show_chords` dynamically. If you add rows to a panel, update that function to subtract them from waveform height.
- **pyin needs warmup** — first call compiles via numba (~1-2s). `AudioAnalyzer._warmup()` handles this. Add any new numba-dependent librosa calls there.
- **Color palette is intentional** — defined in `display.py`, extracted from the original mockup. `_NOTE_COLORS` maps notes to chromatic-wheel colors. Don't change without reason.
- **Generation must not block the UI** — `_trigger_generate` in KeyboardHandler spawns a daemon thread for generation + playback.
