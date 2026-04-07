"""Welcome screen — mode selector with animated waveforms."""

from __future__ import annotations

import math
import os
import queue
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
from rich.text import Text

from riff.core.state import MODES
from riff.ui.palette import (
    YOU_COLOR, YOU_BORDER, RIFF_COLOR, RIFF_BORDER,
    LABEL_DIM, META_VAL, META_KEY, SEP_COLOR, LOGO,
)

_MODE_DESCRIPTIONS: dict[str, str] = {
    "FREE": "see what you play — pitch, tempo, dynamics",
    "COMPOSE": "accumulate chords and generate melodies",
}


class WelcomeScreen:
    def __init__(self) -> None:
        self._index = 0

    def move_down(self) -> None:
        self._index = (self._index + 1) % len(MODES)

    def move_up(self) -> None:
        self._index = (self._index - 1) % len(MODES)

    def selected_mode(self) -> str:
        return MODES[self._index]

    def confirm_selection(self) -> str:
        return self.selected_mode()


# Lazy-loaded raw audio from the bundled MIDI
_audio: "numpy.ndarray | None" = None
_audio_duration: float = 310.0
_SAMPLE_RATE = 44100
_WAVEFORM_WINDOW = _SAMPLE_RATE // 3


def _load_audio():
    """Load Zombie MIDI and synthesize to raw audio (cached)."""
    global _audio, _audio_duration

    if _audio is not None:
        return _audio

    import pathlib
    import numpy as np
    from riff.audio.song import SongData

    midi_path = pathlib.Path(__file__).parent.parent / "assets" / "zombie.mid"
    song = SongData.from_file(str(midi_path))
    audio = song.render_audio()
    _audio_duration = song.total_duration
    _audio = np.abs(audio) if len(audio) > 0 else np.zeros(1, dtype=np.float32)
    return _audio


def fake_waveform(n_bars: int = 28, t: float = 0.0) -> list[float]:
    """Read a chunk of the real audio at position t, like the main app does."""
    import numpy as np

    audio = _load_audio()
    position = t % _audio_duration
    center = int(position * _SAMPLE_RATE)
    start = max(0, center - _WAVEFORM_WINDOW // 2)
    end = min(len(audio), start + _WAVEFORM_WINDOW)
    chunk = audio[start:end]

    if len(chunk) == 0:
        return [0.0] * n_bars

    segments = np.array_split(chunk, n_bars)
    return [float(np.max(s)) if len(s) > 0 else 0.0 for s in segments]


def _mode_selector(selected_index: int) -> Text:
    """Render the mode selector list."""
    t = Text()
    for i, mode in enumerate(MODES):
        label = mode.replace("_", " ")
        desc = _MODE_DESCRIPTIONS.get(mode, "")
        if i == selected_index:
            t.append("  ▸ ", style=f"bold {RIFF_COLOR}")
            t.append(f"{label:<15}", style=f"bold {RIFF_COLOR}")
            t.append(f" {desc}", style=META_VAL)
        else:
            t.append("    ", style=LABEL_DIM)
            t.append(f"{label:<15}", style=LABEL_DIM)
            t.append(f" {desc}", style=META_KEY)
        t.append("\n")
    return t


def _waveform_block(data: list[float], color: str, height: int, n_bars: int) -> Text:
    """Render animated fake waveform bars."""
    from .waveform import render_vbars
    wf = render_vbars(data, n_bars=n_bars, height=height)
    lines = wf.split("\n")
    t = Text()
    for i, line in enumerate(lines):
        suffix = "\n" if i < len(lines) - 1 else ""
        t.append(f"  {line}{suffix}", style=color)
    return t


def build_welcome_layout(
    selected_index: int,
    term_height: int,
    term_width: int,
    t: float = 0.0,
) -> Layout:
    """Build the full welcome screen layout."""
    avail_w = max(10, term_width - 4)
    n_bars = max(8, (avail_w + 1) // 2)

    # Waveform height: fill remaining space
    fixed = 9 + 8 + 2 + 1
    wf_panel_h = max(5, term_height - fixed)
    wf_content_h = max(3, wf_panel_h - 2)

    wf_data = fake_waveform(n_bars=n_bars, t=t)

    # Logo
    logo = Text(LOGO, style=f"bold {YOU_COLOR}")
    subtitle = Text(
        "real-time intelligent frequency follower",
        style=META_VAL,
        justify="center",
    )
    header = Group(
        Text(""),
        Align.center(logo),
        Align.center(subtitle),
    )

    # Mode selector
    selector = _mode_selector(selected_index)
    modes_panel = Panel(
        Align.center(selector),
        border_style=SEP_COLOR,
        box=box.ROUNDED,
        padding=(1, 2),
    )

    # Single animated waveform
    wf_block = _waveform_block(wf_data, YOU_COLOR, wf_content_h, n_bars)
    wf_panel = Panel(
        wf_block,
        border_style=YOU_BORDER,
        box=box.ROUNDED,
        style=f"on #0e0a17",
        padding=(0, 0),
    )

    # Controls
    controls = Text()
    controls.append("  ")
    controls.append("[", style=SEP_COLOR)
    controls.append("↑↓", style=META_VAL)
    controls.append("]", style=SEP_COLOR)
    controls.append(" select", style=META_KEY)
    controls.append("  ", style=META_KEY)
    controls.append("[", style=SEP_COLOR)
    controls.append("enter", style=META_VAL)
    controls.append("]", style=SEP_COLOR)
    controls.append(" start", style=META_KEY)
    controls.append("  ", style=META_KEY)
    controls.append("[", style=SEP_COLOR)
    controls.append("q", style=META_VAL)
    controls.append("]", style=SEP_COLOR)
    controls.append(" quit", style=META_KEY)

    # Compose layout
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=9),
        Layout(name="modes", size=8),
        Layout(name="waveform", ratio=1),
        Layout(name="controls", size=2),
        Layout(name="margin", size=1),
    )

    layout["header"].update(header)
    layout["modes"].update(modes_panel)
    layout["waveform"].update(wf_panel)
    layout["controls"].update(controls)
    layout["margin"].update(Text(""))

    return layout


def _key_reader_loop(key_queue: queue.Queue, stop_event: threading.Event) -> None:
    """Background thread: read keys via select + os.read, push to queue."""
    fd = sys.stdin.fileno()
    while not stop_event.is_set():
        try:
            r, _, _ = select.select([sys.stdin], [], [], 0.05)
            if not r:
                continue
            data = os.read(fd, 32)
            if not data:
                continue
            if b"\x1b[A" in data:
                key_queue.put("up")
            elif b"\x1b[B" in data:
                key_queue.put("down")
            elif data[0:1] == b"\x1b":
                key_queue.put("esc")
            else:
                key_queue.put(data[:1].decode("utf-8", errors="ignore"))
        except Exception:
            break


def run_welcome() -> str | None:
    """Show the welcome screen. Returns selected mode name, or None if user quits."""
    if not sys.stdin.isatty():
        return MODES[0]

    screen = WelcomeScreen()
    console = Console()

    # Maximize terminal window
    if sys.stdout.isatty():
        sys.stdout.write("\033[9;1t")
        sys.stdout.flush()
        time.sleep(0.15)

    original_attrs = None
    try:
        original_attrs = termios.tcgetattr(sys.stdin.fileno())
        tty.setcbreak(sys.stdin.fileno(), termios.TCSANOW)
    except Exception:
        return MODES[0]

    key_q: queue.Queue = queue.Queue()
    stop = threading.Event()
    reader = threading.Thread(target=_key_reader_loop, args=(key_q, stop), daemon=True)
    reader.start()

    start = time.time()
    try:
        try:
            ts = os.get_terminal_size()
            h, w = ts.lines, ts.columns
        except OSError:
            h, w = console.size.height, console.size.width

        with Live(
            build_welcome_layout(screen._index, h, w, 0.0),
            console=console,
            refresh_per_second=20,
            screen=True,
        ) as live:
            while True:
                t = time.time() - start
                try:
                    ts = os.get_terminal_size()
                    h, w = ts.lines, ts.columns
                except OSError:
                    h, w = console.size.height, console.size.width

                live.update(build_welcome_layout(screen._index, h, w, t))

                try:
                    key = key_q.get_nowait()
                except queue.Empty:
                    key = None

                if key == "up" or key == "k":
                    screen.move_up()
                elif key == "down" or key == "j":
                    screen.move_down()
                elif key == "\n" or key == "\r":
                    return screen.confirm_selection()
                elif key in ("q", "Q", "\x03", "\x04"):
                    return None

                time.sleep(1.0 / 20)

    finally:
        stop.set()
        if original_attrs is not None:
            try:
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, original_attrs)
            except Exception:
                pass
