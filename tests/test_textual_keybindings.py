"""Tests for MainScreen key bindings."""

import pytest

from riff.core.state import AppState
from riff.ui.app import RiffApp
from riff.ui.screens.main import MainScreen


class TestMainScreenKeys:
    def _app_with_main(self, **state_kwargs) -> RiffApp:
        app = RiffApp()
        state = AppState(**state_kwargs)
        app.state = state
        from riff.core.commands import ComposeCommands
        app.commands = ComposeCommands(state)
        return app

    @pytest.mark.asyncio
    async def test_space_toggles_mute(self):
        app = self._app_with_main()

        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(MainScreen())
            await pilot.pause()

            await pilot.press("space")

            assert app.state.snapshot()["muted"] is True

    @pytest.mark.asyncio
    async def test_m_cycles_mode(self):
        app = self._app_with_main()

        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(MainScreen())
            await pilot.pause()

            await pilot.press("m")

            assert app.state.snapshot()["mode"] == "COMPOSE"

    @pytest.mark.asyncio
    async def test_q_exits(self):
        app = self._app_with_main()

        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(MainScreen())
            await pilot.pause()

            await pilot.press("q")

            assert app.state.snapshot()["running"] is False

    @pytest.mark.asyncio
    async def test_g_in_compose_with_chords_generates(self):
        app = self._app_with_main(mode_index=1)
        app.state.add_chord("Am")
        app.state.add_chord("F")

        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(MainScreen())
            await pilot.pause()

            await pilot.press("g")
            import asyncio
            await asyncio.sleep(0.5)

            snap = app.state.snapshot()
            assert snap["gen_status"] in ("generating...", "playing", "done")
            app.state.update(running=False)

    @pytest.mark.asyncio
    async def test_c_in_compose_clears(self):
        app = self._app_with_main(mode_index=1)
        app.state.add_chord("Am")

        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(MainScreen())
            await pilot.pause()

            await pilot.press("c")

            assert app.state.snapshot()["captured_chords"] == []
