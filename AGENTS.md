# AGENTS.md

Entry point for any AI agent working on this codebase. Read this before touching any file.

For product context — what Riff is, why it exists, and the principles behind it — read [docs/product/overview.md](docs/product/overview.md) and [docs/product/identity.md](docs/product/identity.md).

For architecture and technical decisions, read [ARCHITECTURE.md](ARCHITECTURE.md) and [docs/decisions/](docs/decisions/).

For visual and interaction design, read [docs/design-system.md](docs/design-system.md).

---

## Critical rules

### Never write AppState fields directly
`riff/core/state.py` is the single source of truth. All threads write via `state.update(**kwargs)` or the atomic helpers: `toggle_mute`, `next_mode`, `next_engine`, `add_chord`, `clear_chords`. Never write directly to a field from outside the object. The display reads via `snapshot()` only.

### Never block the audio callback
`AudioCapture._callback` runs in PortAudio's audio thread. It may only call `queue.put_nowait()`. No I/O, no logging, no slow locks.

### Application logic goes in ComposeCommands
`riff/core/commands.py` owns all COMPOSE logic (load, generate, save, play). Screens and widgets are thin dispatchers — they call `ComposeCommands` methods, never implement business logic.

### pyin needs warmup
`librosa.pyin` compiles via numba on first call (~1-2s). `AudioAnalyzer._warmup()` handles this on thread start. Add any new numba-dependent librosa calls there.

### Generation must not block the UI
`ComposeCommands` spawns daemon threads for generation and playback. The Textual 20fps poll picks up state changes automatically. Never run heavy computation on the main thread.

### The turn principle (Learn mode)
Riff never plays and listens at the same time. Every exercise has two sequential and exclusive phases: Riff plays, then the user plays. See [docs/decisions/003-turn-principle.md](docs/decisions/003-turn-principle.md).

---

## Environment

- **Platform**: macOS (MacBook Air), iTerm2
- **Package manager**: `uv` — use `uv sync` to install, `uv run riff` to run
- **Python**: 3.10+ required
