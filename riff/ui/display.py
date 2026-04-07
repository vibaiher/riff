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
import threading
import time
import tty

from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from .palette import (
    YOU_COLOR, YOU_BORDER, YOU_BG,
    RIFF_COLOR, RIFF_BORDER, RIFF_BG,
    LABEL_DIM, META_KEY, META_VAL, BAR_EMPTY, SEP_COLOR,
    REFRESH_RATE, LOGO, note_color,
)
from .waveform import render_vbars


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
    fixed = 7 + 1 + 1 + 2 + 2 + 1  # = 14
    available = max(10, term_height - fixed)
    panel_rows = max(5, available // 2)
    content_h = panel_rows - 2  # descontar bordes Panel

    if content_h >= 6:
        wf_h = content_h - 3  # nota + wf + chords + meta
        show_chords = True
    else:
        wf_h = max(2, content_h - 2)  # nota + wf + meta
        show_chords = False

    avail_w = max(10, term_width - 4)
    n_bars = max(8, (avail_w + 1) // 2)

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
    t.add_column(width=7, no_wrap=True)  # badge de nota
    t.add_column(ratio=1, no_wrap=True)  # barra de nivel (rellena el espacio)
    t.add_column(width=12, no_wrap=True)  # valor dB

    nc = note_color(note)
    badge = f" {note}{octave if note != '—' else ''}"

    clamped = max(-80.0, min(0.0, db))
    filled = int((clamped + 80.0) / 80.0 * 30)
    bar = Text()
    bar.append("█" * filled, style=panel_color)
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
    wf = render_vbars(data, n_bars=n_bars, height=height)
    lines = wf.split("\n")
    t = Text()
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
        t.append(v, style=META_VAL)
    return t


# ── Paneles principales ───────────────────────────────────────────────────────


def _you_panel(snap: dict, wf_height: int, show_chords: bool, n_bars: int) -> Panel:
    note = snap["note"]
    octave = snap["octave"]
    db = snap["db"]
    bpm = snap["bpm"]
    latency = snap["latency_ms"]
    chords = snap["chords"]
    wf = snap["waveform"]

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


_MODE_TITLES: dict[str, str] = {
    "FREE": "RIFF · FREE",
    "COMPOSE": "RIFF · COMPOSE",
}


def _riff_panel(snap: dict, wf_height: int, show_chords: bool, n_bars: int) -> Panel:
    mode = snap.get("mode", "FREE")
    title = _MODE_TITLES.get(mode, f"RIFF · {mode}")

    parts = _mode_content(mode, snap, wf_height, n_bars, show_chords)

    return Panel(
        Group(*parts),
        title=f"[bold {LABEL_DIM}]  {title}  [/bold {LABEL_DIM}]",
        title_align="left",
        border_style=RIFF_BORDER,
        box=box.ROUNDED,
        style=f"on {RIFF_BG}",
        padding=(0, 0),
    )


def _mode_content(
    mode: str, snap: dict, wf_height: int, n_bars: int, show_chords: bool = True
) -> list:
    if mode == "FREE":
        return _free_mode_content(snap, wf_height, n_bars, show_chords)
    if mode == "COMPOSE":
        return _compose_mode_content(snap, wf_height, n_bars)
    return _free_mode_content(snap, wf_height, n_bars, show_chords)


def _free_mode_content(snap: dict, wf_height: int, n_bars: int, show_chords: bool = True) -> list:
    """FREE mode — just show what the user is playing, nothing more."""
    note = snap.get("note", "—")
    bpm = snap.get("bpm", 0.0)

    t = Text()
    t.append("\n")
    if note != "—":
        t.append(f"  {note}{snap.get('octave', 4)}", style=f"bold {RIFF_COLOR}")
        if bpm > 0:
            t.append(f"   ♩ {bpm:.0f}", style=META_VAL)
    else:
        t.append("  play something...", style=LABEL_DIM)

    for _ in range(wf_height):
        t.append("\n")

    return [t]


def _compose_mode_content(snap: dict, wf_height: int, n_bars: int) -> list:
    """COMPOSE mode — accumulate chords, generate melodies."""
    captured = snap.get("captured_chords", [])
    gen_status = snap.get("gen_status", "")
    engine = snap.get("engine", "phrase")
    phase = snap.get("compose_phase", "")
    attached = snap.get("attached_file", "")
    filename = os.path.basename(attached) if attached else ""

    t = Text()

    # Line 1: file info or captured progression
    t.append("\n")
    if phase == "listening" and filename:
        t.append("  ♫ playing ", style=f"bold {RIFF_COLOR}")
        t.append(filename, style=META_VAL)
        t.append("  — detecting chords...", style=META_KEY)
    elif captured:
        t.append("  chords: ", style=META_KEY)
        visible = captured[-12:]
        if len(captured) > 12:
            t.append("... ", style=LABEL_DIM)
        for i, ch in enumerate(visible):
            if i > 0:
                t.append(" → ", style=LABEL_DIM)
            t.append(ch, style=f"bold {RIFF_COLOR}")
    elif filename:
        t.append(f"  ♫ {filename}", style=META_VAL)
    else:
        t.append("  play to capture chords — ", style=META_KEY)
        t.append("[g]", style=META_VAL)
        t.append(" generate  ", style=META_KEY)
        t.append("[c]", style=META_VAL)
        t.append(" clear", style=META_KEY)

    # Line 2: status
    t.append("\n")
    if gen_status:
        t.append(f"  {gen_status}", style=f"bold {RIFF_COLOR}")
        if gen_status == "playing":
            count = snap.get("gen_note_count", 0)
            dur = snap.get("gen_duration", 0.0)
            t.append(f"  ({count} notes, {dur:.1f}s)", style=META_VAL)
    elif phase == "listening":
        if captured:
            t.append(f"  {len(captured)} chords detected so far", style=META_KEY)
        else:
            t.append("  listening...", style=LABEL_DIM)
    elif captured:
        t.append(f"  {len(captured)} chords captured — press ", style=META_KEY)
        t.append("[g]", style=META_VAL)
        t.append(f" to generate ({engine})", style=META_KEY)
    else:
        t.append("  listening...", style=LABEL_DIM)

    # Fill remaining height
    remaining = max(0, wf_height - 1)
    for _ in range(remaining):
        t.append("\n")

    # Meta line
    meta_items: list[tuple[str, str]] = [("engine", engine)]
    if filename:
        meta_items.append(("file", filename))
    if captured:
        meta_items.append(("captured", str(len(captured))))
    if gen_status:
        meta_items.append(("status", gen_status))

    return [t, _meta_line(meta_items)]


# ── Barra de estado y controles ───────────────────────────────────────────────


def _status_bar(snap: dict) -> Group:
    """
    Dos filas para el slot status(size=2):
      fila 1 → indicadores de dispositivo, señal y modo
      fila 2 → regla separadora (visual breathing room antes de controls)
    """
    device = snap["device_name"]
    active = snap["note"] != "—"
    mode = snap.get("mode", "FREE")
    b = _blink()

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

    # Modo actual
    mode_display = mode.replace("_", " ")
    t.append("● ", style=f"bold {RIFF_COLOR}")
    t.append(mode_display.lower(), style=META_VAL)

    return Group(t, Rule(style=SEP_COLOR))


def _controls_bar(snap: dict) -> Text:
    """Atajos de teclado estilo kbd + cursor parpadeante."""
    cursor = "▌" if _blink() else " "

    if snap.get("input_mode"):
        return _input_prompt_bar(snap)

    t = Text()
    t.append("  ")

    def key(label: str) -> None:
        t.append("[", style=SEP_COLOR)
        t.append(label, style=META_VAL)
        t.append("]", style=SEP_COLOR)

    phase = snap.get("compose_phase", "")

    if phase == "loaded":
        key("l")
        t.append(" replay", style=META_KEY)
        t.append("  ", style=META_KEY)
        key("g")
        t.append(" generate", style=META_KEY)
        t.append("  ", style=META_KEY)
        key("c")
        t.append(" clear", style=META_KEY)
    elif phase == "listening":
        t.append(" listening...", style=f"bold {RIFF_COLOR}")
    elif phase == "generated":
        key("l")
        t.append(" listen", style=META_KEY)
        t.append("  ", style=META_KEY)
        key("s")
        t.append(" save", style=META_KEY)
        t.append("  ", style=META_KEY)
        key("p")
        t.append(" play mix", style=META_KEY)
        t.append("  ", style=META_KEY)
        key("g")
        t.append(" regenerate", style=META_KEY)
        t.append("  ", style=META_KEY)
        key("c")
        t.append(" clear", style=META_KEY)
    else:
        key("space")
        t.append(" pause", style=META_KEY)
        t.append("  ", style=META_KEY)
        key("f")
        t.append(" load", style=META_KEY)
        t.append("  ", style=META_KEY)
        key("g")
        t.append(" generate", style=META_KEY)
        t.append("  ", style=META_KEY)
        key("c")
        t.append(" clear", style=META_KEY)
        t.append("  ", style=META_KEY)
        key("m")
        t.append(" mode", style=META_KEY)

    t.append("  ", style=META_KEY)
    key("q")
    t.append(" quit", style=META_KEY)
    t.append(f"  {cursor}", style=f"bold {YOU_COLOR}")

    return t


def _input_prompt_bar(snap: dict) -> Text:
    """Show file path input with blinking cursor."""
    cursor = "▌" if _blink() else " "
    buf = snap.get("input_buffer", "")

    t = Text()
    t.append("  file: ", style=f"bold {RIFF_COLOR}")
    t.append(buf, style=META_VAL)
    t.append(cursor, style=f"bold {YOU_COLOR}")
    t.append("   ", style=META_KEY)
    t.append("[tab]", style=SEP_COLOR)
    t.append(" complete  ", style=META_KEY)
    t.append("[enter]", style=SEP_COLOR)
    t.append(" load  ", style=META_KEY)
    t.append("[esc]", style=SEP_COLOR)
    t.append(" cancel", style=META_KEY)

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
        Layout(name="header", size=7),
        Layout(name="sep1", size=1),
        Layout(name="you", ratio=1),
        Layout(name="sep2", size=1),
        Layout(name="riff", ratio=1),
        Layout(name="status", size=2),
        Layout(name="controls", size=2),
        Layout(name="margin", size=1),
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
        from riff.core.commands import ComposeCommands
        self.state = state
        self._thread: threading.Thread | None = None
        self._original: list | None = None
        self._cmds = ComposeCommands(state)

    def start(self) -> None:
        if not sys.stdin.isatty():
            return
        try:
            self._original = termios.tcgetattr(sys.stdin.fileno())
            tty.setcbreak(sys.stdin.fileno(), termios.TCSANOW)
        except Exception:
            return
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="riff-keyboard",
        )
        self._thread.start()

    def stop(self) -> None:
        if self._original is not None:
            try:
                termios.tcsetattr(
                    sys.stdin.fileno(),
                    termios.TCSADRAIN,
                    self._original,
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
        if self.state.snapshot()["input_mode"]:
            self._handle_input(ch)
            return
        if ch == " ":
            self.state.toggle_mute()
        elif ch in ("m", "M"):
            self.state.next_mode()
        elif ch in ("t", "T"):
            self.state.next_timbre()
        elif ch in ("e", "E"):
            self.state.next_engine()
        elif ch in ("q", "Q", "\x03", "\x04"):
            self.state.update(running=False)
        elif ch == "[":
            self.state.speed_down()
        elif ch == "]":
            self.state.speed_up()
        elif self.state.snapshot()["mode"] == "COMPOSE":
            self._handle_compose(ch)

    @property
    def _source_type(self):
        return self._cmds.source_type

    @property
    def _source_audio(self):
        return self._cmds.source_audio

    @property
    def _generated_audio(self):
        return self._cmds.generated_audio

    @property
    def _source_song(self):
        return self._cmds._source_song

    @_source_song.setter
    def _source_song(self, v):
        self._cmds._source_song = v

    @property
    def _timed_chords(self):
        return self._cmds._timed_chords

    @_timed_chords.setter
    def _timed_chords(self, v):
        self._cmds._timed_chords = v

    @_source_type.setter
    def _source_type(self, v):
        self._cmds.source_type = v

    @_source_audio.setter
    def _source_audio(self, v):
        self._cmds.source_audio = v

    @_generated_audio.setter
    def _generated_audio(self, v):
        self._cmds.generated_audio = v

    @property
    def _save_dir(self):
        return self._cmds._save_dir

    @_save_dir.setter
    def _save_dir(self, v):
        self._cmds._save_dir = v

    def _handle_compose(self, ch: str) -> None:
        phase = self.state.snapshot()["compose_phase"]
        if ch in ("f", "F"):
            self.state.start_input("file")
        elif ch in ("c", "C"):
            self._cmds.clear()
        elif phase == "":
            if ch in ("g", "G"):
                self._cmds.generate()
        elif phase in ("loaded", "generated"):
            if ch in ("l", "L"):
                self._cmds.listen_source()
            elif ch in ("g", "G"):
                if self._cmds.source_type == "midi" and self._cmds._timed_chords:
                    self._cmds.generate_from_file()
                else:
                    self._cmds.generate()
            elif phase == "generated" and ch in ("s", "S"):
                self._cmds.save()
            elif phase == "generated" and ch in ("p", "P"):
                self._cmds.play_mix()

    def _handle_input(self, ch: str) -> None:
        if ch == "\x1b":  # Escape
            self.state.cancel_input()
        elif ch == "\n":  # Enter
            self._confirm_file_input()
        elif ch == "\t":  # Tab
            self._tab_complete()
        elif ch == "\x7f":  # Backspace
            current = self.state.snapshot()["input_buffer"]
            self.state.update(input_buffer=current[:-1])
        elif ch.isprintable():
            current = self.state.snapshot()["input_buffer"]
            self.state.update(input_buffer=current + ch)

    def _tab_complete(self) -> None:
        from .file_input import complete_path
        current = self.state.snapshot()["input_buffer"]
        matches = complete_path(current)
        if len(matches) == 1:
            self.state.update(input_buffer=matches[0])
        elif matches:
            prefix = os.path.commonprefix(matches)
            if prefix:
                self.state.update(input_buffer=prefix)

    def _confirm_file_input(self) -> None:
        path = self.state.confirm_input()
        self._confirm_file_input_path(path)

    def _confirm_file_input_path(self, path: str) -> None:
        self._cmds.load_file(path)


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
        self.state = state
        self._console = Console()
        self._kb = KeyboardHandler(state)

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
            sys.stdout.write("\033[9;1t")  # XTerm: maximize window
            sys.stdout.flush()
            time.sleep(0.15)  # esperar a que el OS redimensione

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
