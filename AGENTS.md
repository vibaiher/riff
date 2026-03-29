# AGENTS.md — Guía para agentes IA trabajando en RIFF

Contexto acumulado durante el desarrollo.
Léelo antes de tocar cualquier archivo del proyecto.

---

## Qué es este proyecto

CLI Python para aprender y mejorar tocando un instrumento en tiempo real.
Escucha via Focusrite Scarlett Solo, analiza pitch/BPM/dinámica, y muestra
feedback visual en una TUI fullscreen con `rich`.

Tres modos: FREE (jam con métricas), PRACTICE (ejercicios guiados),
EAR_TRAINING (entrenamiento auditivo). Ver `ROADMAP.md` para detalles.

---

## Reglas críticas

### No romper el contrato de AppState
`riff/core/state.py` es la única fuente de verdad. Todo thread escribe vía
`state.update(**kwargs)` o los helpers atómicos (`toggle_mute`, `next_mode`,
`next_timbre`). Nunca escribas directamente a un campo desde fuera del objeto.

### El layout no puede hacer scroll
El constraint más importante del display: todo el contenido debe caber en pantalla
sin scroll. El sistema usa `_panel_content_params(term_height)` para calcular
`wf_height` y `show_chords` dinámicamente. Si añades filas al panel, actualiza
esa función para que descuente las filas extra del waveform.

### Nunca bloquear el hilo de audio
`AudioCapture._callback` corre en el hilo de audio de PortAudio. Solo puede
hacer `queue.put_nowait()`. Nada de I/O, logging pesado ni locks lentos ahí.

### pyin necesita warmup
`librosa.pyin` compila con numba la primera vez. `AudioAnalyzer._warmup()`
corre al arrancar el hilo de análisis. Si añades otras funciones de librosa
que usen numba, añádelas al warmup.

---

## Arquitectura en detalle

### Hilos en ejecución

| Hilo | Nombre | Qué hace |
|---|---|---|
| Principal | — | `RiffDisplay.run()` → rich Live @ 20 fps |
| Audio | sounddevice interno | `AudioCapture._callback()` |
| Análisis | `riff-analyzer` | `AudioAnalyzer._loop()` |
| Teclado | `riff-keyboard` | `KeyboardHandler._loop()` |

### Comunicación entre hilos

```
Audio callback → audio_queue (Queue, maxsize=64) → AudioAnalyzer
AudioAnalyzer  → AppState.update()
RiffDisplay    → AppState.snapshot()  (copia inmutable por frame)
KeyboardHandler→ AppState.toggle_mute() / next_mode() / next_timbre() / update(running=False)
```

`AppState.snapshot()` copia todos los campos bajo lock. El display nunca lee
campos directamente; siempre trabaja con el dict devuelto por snapshot.

### Sistema de modos

`MODES = ["FREE", "PRACTICE", "EAR_TRAINING"]` en `state.py`.
Tecla `m` cicla modos, tecla `t` cicla timbres.
El panel inferior renderiza contenido diferente según `snap["mode"]` via
`_MODE_TITLES` y `_MODE_PLACEHOLDERS` en `display.py`.

### Tamaños de buffer del analyzer

| Buffer | Duración | Uso |
|---|---|---|
| `_pitch_buf` (4 bloques) | ~93 ms | Acumular audio para `pyin` |
| `_waveform_buf` (deque) | ~300 ms | Display del waveform |
| `_bpm_buf` (deque) | ~4 s | `beat_track` |

BPM se actualiza cada `BPM_UPDATE_BLOCKS` (~3 s) para no sobrecargar.

---

## Paleta de colores (no cambiar sin motivo)

Extraída del mockup `riff_cli_mockup.html`. Usada de forma consistente en
todo `display.py`.

```python
YOU_COLOR   = "#b388ff"   # texto/waveform panel YOU (púrpura claro)
YOU_BORDER  = "#7c4dff"   # borde panel YOU (púrpura medio)
YOU_BG      = "#0e0a17"   # fondo panel YOU (casi negro con tinte púrpura)

RIFF_COLOR  = "#69f0ae"   # texto/waveform panel RIFF (verde claro)
RIFF_BORDER = "#00bfa5"   # borde panel RIFF (teal)
RIFF_BG     = "#090f0d"   # fondo panel RIFF (casi negro con tinte teal)

LABEL_DIM   = "#555555"   # etiquetas de sección
META_KEY    = "#444444"   # claves de metadatos
META_VAL    = "#666666"   # valores de metadatos
BAR_EMPTY   = "#1e1e1e"   # segmentos vacíos barra de nivel
SEP_COLOR   = "#2a2a2a"   # separadores
```

Los colores de nota (`_NOTE_COLORS`) mapean cada nota a un color de la rueda
cromática. No son arbitrarios; están pensados para que notas cercanas tengan
colores similares.

---

## Cómo funciona el fullscreen en macOS

Al arrancar `RiffDisplay.run()`:
1. Se envía `\033[9;1t` — escape XTerm que maximiza la ventana en
   iTerm2, Terminal.app y emuladores compatibles.
2. Se espera 150 ms para que el OS procese el resize.
3. `rich.Live(screen=True)` entra en el buffer de pantalla alternativa
   (como hace `vim` o `less`). Al salir, restaura el terminal anterior.
4. En cada frame se lee `console.size.height` — la misma fuente que usa
   `rich.Layout` internamente — garantizando sincronía perfecta.

---

## Lecciones aprendidas

### rich.Layout vs Group para pantalla completa
- `rich.console.Group` apilado verticalmente no llena la pantalla.
- `rich.layout.Layout` con secciones `size=N` y `ratio=1` llena el
  terminal exactamente y se adapta a cualquier altura.

### librosa.pyin en tiempo real
- Necesita al menos ~2048 muestras para dar resultados útiles.
- Con bloques de 1024 muestras acumulamos 4 bloques (~93 ms) antes de llamarlo.
- La primera llamada compila numba (~1-2 s): hacer warmup al arrancar el hilo.
- Para señales en silencio (`db < SILENCE_DB`), saltar pyin completamente.

### Chord pills
Las sugerencias de acordes son heurísticas simples (teoría musical básica):
tónica mayor, relativa menor, subdominante, dominante 7ª.

---

## Convenciones del proyecto

- **Un solo `AppState`**: se crea en `main()` y se pasa a todos los componentes.
- **Snapshot por frame**: el display nunca lee state en medio de un render;
  llama `snapshot()` una vez al inicio del frame y usa ese dict.
- **Hilos daemon**: todos los hilos auxiliares son `daemon=True` para que
  terminen solos si el proceso principal muere.
- **Queue con maxsize**: la cola de audio tiene `maxsize=64`. Si el analyzer
  va lento, los bloques se descartan silenciosamente. Nunca bloquear el callback.

---

## Entorno

- **Plataforma de desarrollo**: macOS (MacBook Air), terminal iTerm2
- **Gestor de paquetes**: `uv` (`uv sync` para instalar, `uv run riff` para ejecutar)
- **Python**: 3.10+ requerido (usa `match`, `X | Y` type union, etc.)
