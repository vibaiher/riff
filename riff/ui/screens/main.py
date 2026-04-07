"""Main screen — the primary RIFF interface with YOU and RIFF panels."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static

from riff.ui.widgets.header import LogoHeader
from riff.ui.widgets.you_panel import YouPanel
from riff.ui.widgets.riff_panel import RiffPanel
from riff.ui.widgets.status_bar import StatusBar
from riff.ui.widgets.controls_bar import ControlsBar


class MainScreen(Screen):
    CSS = """
    MainScreen {
        layout: vertical;
    }
    #header {
        height: 7;
    }
    #you {
        height: 1fr;
    }
    #riff {
        height: 1fr;
    }
    #status {
        height: 1;
    }
    #controls {
        height: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield LogoHeader(id="header")
        yield YouPanel(id="you")
        yield RiffPanel(id="riff")
        yield StatusBar(id="status")
        yield ControlsBar(id="controls")

    def on_mount(self) -> None:
        self.set_interval(1 / 20, self._poll_state)

    def _poll_state(self) -> None:
        state = getattr(self.app, "state", None)
        if state is None:
            return
        snap = state.snapshot()
        self.query_one("#you", YouPanel).update_from_snapshot(snap)
        self.query_one("#riff", RiffPanel).update_from_snapshot(snap)
        self.query_one("#status", StatusBar).update_from_snapshot(snap)
        self.query_one("#controls", ControlsBar).update_from_snapshot(snap)
        if not snap["running"]:
            self.app.exit()
