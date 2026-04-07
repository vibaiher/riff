"""Controls bar widget — context-aware keyboard hints."""

from __future__ import annotations

import time

from rich.text import Text
from textual.widgets import Static

from riff.ui.palette import (
    YOU_COLOR, RIFF_COLOR, SEP_COLOR, META_KEY, META_VAL,
)


class ControlsBar(Static):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._snap: dict = {}

    def update_from_snapshot(self, snap: dict) -> None:
        self._snap = snap
        self.refresh()

    def render(self) -> Text:
        snap = self._snap
        cursor = "▌" if int(time.time() * 3) % 2 == 0 else " "
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
