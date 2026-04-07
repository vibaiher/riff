# RIFF — Real-time Intelligent Frequency Follower

CLI Python app that listens to your instrument in real time, analyzes what you play, and helps you learn and improve. Full-screen TUI built with `textual`.

```
██████╗ ██╗███████╗███████╗
██╔══██╗██║██╔════╝██╔════╝
██████╔╝██║█████╗  █████╗
██╔══██╗██║██╔══╝  ██╔══╝
██║  ██║██║██║     ██║
╚═╝  ╚═╝╚═╝╚═╝     ╚═╝  v0.2
```

For AI agents and contributors working on this codebase, read [AGENTS.md](AGENTS.md) first.

---

## Supported hardware

| Device | Connection | Status |
|---|---|---|
| Focusrite Scarlett Solo | USB | Auto-detected |
| Electric guitar | Jack → Scarlett | ✓ |
| Acoustic guitar | Jack → Scarlett | ✓ |
| Ukulele | Jack → Scarlett | ✓ |
| Darbuka / percussion | XLR → Scarlett | ✓ |

---

## Stack

| Library | Role |
|---|---|
| `textual` | TUI: screens, widgets, key bindings, CSS layout |
| `sounddevice` | Real-time audio capture (PortAudio) |
| `librosa` | Analysis: pitch (pyin), tempo, RMS/dB |
| `numpy` | Audio buffer processing |
| `pretty_midi` | MIDI to audio synthesis for generation |

---

## Installation

Requires Python 3.10+. `uv` recommended.

```bash
git clone <repo>
cd riff
uv sync
```

---

## Usage

```bash
uv run riff
uv run pytest
uv run pytest tests/test_modes.py -k test_phase_1
```

> Riff uses Textual's alternate screen mode for a fullscreen terminal experience.

---

## Controls

| Key | Action |
|---|---|
| `space` | Mute / unmute |
| `m` | Cycle mode (FREE → COMPOSE → FREE) |
| `e` | Cycle generation engine |
| `g` | Generate melody (COMPOSE only) |
| `c` | Clear captured chords (COMPOSE only) |
| `f` | Load MIDI or audio file (COMPOSE only) |
| `s` | Save mix as WAV (COMPOSE only) |
| `p` | Play mix (COMPOSE only) |
| `q` / `Ctrl-C` | Quit |

---

## Modes

| Mode | Description |
|---|---|
| **FREE** | Play and see what you're playing: note, octave, BPM |
| **COMPOSE** | Accumulate chords, load audio, generate melodies |
| **LEARN** | Guided learning with a living plan around real songs *(coming soon)* |

For full product documentation see [docs/product/overview.md](docs/product/overview.md).
