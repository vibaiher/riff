"""YOU panel widget — note, waveform, chords, meta."""

from __future__ import annotations

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.widgets import Static

from riff.ui.palette import (
    BAR_EMPTY,
    LABEL_DIM,
    META_KEY,
    META_VAL,
    YOU_BG,
    YOU_BORDER,
    YOU_COLOR,
    note_color,
)
from riff.ui.waveform import render_vbars


class YouPanel(Static):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._snap: dict = {}

    def update_from_snapshot(self, snap: dict) -> None:
        self._snap = snap
        self.refresh()

    def render(self) -> Panel:
        snap = self._snap
        note = snap.get("note", "—")
        octave = snap.get("octave", 4)
        db = snap.get("db", -80.0)
        bpm = snap.get("bpm", 0.0)
        latency = snap.get("latency_ms", 0.0)
        chords = snap.get("chords", [])
        wf = snap.get("waveform", [])

        size = self.size
        n_bars = max(8, (size.width - 4 + 1) // 2)
        content_h = max(3, size.height - 2)
        wf_h = max(2, content_h - 3)

        parts: list = [
            _note_bar_row(note, octave, db),
            _waveform_block(wf, YOU_COLOR, wf_h, n_bars),
        ]
        if content_h >= 6:
            parts.append(_chord_pills(chords))
        bpm_str = f"♩ {bpm:.0f}" if bpm > 0 else "—"
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


def _note_bar_row(note: str, octave: int, db: float) -> Table:
    t = Table.grid(expand=True, padding=(0, 1, 0, 0))
    t.add_column(width=7, no_wrap=True)
    t.add_column(ratio=1, no_wrap=True)
    t.add_column(width=12, no_wrap=True)
    nc = note_color(note)
    badge = f" {note}{octave if note != '—' else ''}"
    clamped = max(-80.0, min(0.0, db))
    filled = int((clamped + 80.0) / 80.0 * 30)
    bar = Text()
    bar.append("█" * filled, style=YOU_COLOR)
    bar.append("░" * (30 - filled), style=BAR_EMPTY)
    t.add_row(
        Text(f"{badge:<7}", style=f"bold {nc}"),
        bar,
        Text(f" {db:+.1f} dB ", style=META_VAL),
    )
    return t


def _waveform_block(data: list[float], color: str, height: int, n_bars: int) -> Text:
    wf = render_vbars(data, n_bars=n_bars, height=height)
    t = Text()
    for i, line in enumerate(wf.split("\n")):
        suffix = "\n" if i < len(wf.split("\n")) - 1 else ""
        t.append(f"  {line}{suffix}", style=color)
    return t


def _chord_pills(chords: list[str]) -> Text:
    t = Text()
    t.append("  ")
    for i, chord in enumerate(chords[:4]):
        if i:
            t.append("  ")
        style = f"bold {YOU_COLOR}" if i == 0 else f"{LABEL_DIM}"
        t.append(f"[{chord}]", style=style)
    return t


def _meta_line(items: list[tuple[str, str]]) -> Text:
    t = Text()
    t.append("  ")
    for i, (k, v) in enumerate(items):
        if i:
            t.append("  ·  ", style=META_KEY)
        t.append(f"{k}: ", style=META_KEY)
        t.append(v, style=META_VAL)
    return t
