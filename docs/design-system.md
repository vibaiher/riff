# Design System

Riff is a terminal application. Its design system operates within the constraints of a fixed-size screen, monospace typography, and a single color space. Every decision is intentional — the palette, the layout, the waveform, the silence.

---

## Principles

**The music is the interface.** Riff never competes with what you're playing. Visual elements exist to reflect and support the sound, not to draw attention to themselves.

**No scroll, ever.** The entire interface must fit on screen at all times. Content adapts dynamically to the available terminal height. If it doesn't fit, it doesn't show.

**Silence is a design decision.** Riff shows information only when it's useful. Empty space is not a problem to solve.

**Two voices, clearly separated.** YOU and RIFF are always visually distinct. The user always knows whose turn it is and who is speaking.

---

## Color palette

The palette is extracted from the original mockup and must not change without reason. It is defined in `riff/ui/palette.py`.

### YOU panel

```python
YOU_COLOR   = "#b388ff"   # Text and waveform (light purple)
YOU_BORDER  = "#7c4dff"   # Panel border (medium purple)
YOU_BG      = "#0e0a17"   # Panel background (near-black with purple tint)
```

### RIFF panel

```python
RIFF_COLOR  = "#69f0ae"   # Text and waveform (light green)
RIFF_BORDER = "#00bfa5"   # Panel border (teal)
RIFF_BG     = "#090f0d"   # Panel background (near-black with teal tint)
```

### Note colors

Each note maps to a color on the chromatic wheel via `NOTE_COLORS` in `riff/ui/palette.py`. The mapping is consistent across all contexts where a note is displayed.

### General background

Near-black throughout. The two panel tints (purple and teal) create the only chromatic separation in the layout. No other background colors are introduced.

---

## Typography

Riff runs in a monospace terminal. There are no font choices — the terminal font is the font. Design decisions work within that constraint.

**The logo** uses ASCII block characters rendered at startup and on the welcome screen. It is fixed — do not alter the proportions or character set.

```
██████╗ ██╗███████╗███████╗
██╔══██╗██║██╔════╝██╔════╝
██████╔╝██║█████╗  █████╗
██╔══██╗██║██╔══╝  ██╔══╝
██║  ██║██║██║     ██║
╚═╝  ╚═╝╚═╝╚═╝     ╚═╝
```

**Information hierarchy** is communicated through color, not size. The detected note is the most prominent element in the YOU panel. Everything else is secondary.

---

## Layout

The screen is divided into three vertical regions:

```
╭─ Header ──────────────────────────────────────────────╮
│  Logo + subtitle                                      │
╰───────────────────────────────────────────────────────╯
╭─ YOU ─────────────────────────────────────────────────╮
│  Note · dB meter · Waveform · Chord pills · Tempo     │
╰───────────────────────────────────────────────────────╯
╭─ RIFF · [MODE] ───────────────────────────────────────╮
│  Mode-specific content                                │
╰───────────────────────────────────────────────────────╯
  Status bar · Controls
```

### Dynamic height

Layout is managed via Textual CSS. The YOU and RIFF panels use `height: 1fr` to split remaining space equally. The waveform inside each panel adapts to the available widget size dynamically. Fixed elements (header, status bar, controls) have explicit heights.

### Panel borders

Panels are Textual widgets that render Rich Panel renderables internally. YOU uses purple borders, RIFF uses teal. The mode name appears in the RIFF panel title: `─ RIFF · COMPOSE ─`.

---

## Components

### Waveform

The central visual element. Three rendering modes available in `waveform.py`:

- `render_vbars()` — vertical bars, the default
- `render_bars()` — horizontal bars
- `render_oscilloscope()` — oscilloscope curve

The waveform height adapts dynamically. It is the only element that shrinks when the terminal is too small — all other elements are fixed height.

The waveform in the YOU panel uses `YOU_COLOR`. The waveform in the RIFF panel uses `RIFF_COLOR`. They are never the same color.

### dB meter

A horizontal bar showing signal level in dBFS. Displayed in the YOU panel alongside the detected note. Provides immediate visual feedback on playing dynamics.

### Chord pills

Rendered in the YOU panel as bracketed labels: `[Em]  [C#m]  [A]  [B7]`. Pills show the current chord suggestions for the detected note. In COMPOSE mode, the accumulated progression appears in the RIFF panel.

### Status bar

A single line at the bottom of the screen. Shows:
- Hardware status (Scarlett Solo connected)
- Listening state
- Active mode
- Available controls for the current mode

Controls are shown as `[key] action` pairs. Only controls relevant to the current mode are shown.

### Welcome screen

Displayed on startup. Contains the mode selector and an animated waveform driven by `zombie.mid`. The animation uses the same waveform rendering as the main interface. Mode selection happens here before any audio processing begins.

---

## Interaction design

### Two panels, two roles

YOU reflects what the user plays. RIFF responds, generates, or guides — depending on the mode. This separation is never broken. RIFF content never appears in the YOU panel and vice versa.

### Mode-aware controls

The status bar and keyboard shortcuts adapt to the active mode. Controls that do nothing in the current mode are not shown. This reduces visual noise and prevents confusion.

### Feedback without judgment

When detection produces no result — silence, noise, an unrecognized chord — the interface shows nothing rather than an error. Riff does not signal failure for ambiguous input.

### Generation feedback

When the user triggers generation (`g`), the RIFF panel shows a status string: `generating...` → `playing` → `done`. The UI never blocks. Generation runs in a background thread and updates `gen_status` in AppState, which the display picks up on the next frame.

---

## Sound design

### Timbres

AppState defines a set of timbres via `TIMBRES`. These control the character of synthesized audio:

| Timbre | Character |
|---|---|
| CLEAN | Neutral, uncolored |
| WARM | Rounded, soft attack |
| BRIGHT | High presence, sharp attack |
| PAD | Sustained, slow attack |
| RAW | Unprocessed, direct |

Timbres apply to all audio synthesis within Riff. The active timbre is part of AppState and persists across mode changes.

### Electric guitar soundfont

All MIDI reproduction uses FluidSynth with an electric guitar SF2 soundfont. The output must sound like an electric guitar — not a keyboard, not a generic synth. See [decisions/004-fluidsynth.md](decisions/004-fluidsynth.md).
