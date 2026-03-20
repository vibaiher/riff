# RIFF — Real-time Intelligent Frequency Follower

CLI en Python que escucha tu instrumento en tiempo real y responde musicalmente
como si fuera un músico improvisando contigo. Interfaz visual de pantalla
completa construida con `rich`.

```
██████╗ ██╗███████╗███████╗
██╔══██╗██║██╔════╝██╔════╝
██████╔╝██║█████╗  █████╗
██╔══██╗██║██╔══╝  ██╔══╝
██║  ██║██║██║     ██║
╚═╝  ╚═╝╚═╝╚═╝     ╚═╝  v0.1
```

---

## Hardware soportado

| Dispositivo | Conexión | Estado |
|---|---|---|
| Focusrite Scarlett Solo | USB | Auto-detectado |
| Guitarra eléctrica | Jack → Scarlett | ✓ |
| Guitarra acústica | Jack → Scarlett | ✓ |
| Ukelele | Jack → Scarlett | ✓ |
| Darbuka / percusión | XLR → Scarlett | ✓ |
| Raspberry Pi 4 | — | Fase 4 |

---

## Stack

| Librería | Rol |
|---|---|
| `rich` | TUI: layout, paneles, colores, live refresh |
| `sounddevice` | Captura de audio en tiempo real (PortAudio) |
| `librosa` | Análisis: pitch (pyin), tempo, RMS/dB |
| `numpy` | Procesado de buffers de audio |
| `magenta` / MelodyRNN | Generación de respuesta musical (Fase 2) |
| `fluidsynth` + `pretty_midi` | Síntesis MIDI a audio (Fase 3) |

---

## Instalación

Requiere Python 3.10+. Se recomienda `uv`.

```bash
git clone <repo>
cd riff
uv sync          # crea .venv e instala dependencias
```

---

## Uso

```bash
uv run riff
```

> **iTerm2 / Terminal.app**: el arranque envía `\033[9;1t` para maximizar la
> ventana automáticamente. Si tu terminal bloquea esta secuencia, pulsa
> `⌘⇧F` (iTerm2) o el botón verde antes de ejecutar.

### Controles

| Tecla | Acción |
|---|---|
| `space` | Silenciar / activar respuesta IA |
| `m` | Cambiar modo de improvisación |
| `q` / `Ctrl-C` | Salir |

### Modos disponibles

`JAZZ` · `BLUES` · `AMBIENT` · `ROCK` · `FREE`

---

## Interfaz

```
╭──────────────────────────────────────────────────────╮
│              ██████╗ ██╗███████╗███████╗              │
│              …                                        │
╰──── real-time intelligent frequency follower ─────────╯
╭─  YOU  ───────────────────────────────────────────────╮
│ E4    ███████████████████░░░░░░  -18.3 dB             │
│   █ █ █ █     █ █ █ █     █ █ █ █     █ █ █ █         │  ← waveform
│   …                                                   │
│  [E]  [C#m]  [A]  [B7]                               │  ← chord pills
│  tempo: ♩ 94  ·  latency: 18 ms                      │
╰───────────────────────────────────────────────────────╯
╭─  RIFF IS PLAYING  ──────────────────────────────────╮
│  …                                                    │
╰───────────────────────────────────────────────────────╯
  ● Scarlett Solo   ● listening   ○ generating
  [space] mute  [m] mode  [q] quit  ▌
```

### Adaptación dinámica al terminal

El layout calcula automáticamente la altura del waveform según las filas
disponibles. No hay scroll ni contenido fuera de pantalla.

| Terminal | Waveform | Chord pills |
|---|---|---|
| 24 filas | 3 filas | No |
| 30 filas | 5 filas | Sí |
| 40+ filas | 10+ filas | Sí |

---

## Fases del proyecto

### Fase 1 — Escuchar y visualizar ✅
- Detección automática de la Scarlett Solo
- Captura en tiempo real con `sounddevice`
- Pitch con `librosa.pyin` (C2–C8, cubre guitarra, uke y darbuka)
- BPM con `librosa.beat.beat_track` (buffer rolling de 4 s)
- TUI fullscreen con `rich.layout.Layout` + `Live(screen=True)`
- Waveform animado de barras verticales
- Chord pills (sugerencias de acordes por nota detectada)

### Fase 2 — Responder con IA 🔜
- Integrar MelodyRNN de Magenta
- Hook en `riff/audio/analyzer.py` → `# Phase 2 hook`
- Hook en `riff/main.py` → `# Phase 2` (instanciar `RiffResponder`)
- Poblar `state.riff_note`, `state.riff_active`, `state.riff_waveform`

### Fase 3 — Loop en tiempo real 🔜
- Unir escucha + análisis + generación + síntesis
- Objetivo de latencia < 50 ms
- La IA responde según dinámica: suave si tocas suave, agresiva si tocas fuerte

### Fase 4 — Port a Raspberry Pi 🔜
- Optimizar para Raspberry Pi 4
- Autostart con `systemd`
- Standalone sin laptop

---

## Arquitectura

```
riff/
├── main.py               ← Entry point. Wiring + señales SIGINT/SIGTERM.
├── core/
│   └── state.py          ← AppState: fuente única de verdad, thread-safe.
├── audio/
│   ├── capture.py        ← AudioCapture: sounddevice InputStream.
│   └── analyzer.py       ← AudioAnalyzer: pitch · BPM · dB · chords.
└── ui/
    ├── waveform.py       ← render_vbars() · render_bars() · render_oscilloscope()
    └── display.py        ← RiffDisplay · KeyboardHandler · build_layout()
```

### Pipeline de datos

```
Scarlett Solo
     │  USB audio
     ▼
AudioCapture._callback()     ← hilo de audio (sounddevice)
     │  queue.Queue (maxsize=64)
     ▼
AudioAnalyzer._loop()        ← hilo de análisis (daemon)
  ├─ cada bloque (~23 ms)  → RMS/dB + waveform
  ├─ cada 4 bloques (~93 ms) → pitch (librosa.pyin)
  └─ cada 3 s              → BPM (librosa.beat_track)
     │  AppState.update()
     ▼
RiffDisplay.run()            ← hilo principal
  └─ rich.Live @ 20 fps    → build_layout(snapshot)
```

---

## Variables de estado relevantes (`AppState`)

| Campo | Tipo | Descripción |
|---|---|---|
| `note` | `str` | Nota detectada, e.g. `"E"` |
| `octave` | `int` | Octava, e.g. `4` |
| `frequency` | `float` | Frecuencia fundamental en Hz |
| `bpm` | `float` | Tempo estimado |
| `db` | `float` | Nivel de señal en dBFS |
| `waveform` | `list[float]` | 48 puntos de amplitud para display |
| `chords` | `list[str]` | Sugerencias de acordes para la nota actual |
| `riff_note` | `str` | Nota generada por la IA (Fase 2) |
| `riff_active` | `bool` | True cuando la IA está generando |
| `muted` | `bool` | True cuando el usuario silencia la IA |
| `mode` | `str` (property) | Modo activo: JAZZ / BLUES / etc. |
