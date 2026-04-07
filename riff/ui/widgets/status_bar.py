"""Status bar widget — device, listening, mode indicators."""

from __future__ import annotations

import time

from rich.text import Text
from textual.widgets import Static

from riff.ui.palette import (
    LABEL_DIM,
    META_KEY,
    META_VAL,
    RIFF_COLOR,
    YOU_COLOR,
)


class StatusBar(Static):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._snap: dict = {}

    def update_from_snapshot(self, snap: dict) -> None:
        self._snap = snap
        self.refresh()

    def render(self) -> Text:
        snap = self._snap
        device = snap.get("device_name", "Detecting...")
        active = snap.get("note", "—") != "—"
        mode = snap.get("mode", "FREE")
        b = int(time.time() * 3) % 2 == 0

        t = Text()
        t.append("  ")
        t.append("● ", style=f"bold {RIFF_COLOR}")
        t.append(f"{device}   ", style=META_VAL)

        if active and b:
            t.append("● ", style=f"bold {YOU_COLOR}")
        else:
            t.append("○ ", style=f"{LABEL_DIM}")
        t.append("listening   ", style=META_VAL if active else META_KEY)

        mode_display = mode.replace("_", " ")
        t.append("● ", style=f"bold {RIFF_COLOR}")
        t.append(mode_display.lower(), style=META_VAL)

        return t
