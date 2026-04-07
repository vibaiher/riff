"""Tests for the Textual main screen widgets."""

import pytest
from rich.console import Console

from riff.core.state import AppState
from riff.ui.app import RiffApp
from riff.ui.screens.main import MainScreen
from riff.ui.widgets.you_panel import YouPanel
from riff.ui.widgets.riff_panel import RiffPanel
from riff.ui.widgets.status_bar import StatusBar
from riff.ui.widgets.controls_bar import ControlsBar


def _render_to_str(renderable) -> str:
    console = Console(file=None, force_terminal=True, width=100)
    with console.capture() as capture:
        console.print(renderable)
    return capture.get()


class TestMainScreen:
    @pytest.mark.asyncio
    async def test_main_screen_has_all_widgets(self):
        app = RiffApp()
        app.state = AppState()

        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(MainScreen())
            await pilot.pause()

            assert app.screen.query_one("#you", YouPanel)
            assert app.screen.query_one("#riff", RiffPanel)
            assert app.screen.query_one("#status", StatusBar)
            assert app.screen.query_one("#controls", ControlsBar)

    @pytest.mark.asyncio
    async def test_you_panel_renders_note(self):
        app = RiffApp()
        app.state = AppState()
        app.state.update(note="A", octave=4, db=-20.0, bpm=120.0)

        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(MainScreen())
            await pilot.pause()
            await pilot.pause()

            you = app.screen.query_one("#you", YouPanel)
            rendered = _render_to_str(you.render())

            assert "A4" in rendered

    @pytest.mark.asyncio
    async def test_riff_panel_shows_free_mode(self):
        app = RiffApp()
        app.state = AppState()

        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(MainScreen())
            await pilot.pause()
            await pilot.pause()

            riff = app.screen.query_one("#riff", RiffPanel)
            rendered = _render_to_str(riff.render())

            assert "play something" in rendered

    @pytest.mark.asyncio
    async def test_riff_panel_shows_compose_mode(self):
        app = RiffApp()
        app.state = AppState(mode_index=1)

        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(MainScreen())
            await pilot.pause()
            await pilot.pause()

            riff = app.screen.query_one("#riff", RiffPanel)
            rendered = _render_to_str(riff.render())

            assert "COMPOSE" in rendered

    @pytest.mark.asyncio
    async def test_status_bar_shows_device(self):
        app = RiffApp()
        app.state = AppState()
        app.state.update(device_name="Scarlett Solo")

        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(MainScreen())
            await pilot.pause()
            await pilot.pause()

            status = app.screen.query_one("#status", StatusBar)
            rendered = _render_to_str(status.render())

            assert "Scarlett Solo" in rendered

    @pytest.mark.asyncio
    async def test_controls_bar_shows_quit(self):
        app = RiffApp()
        app.state = AppState()

        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(MainScreen())
            await pilot.pause()

            controls = app.screen.query_one("#controls", ControlsBar)
            rendered = _render_to_str(controls.render())

            assert "quit" in rendered
