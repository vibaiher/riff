"""Main screen — the primary RIFF interface with YOU and RIFF panels."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen

from riff.ui.widgets.header import LogoHeader
from riff.ui.widgets.you_panel import YouPanel
from riff.ui.widgets.riff_panel import RiffPanel
from riff.ui.widgets.status_bar import StatusBar
from riff.ui.widgets.controls_bar import ControlsBar


class MainScreen(Screen):
    BINDINGS = [
        Binding("space", "toggle_mute", "Pause", show=False),
        Binding("m", "next_mode", "Mode", show=False),
        Binding("t", "next_timbre", "Timbre", show=False),
        Binding("e", "next_engine", "Engine", show=False),
        Binding("q", "quit_app", "Quit", show=False),
        Binding("left_square_bracket", "speed_down", "Slower", show=False),
        Binding("right_square_bracket", "speed_up", "Faster", show=False),
        Binding("f", "load_file", "Load", show=False),
        Binding("g", "generate", "Generate", show=False),
        Binding("c", "clear", "Clear", show=False),
        Binding("l", "listen", "Listen", show=False),
        Binding("s", "save", "Save", show=False),
        Binding("p", "play_mix", "Play mix", show=False),
    ]

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

    @property
    def _state(self):
        return self.app.state

    @property
    def _cmds(self):
        return self.app.commands

    def _is_compose(self) -> bool:
        return self._state.snapshot()["mode"] == "COMPOSE"

    def action_toggle_mute(self) -> None:
        self._state.toggle_mute()

    def action_next_mode(self) -> None:
        self._state.next_mode()

    def action_next_timbre(self) -> None:
        self._state.next_timbre()

    def action_next_engine(self) -> None:
        self._state.next_engine()

    def action_quit_app(self) -> None:
        self._state.update(running=False)
        self.app.exit()

    def action_speed_down(self) -> None:
        self._state.speed_down()

    def action_speed_up(self) -> None:
        self._state.speed_up()

    def action_load_file(self) -> None:
        if not self._is_compose():
            return
        self.app.push_screen("file_input")

    def action_generate(self) -> None:
        if not self._is_compose():
            return
        phase = self._state.snapshot()["compose_phase"]
        if phase in ("loaded", "generated") and self._cmds.source_type == "midi" and self._cmds._timed_chords:
            self._cmds.generate_from_file()
        else:
            self._cmds.generate()

    def action_clear(self) -> None:
        if not self._is_compose():
            return
        self._cmds.clear()

    def action_listen(self) -> None:
        if not self._is_compose():
            return
        phase = self._state.snapshot()["compose_phase"]
        if phase in ("loaded", "generated"):
            self._cmds.listen_source()

    def action_save(self) -> None:
        if not self._is_compose():
            return
        if self._state.snapshot()["compose_phase"] == "generated":
            self._cmds.save()

    def action_play_mix(self) -> None:
        if not self._is_compose():
            return
        if self._state.snapshot()["compose_phase"] == "generated":
            self._cmds.play_mix()
