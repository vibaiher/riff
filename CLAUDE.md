# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

RIFF (Real-time Intelligent Frequency Follower) is a CLI Python app for learning and improving your instrument playing. It listens to a live instrument (guitar, uke, darbuka) via a Focusrite Scarlett Solo, analyzes pitch/tempo/dynamics in real time, and provides visual feedback through a fullscreen TUI.

Three modes: FREE (jam with metrics), PRACTICE (guided exercises), EAR_TRAINING (reproduce what you hear). See `ROADMAP.md` for detailed plans per mode.

## Commands

```bash
uv sync                  # install dependencies
uv run riff              # run the app
uv run riff --file x.mp3 # jam over an audio file
uv run pytest            # run all tests
uv run pytest tests/test_modes.py -k test_phase_1  # run a single test
```

## Architecture

Three threads communicate through `AppState` (single source of truth in `riff/core/state.py`):

```
Audio callback (sounddevice) → Queue(maxsize=64) → AudioAnalyzer thread
AudioAnalyzer → AppState.update()
RiffDisplay (main thread) → AppState.snapshot() → rich.Live @ 20fps
KeyboardHandler thread → AppState.toggle_mute() / next_mode() / next_timbre()
```

Key files:
- `riff/main.py` — entry point, wiring, signal handling
- `riff/core/state.py` — `AppState`: thread-safe shared state, `MODES`, `TIMBRES`
- `riff/audio/capture.py` — `AudioCapture` / `FilePlayback`: sounddevice InputStream
- `riff/audio/analyzer.py` — `AudioAnalyzer`: pitch (pyin), BPM, dB, chords
- `riff/ui/display.py` — `RiffDisplay` + `KeyboardHandler` + mode-aware panel rendering
- `riff/ui/waveform.py` — waveform rendering functions
- `riff/ai/` — reserved for future mode-specific logic

## Mode system

Modes cycle with `m` key: FREE → PRACTICE → EAR_TRAINING → FREE. Timbres cycle with `t`. The bottom panel renders different content per mode via `_MODE_TITLES` and `_MODE_PLACEHOLDERS` in `display.py`.

## Critical rules

- **Never write AppState fields directly** — always use `state.update(**kwargs)` or the atomic helpers (`toggle_mute`, `next_mode`, `next_timbre`). Display reads via `snapshot()` only.
- **Never block the audio callback** — `AudioCapture._callback` runs in PortAudio's thread. Only `queue.put_nowait()`. No I/O, no slow locks.
- **Layout must fit exactly on screen, no scroll** — `_panel_content_params(term_height)` computes `wf_height` and `show_chords` dynamically. If you add rows to a panel, update that function to subtract them from waveform height.
- **pyin needs warmup** — first call compiles via numba (~1-2s). `AudioAnalyzer._warmup()` handles this. Add any new numba-dependent librosa calls there.
- **Color palette is intentional** — defined in `display.py`, extracted from the original mockup. `_NOTE_COLORS` maps notes to chromatic-wheel colors. Don't change without reason.
