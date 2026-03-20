# AGENTS.md — Guía para agentes IA trabajando en RIFF

Contexto acumulado durante la sesión de desarrollo inicial.
Léelo antes de tocar cualquier archivo del proyecto.

---

## Qué es este proyecto

CLI Python de música en tiempo real. El usuario toca un instrumento, RIFF lo
escucha, analiza la señal y responde musicalmente como un músico improvisando.
Fase 1 ya implementada. Fases 2-4 pendientes.

---

## Reglas críticas

### No romper el contrato de AppState
`riff/core/state.py` es la única fuente de verdad. Todo thread escribe vía
`state.update(**kwargs)` o los helpers atómicos (`toggle_mute`, `next_mode`).
Nunca escribas directamente a un campo desde fuera del objeto.

### El layout no puede hacer scroll
El constraint más importante del display: todo el contenido debe caber en pantalla
sin scroll. El sistema usa `_panel_content_params(term_height)` para calcular
`wf_height` y `show_chords` dinámicamente. Si añades filas al panel, actualiza
esa función para que descuente las filas extra del waveform.

### La altura del layout debe cuadrar exactamente
```
header(8) + you(ratio=1) + riff(ratio=1) + status(1) + controls(1)
```
Filas fijas = 10. Los dos paneles con `ratio=1` se reparten el resto.
Si cambias tamaños fijos, actualiza `_panel_content_params` en consecuencia.

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
| (Fase 2) | `riff-responder` | MelodyRNN inference |

### Comunicación entre hilos

```
Audio callback → audio_queue (Queue, maxsize=64) → AudioAnalyzer
AudioAnalyzer  → AppState.update()
RiffDisplay    → AppState.snapshot()  (copia inmutable por frame)
KeyboardHandler→ AppState.toggle_mute() / next_mode() / update(running=False)
```

`AppState.snapshot()` copia todos los campos bajo lock. El display nunca lee
campos directamente; siempre trabaja con el dict devuelto por snapshot.

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

## Cómo extender para Fase 2 (MelodyRNN)

Los hooks ya están marcados en el código:

### 1. `riff/audio/analyzer.py` — al final de `_process()`
```python
# ── Phase 2 hook ──────────────────────────────────────────────────────────────
# TODO: forward updates["note"], updates.get("bpm"), db to MelodyRNN
# and write state.riff_note / state.riff_active / state.riff_waveform
```
Aquí crea un `RiffResponder` que recibe la nota+BPM+dB y llama a MelodyRNN
en su propio hilo para no bloquear el análisis.

### 2. `riff/main.py` — en `main()`
```python
# Phase 2: instantiate MelodyRNN here and pass it to a RiffResponder
# riff_responder = RiffResponder(state, model_checkpoint="...")
```
Instancia e inicia el responder entre `analyzer.start()` y `display.run()`.

### 3. `riff/core/state.py` — campos ya preparados
```python
riff_note: str       # nota generada
riff_octave: int     # octava de la nota generada
riff_waveform: list  # amplitudes del audio sintetizado (para display)
riff_active: bool    # True cuando la IA está generando
riff_next_note: str  # siguiente nota predicha (para mostrar en UI)
```
Escribe estos campos con `state.update(riff_note=..., riff_active=True, ...)`.

### 4. `riff/ui/display.py` — panel RIFF
El panel `_riff_panel()` ya lee `riff_waveform` y `riff_note` del snapshot.
En Fase 2 también poblar `riff_chords` (lista vacía en Fase 1).

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

Si el terminal bloquea las manipulaciones de ventana
(*iTerm2 → Preferences → Profiles → Terminal → Disable session-initiated
window resizing*), el usuario debe maximizar manualmente antes de ejecutar.

---

## Lecciones aprendidas en esta sesión

### rich.Layout vs Group para pantalla completa
- `rich.console.Group` apilado verticalmente no llena la pantalla: el
  contenido aparece arriba y el resto queda vacío.
- `rich.layout.Layout` con secciones `size=N` y `ratio=1` llena el
  terminal exactamente y se adapta a cualquier altura.
- Usar siempre `Layout` para TUIs que deben ocupar toda la pantalla.

### Panel height y contenido adaptativo
Cuando el contenido de un Panel es más corto que la sección del Layout,
rich añade líneas en blanco al final del Panel. Esto es correcto y esperado.
El Panel sí llena su sección; el contenido interior puede ser más corto.

### tty.setraw() no afecta a os.get_terminal_size()
El modo raw afecta solo al procesado de input (sin eco, sin buffering por línea).
`TIOCGWINSZ` (el ioctl que devuelve el tamaño del terminal) es independiente
del modo tty. Se pueden usar ambos simultáneamente sin conflicto.

### librosa.pyin en tiempo real
- Necesita al menos ~2048 muestras para dar resultados útiles.
- Con bloques de 1024 muestras acumulamos 4 bloques (~93 ms) antes de llamarlo.
- La primera llamada compila numba (~1-2 s): hacer warmup al arrancar el hilo.
- Para señales en silencio (`db < SILENCE_DB`), saltar pyin completamente.

### La barra de nivel dB
Rango útil: -80 dBFS (silencio) a 0 dBFS (clip). Formula:
```python
filled = int((db + 80.0) / 80.0 * bar_width)
```
Los instrumentos acústicos suelen estar entre -40 y -10 dBFS.

### Chord pills
Las sugerencias de acordes son heurísticas simples (teoría musical básica):
tónica mayor, relativa menor, subdominante, dominante 7ª.
En Fase 2 sustituir por el contexto armónico real que genere MelodyRNN.

---

## Convenciones del proyecto

- **Un solo `AppState`**: se crea en `main()` y se pasa a todos los componentes.
- **Snapshot por frame**: el display nunca lee state en medio de un render;
  llama `snapshot()` una vez al inicio del frame y usa ese dict.
- **Hilos daemon**: todos los hilos auxiliares son `daemon=True` para que
  terminen solos si el proceso principal muere.
- **Queue con maxsize**: la cola de audio tiene `maxsize=64`. Si el analyzer
  va lento, los bloques se descartan silenciosamente. Nunca bloquear el callback.
- **Comentarios `# Phase N:`**: marcan puntos de extensión. No borrarlos.

---

## Entorno

- **Plataforma de desarrollo**: macOS (MacBook Air), terminal iTerm2
- **Plataforma de producción final**: Raspberry Pi 4 (Fase 4)
- **Gestor de paquetes**: `uv` (`uv sync` para instalar, `uv run riff` para ejecutar)
- **Python**: 3.10+ requerido (usa `match`, `X | Y` type union, etc.)
