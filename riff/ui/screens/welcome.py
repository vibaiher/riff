"""Textual welcome screen — mode selector with animated waveform."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Middle
from textual.screen import Screen
from textual.widgets import Static

from riff.core.state import MODES
from riff.ui.palette import (
    LOGO, YOU_COLOR, RIFF_COLOR, RIFF_BORDER,
    LABEL_DIM, META_VAL, META_KEY, SEP_COLOR,
)
from riff.core.welcome_model import fake_waveform, WelcomeModel
from riff.ui.widgets.waveform_display import WaveformDisplay

_MODE_DESCRIPTIONS: dict[str, str] = {
    "FREE": "see what you play — pitch, tempo, dynamics",
    "COMPOSE": "accumulate chords and generate melodies",
}


class ModeSelector(Static):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._selected = 0

    @property
    def selected_index(self) -> int:
        return self._selected

    @selected_index.setter
    def selected_index(self, val: int) -> None:
        self._selected = val % len(MODES)
        self.refresh()

    def render(self) -> Text:
        t = Text()
        for i, mode in enumerate(MODES):
            label = mode.replace("_", " ")
            desc = _MODE_DESCRIPTIONS.get(mode, "")
            if i == self._selected:
                t.append("  ▸ ", style=f"bold {RIFF_COLOR}")
                t.append(f"{label:<15}", style=f"bold {RIFF_COLOR}")
                t.append(f" {desc}", style=META_VAL)
            else:
                t.append("    ", style=LABEL_DIM)
                t.append(f"{label:<15}", style=LABEL_DIM)
                t.append(f" {desc}", style=META_KEY)
            if i < len(MODES) - 1:
                t.append("\n")
        return t


class WelcomeScreen(Screen):
    BINDINGS = [
        Binding("down,j", "move_down", "Down", show=False),
        Binding("up,k", "move_up", "Up", show=False),
        Binding("enter", "confirm", "Start", show=False),
        Binding("q", "quit", "Quit", show=False),
    ]

    CSS = """
    WelcomeScreen {
        align: center middle;
        layout: vertical;
    }
    #logo {
        text-align: center;
        width: 100%;
        content-align: center middle;
        color: #b388ff;
        text-style: bold;
        margin-bottom: 1;
    }
    #subtitle {
        text-align: center;
        width: 100%;
        content-align: center middle;
        color: #666666;
        margin-bottom: 1;
    }
    #modes {
        width: auto;
        height: auto;
        padding: 1 2;
        border: round #2a2a2a;
        margin-bottom: 1;
    }
    #waveform {
        width: 100%;
        height: 1fr;
        border: round #7c4dff;
        background: #0e0a17;
    }
    #controls {
        width: 100%;
        height: 1;
        color: #444444;
        text-align: center;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._model = WelcomeModel()

    def compose(self) -> ComposeResult:
        yield Static(LOGO, id="logo")
        yield Static("real-time intelligent frequency follower", id="subtitle")
        with Center():
            yield ModeSelector(id="modes")
        yield WaveformDisplay(color=YOU_COLOR, id="waveform")
        yield Static("[↑↓] select  [enter] start  [q] quit", id="controls")

    def on_mount(self) -> None:
        self.set_interval(1 / 20, self._update_waveform)
        self._start_time = 0.0
        import time
        self._start_time = time.time()

    def _update_waveform(self) -> None:
        import time
        t = time.time() - self._start_time
        wf = self.query_one("#waveform", WaveformDisplay)
        size = wf.size
        n_bars = max(8, (size.width - 2 + 1) // 2)
        data = fake_waveform(n_bars=n_bars, t=t)
        wf.update_data(data)

    def action_move_down(self) -> None:
        self._model.move_down()
        self.query_one("#modes", ModeSelector).selected_index = self._model._index

    def action_move_up(self) -> None:
        self._model.move_up()
        self.query_one("#modes", ModeSelector).selected_index = self._model._index

    def action_confirm(self) -> None:
        mode = self._model.confirm_selection()
        self.dismiss(mode)

    def action_quit(self) -> None:
        self.app.exit()
