"""Terminal UI — layout exacto para 146×42 con FiraCode Nerd Font Mono 16px.

Layout de pantalla completa con rich.layout.Layout.  Sin scroll.
Dimensiones leídas en runtime con os.get_terminal_size() (via console.size).

Estructura fija (42 filas × 146 columnas):
  ┌─ HEADER   (size=5)  ────────────────────────────┐  Logo ASCII 3 líneas + subtítulo
  ├─ SEP1     (size=1)  ────────────────────────────┤  Separador horizontal
  ├─ YOU      (size=15) ────────────────────────────┤  Panel púrpura — nota, waveform, chords
  ├─ SEP2     (size=1)  ────────────────────────────┤  Separador horizontal
  ├─ RIFF     (size=15) ────────────────────────────┤  Panel teal — respuesta IA
  ├─ STATUS   (size=2)  ────────────────────────────┤  Dots de estado + regla
  ├─ CONTROLS (size=2)  ────────────────────────────┤  Atajos de teclado + cursor
  └─ MARGIN   (size=1)  ────────────────────────────┘  Margen inferior
                                                        Total = 5+1+15+1+15+2+2+1 = 42

Filas de contenido por panel (size=15, bordes Panel = 2):
  13 filas = 1 (nota+barra) + 10 (waveform) + 1 (chords) + 1 (meta)

n_bars del waveform para 146 cols:
  avail_w = 146 − 2 (bordes panel) − 2 (prefijo) = 142
  n_bars  = (142 + 1) // 2 = 71  →  ancho = 141 chars ✓
"""
from __future__ import annotations

import os
import select
import sys
import termios
import time
import tty
import threading
from typing import Optional

from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from .waveform import render_vbars

# ── Paleta exacta del mockup ──────────────────────────────────────────────────
YOU_COLOR   = "#b388ff"   # texto y waveform panel YOU
YOU_BORDER  = "#7c4dff"   # borde panel YOU
YOU_BG      = "#0e0a17"   # fondo panel YOU (púrpura muy oscuro)

RIFF_COLOR  = "#69f0ae"   # texto y waveform panel RIFF
RIFF_BORDER = "#00bfa5"   # borde panel RIFF
RIFF_BG     = "#090f0d"   # fondo panel RIFF (teal muy oscuro)

LABEL_DIM   = "#555555"   # etiquetas de sección
META_KEY    = "#444444"   # claves de metadatos
META_VAL    = "#666666"   # valores de metadatos
BAR_EMPTY   = "#1e1e1e"   # segmentos vacíos de la barra de nivel
SEP_COLOR   = "#2a2a2a"   # separadores / bordes casi invisibles

REFRESH_RATE = 20

# ── Logo ASCII — 6 líneas completas para header(size=7) sin Panel ────────────
#   Group directo: 6 (logo) + 1 (subtítulo) = 7 filas exactas ✓
LOGO = (
    "██████╗ ██╗███████╗███████╗\n"
    "██╔══██╗██║██╔════╝██╔════╝\n"
    "██████╔╝██║█████╗  █████╗  \n"
    "██╔══██╗██║██╔══╝  ██╔══╝  \n"
    "██║  ██║██║██║     ██║     \n"
    "╚═╝  ╚═╝╚═╝╚═╝     ╚═╝  v0.1"
)

# ── Color por nota (rueda cromática) ─────────────────────────────────────────
_NOTE_COLORS: dict[str, str] = {
    "C": "#ff6b6b", "C#": "#ff9f43", "D": "#ffd32a", "D#": "#0be881",
    "E": "#0fbcf9", "F": "#48dbfb", "F#": "#f368e0", "G": "#ff9ff3",
    "G#": "#54a0ff", "A": "#a29bfe", "A#": "#00d2d3", "B":  "#fd79a8",
    "—": LABEL_DIM,
}


def _note_color(note: str) -> str:
    return _NOTE_COLORS.get(note, "#aaaaaa")


def _blink() -> bool:
    """Parpadeo lento (~1.5 Hz) para dots de estado y cursor."""
    return int(time.time() * 3) % 2 == 0


# ── Cálculo adaptativo de alturas y barras ────────────────────────────────────

def _panel_content_params(term_height: int, term_width: int) -> tuple[int, bool, int]:
    """
    Devuelve (wf_height, show_chords, n_bars) según las dimensiones del terminal.

    Filas fijas del layout (sin los dos paneles you/riff):
      header(7) + sep1(1) + sep2(1) + status(2) + controls(2) + margin(1) = 14

    Filas disponibles para ambos paneles: term_height − 12
    Filas por panel: available // 2  (el riff absorbe el residuo impar)
    Contenido por panel (menos 2 bordes del Panel): panel_rows − 2

    Distribución de contenido (content_h >= 6):
      1 fila  → nota + barra de nivel
      N filas → waveform
      1 fila  → chord pills
      1 fila  → metadatos

    n_bars = (term_width − 4 + 1) // 2
      donde 4 = 2 (bordes panel) + 2 (prefijo de espacios en waveform)
    """
    fixed       = 7 + 1 + 1 + 2 + 2 + 1          # = 14
    available   = max(10, term_height - fixed)
    panel_rows  = max(5, available // 2)
    content_h   = panel_rows - 2                  # descontar bordes Panel

    if content_h >= 6:
        wf_h        = content_h - 3               # nota + wf + chords + meta
        show_chords = True
    else:
        wf_h        = max(2, content_h - 2)       # nota + wf + meta
        show_chords = False

    avail_w = max(10, term_width - 4)
    n_bars  = max(8, (avail_w + 1) // 2)

    return wf_h, show_chords, n_bars


# ── Constructores de elementos individuales ───────────────────────────────────

def _header_panel() -> Group:
    """
    Cabecera sin Panel — las 7 filas son contenido directo:
      rows 0-5 → logo ASCII completo (6 líneas, todas las letras cerradas)
      row 6    → subtítulo centrado
    Total = 7 filas ✓
    """
    logo = Text(LOGO, style=f"bold {YOU_COLOR}")
    subtitle = Text(
        "real-time intelligent frequency follower",
        style=META_VAL,
        justify="center",
    )
    return Group(Align.center(logo), Align.center(subtitle))


def _separator() -> Rule:
    """Separador horizontal de 1 fila entre secciones del layout."""
    return Rule(style=SEP_COLOR)


def _note_bar_row(note: str, octave: int, db: float, panel_color: str) -> Table:
    """
    Fila única: badge de nota  +  barra horizontal de nivel  +  valor dB.
    Usa rich.table.Table.grid para alineación precisa de columnas.
    """
    t = Table.grid(expand=True, padding=(0, 1, 0, 0))
    t.add_column(width=7,  no_wrap=True)   # badge de nota
    t.add_column(ratio=1,  no_wrap=True)   # barra de nivel (rellena el espacio)
    t.add_column(width=12, no_wrap=True)   # valor dB

    nc    = _note_color(note)
    badge = f" {note}{octave if note != '—' else ''}"

    clamped = max(-80.0, min(0.0, db))
    filled  = int((clamped + 80.0) / 80.0 * 30)
    bar = Text()
    bar.append("█" * filled,        style=panel_color)
    bar.append("░" * (30 - filled), style=BAR_EMPTY)

    t.add_row(
        Text(f"{badge:<7}", style=f"bold {nc}"),
        bar,
        Text(f" {db:+.1f} dB ", style=META_VAL),
    )
    return t


def _waveform_block(data: list[float], color: str, height: int, n_bars: int) -> Text:
    """
    Bloque de barras verticales animado.
    n_bars se calcula en _panel_content_params según el ancho del terminal.
    """
    wf    = render_vbars(data, n_bars=n_bars, height=height)
    lines = wf.split("\n")
    t     = Text()
    for i, line in enumerate(lines):
        suffix = "\n" if i < len(lines) - 1 else ""
        t.append(f"  {line}{suffix}", style=color)
    return t


def _chord_pills(chords: list[str], color: str) -> Text:
    """
    Badges de acordes: el primero en color activo, el resto en gris tenue.
    Máximo 4 acordes para no desbordar la línea.
    """
    t = Text()
    t.append("  ")
    for i, chord in enumerate(chords[:4]):
        if i:
            t.append("  ")
        style = f"bold {color}" if i == 0 else f"{LABEL_DIM}"
        t.append(f"[{chord}]", style=style)
    return t


def _meta_line(items: list[tuple[str, str]]) -> Text:
    """Línea de metadatos clave·valor separados por ·"""
    t = Text()
    t.append("  ")
    for i, (k, v) in enumerate(items):
        if i:
            t.append("  ·  ", style=META_KEY)
        t.append(f"{k}: ", style=META_KEY)
        t.append(v,         style=META_VAL)
    return t


# ── Paneles principales ───────────────────────────────────────────────────────

def _you_panel(snap: dict, wf_height: int, show_chords: bool, n_bars: int) -> Panel:
    note    = snap["note"]
    octave  = snap["octave"]
    db      = snap["db"]
    bpm     = snap["bpm"]
    latency = snap["latency_ms"]
    chords  = snap["chords"]
    wf      = snap["waveform"]

    bpm_str = f"♩ {bpm:.0f}" if bpm > 0 else "—"

    parts: list = [
        _note_bar_row(note, octave, db, YOU_COLOR),
        _waveform_block(wf, YOU_COLOR, wf_height, n_bars),
    ]
    if show_chords:
        parts.append(_chord_pills(chords, YOU_COLOR))
    parts.append(_meta_line([("tempo", bpm_str), ("latency", f"{latency:.0f} ms")]))

    return Panel(
        Group(*parts),
        title=f"[bold {LABEL_DIM}]  YOU  [/bold {LABEL_DIM}]",
        title_align="left",
        border_style=YOU_BORDER,
        box=box.ROUNDED,
        style=f"on {YOU_BG}",
        padding=(0, 0),
    )


def _riff_panel(snap: dict, wf_height: int, show_chords: bool, n_bars: int) -> Panel:
    note      = snap["riff_note"]
    octave    = snap["riff_octave"]
    active    = snap["riff_active"]
    muted     = snap["muted"]
    mode      = snap["mode"]
    model     = snap["riff_model"]
    next_note = snap["riff_next_note"]
    wf        = snap["riff_waveform"]

    # Phase 2: riff_chords vendrá de MelodyRNN
    riff_chords: list[str] = []

    if muted:
        border_style = "#5a1a1a"
        color        = "#ff5555"
    else:
        border_style = RIFF_BORDER
        color        = RIFF_COLOR

    next_str = f"{next_note} →" if next_note != "—" else "—"

    parts: list = [
        _note_bar_row(note, octave, -80.0, color),  # Phase 2: dB real del synth
        _waveform_block(wf, color, wf_height, n_bars),
    ]
    if show_chords:
        parts.append(
            _chord_pills(riff_chords, color) if riff_chords else Text()
        )
    parts.append(_meta_line([("mode", mode), ("model", model), ("next", next_str)]))

    return Panel(
        Group(*parts),
        title=f"[bold {LABEL_DIM}]  RIFF IS PLAYING  [/bold {LABEL_DIM}]",
        title_align="left",
        border_style=border_style,
        box=box.ROUNDED,
        style=f"on {RIFF_BG}",
        padding=(0, 0),
    )


# ── Barra de estado y controles ───────────────────────────────────────────────

def _status_bar(snap: dict) -> Group:
    """
    Dos filas para el slot status(size=2):
      fila 1 → tres indicadores con punto de color, dos parpadeantes
      fila 2 → regla separadora (visual breathing room antes de controls)
    """
    device  = snap["device_name"]
    active  = snap["note"] != "—"
    riff_on = snap["riff_active"] and not snap["muted"]
    b       = _blink()

    t = Text()
    t.append("  ")

    # Punto verde fijo: dispositivo conectado
    t.append("● ", style=f"bold {RIFF_COLOR}")
    t.append(f"{device}   ", style=META_VAL)

    # Punto púrpura: listening (parpadea cuando detecta señal)
    if active and b:
        t.append("● ", style=f"bold {YOU_COLOR}")
    else:
        t.append("○ ", style=f"{LABEL_DIM}")
    t.append("listening   ", style=META_VAL if active else META_KEY)

    # Punto verde: generating (parpadea cuando RIFF está activo)
    if riff_on and b:
        t.append("● ", style=f"bold {RIFF_COLOR}")
    else:
        t.append("○ ", style=f"{LABEL_DIM}")
    t.append("generating", style=META_VAL if riff_on else META_KEY)

    return Group(t, Rule(style=SEP_COLOR))


def _controls_bar(snap: dict) -> Text:
    """Atajos de teclado estilo kbd + cursor parpadeante."""
    cursor = "▌" if _blink() else " "

    t = Text()
    t.append("  ")

    def key(label: str) -> None:
        t.append("[",     style=SEP_COLOR)
        t.append(label,   style=META_VAL)
        t.append("]",     style=SEP_COLOR)

    key("space")
    t.append(" mute riff", style=META_KEY)
    t.append("   ",        style=META_KEY)
    key("m")
    t.append(" change mode", style=META_KEY)
    t.append("   ",          style=META_KEY)
    key("q")
    t.append(" quit",       style=META_KEY)
    t.append(f"  {cursor}", style=f"bold {YOU_COLOR}")

    return t


# ── Composición del layout completo ──────────────────────────────────────────

def build_layout(snap: dict, term_height: int, term_width: int) -> Layout:
    """
    Construye el layout completo adaptado al terminal.

    Slots fijos: header(7) + sep1(1) + sep2(1) + status(2) + controls(2) + margin(1) = 14
    Paneles you/riff con ratio=1 — rich los adapta automáticamente al espacio restante,
    garantizando que el layout NUNCA excede el alto real del terminal.

    Para 42 filas: cada panel ocupa (42-14)/2 = 14 filas ✓
    """
    wf_h, show_chords, n_bars = _panel_content_params(term_height, term_width)

    layout = Layout()
    layout.split_column(
        Layout(name="header",   size=7),
        Layout(name="sep1",     size=1),
        Layout(name="you",      ratio=1),
        Layout(name="sep2",     size=1),
        Layout(name="riff",     ratio=1),
        Layout(name="status",   size=2),
        Layout(name="controls", size=2),
        Layout(name="margin",   size=1),
    )

    layout["header"].update(_header_panel())
    layout["sep1"].update(_separator())
    layout["you"].update(_you_panel(snap, wf_h, show_chords, n_bars))
    layout["sep2"].update(_separator())
    layout["riff"].update(_riff_panel(snap, wf_h, show_chords, n_bars))
    layout["status"].update(_status_bar(snap))
    layout["controls"].update(_controls_bar(snap))
    layout["margin"].update(Text(""))

    return layout


# ── Teclado (tty raw + select, sin dependencias extra) ────────────────────────

class KeyboardHandler:
    """
    Lectura de teclas no bloqueante via modo raw POSIX + select.
    Funciona en macOS y Linux sin permisos especiales.
    Se desactiva en silencio si stdin no es un TTY.
    """

    def __init__(self, state) -> None:
        self.state     = state
        self._thread:   Optional[threading.Thread] = None
        self._original: Optional[list]             = None

    def start(self) -> None:
        if not sys.stdin.isatty():
            return
        try:
            self._original = termios.tcgetattr(sys.stdin.fileno())
            tty.setcbreak(sys.stdin.fileno(), termios.TCSANOW)
        except Exception:
            return
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="riff-keyboard",
        )
        self._thread.start()

    def stop(self) -> None:
        if self._original is not None:
            try:
                termios.tcsetattr(
                    sys.stdin.fileno(), termios.TCSADRAIN, self._original,
                )
            except Exception:
                pass

    def _loop(self) -> None:
        while self.state.snapshot()["running"]:
            try:
                r, _, _ = select.select([sys.stdin], [], [], 0.1)
                if r:
                    self._handle(sys.stdin.read(1))
            except Exception:
                break

    def _handle(self, ch: str) -> None:
        if ch == " ":
            self.state.toggle_mute()
        elif ch in ("m", "M"):
            self.state.next_mode()
        elif ch in ("q", "Q", "\x03", "\x04"):
            self.state.update(running=False)


# ── Controlador principal del display ────────────────────────────────────────

class RiffDisplay:
    """
    Arranca el Live display a pantalla completa y el handler de teclado.

    Al iniciar:
      1. Envía \033[9;1t  — escape XTerm que maximiza la ventana en iTerm2 /
         Terminal.app / la mayoría de emuladores compatibles con xterm.
      2. Espera 150 ms para que el OS procese el redimensionado.
      3. Lee console.size (misma fuente que usa rich.Layout internamente)
         para que el cálculo de n_bars y wf_height estén siempre sincronizados.
    """

    def __init__(self, state) -> None:
        self.state    = state
        self._console = Console()
        self._kb      = KeyboardHandler(state)

    def _size(self) -> tuple[int, int]:
        """Lee el tamaño real del terminal. os.get_terminal_size() es la fuente
        primaria (TIOCGWINSZ); console.size es el fallback."""
        try:
            ts = os.get_terminal_size()
            return ts.lines, ts.columns
        except OSError:
            return self._console.size.height, self._console.size.width

    def run(self) -> None:
        # ── Maximizar ventana de terminal (iTerm2, Terminal.app, xterm…) ──────
        if sys.stdout.isatty():
            sys.stdout.write("\033[9;1t")   # XTerm: maximize window
            sys.stdout.flush()
            time.sleep(0.15)                # esperar a que el OS redimensione

        self._kb.start()
        try:
            h, w = self._size()
            with Live(
                build_layout(self.state.snapshot(), h, w),
                console=self._console,
                refresh_per_second=REFRESH_RATE,
                screen=True,
            ) as live:
                while self.state.snapshot()["running"]:
                    try:
                        h, w = self._size()
                        live.update(build_layout(self.state.snapshot(), h, w))
                    except Exception:
                        pass
                    time.sleep(1.0 / REFRESH_RATE)
        finally:
            self._kb.stop()

    def _term_height(self) -> int:
        return self._console.size.height
