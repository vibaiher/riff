"""RIFF panel widget — mode-aware bottom panel."""

from __future__ import annotations

import os

from rich import box
from rich.console import Group
from rich.text import Text
from textual.widgets import Static

from riff.ui.palette import (
    LABEL_DIM,
    META_KEY,
    META_VAL,
    RIFF_BG,
    RIFF_BORDER,
    RIFF_COLOR,
)

_MODE_TITLES: dict[str, str] = {
    "FREE": "RIFF · FREE",
    "COMPOSE": "RIFF · COMPOSE",
}


class RiffPanel(Static):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._snap: dict = {}

    def update_from_snapshot(self, snap: dict) -> None:
        self._snap = snap
        self.refresh()

    def render(self):
        from rich.panel import Panel

        snap = self._snap
        mode = snap.get("mode", "FREE")
        title = _MODE_TITLES.get(mode, f"RIFF · {mode}")

        size = self.size
        content_h = max(3, size.height - 2)
        wf_h = max(2, content_h - 2)

        if mode == "COMPOSE":
            parts = _compose_content(snap, wf_h)
        else:
            parts = _free_content(snap, wf_h)

        return Panel(
            Group(*parts),
            title=f"[bold {LABEL_DIM}]  {title}  [/bold {LABEL_DIM}]",
            title_align="left",
            border_style=RIFF_BORDER,
            box=box.ROUNDED,
            style=f"on {RIFF_BG}",
            padding=(0, 0),
        )


def _free_content(snap: dict, wf_height: int) -> list:
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


def _compose_content(snap: dict, wf_height: int) -> list:
    captured = snap.get("captured_chords", [])
    gen_status = snap.get("gen_status", "")
    engine = snap.get("engine", "phrase")
    phase = snap.get("compose_phase", "")
    attached = snap.get("attached_file", "")
    filename = os.path.basename(attached) if attached else ""

    t = Text()
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

    remaining = max(0, wf_height - 1)
    for _ in range(remaining):
        t.append("\n")

    meta_items: list[tuple[str, str]] = [("engine", engine)]
    if filename:
        meta_items.append(("file", filename))
    if captured:
        meta_items.append(("captured", str(len(captured))))
    if gen_status:
        meta_items.append(("status", gen_status))

    meta = Text()
    meta.append("  ")
    for i, (k, v) in enumerate(meta_items):
        if i:
            meta.append("  ·  ", style=META_KEY)
        meta.append(f"{k}: ", style=META_KEY)
        meta.append(v, style=META_VAL)

    return [t, meta]
