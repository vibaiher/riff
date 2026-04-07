"""Waveform display widget for Textual."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from riff.ui.waveform import render_vbars


class WaveformDisplay(Static):
    def __init__(self, color: str = "#b388ff", **kwargs) -> None:
        super().__init__(**kwargs)
        self._color = color
        self._data: list[float] = []

    def update_data(self, data: list[float]) -> None:
        self._data = data
        self.refresh()

    def render(self) -> Text:
        size = self.size
        n_bars = max(8, (size.width - 2 + 1) // 2)
        height = max(2, size.height)
        wf = render_vbars(self._data, n_bars=n_bars, height=height)
        t = Text()
        for i, line in enumerate(wf.split("\n")):
            if i > 0:
                t.append("\n")
            t.append(line, style=self._color)
        return t
