"""Tests for the Textual welcome screen."""

import pytest

from riff.ui.app import RiffApp


@pytest.mark.asyncio
async def test_welcome_displays_logo():
    app = RiffApp()

    async with app.run_test() as _pilot:
        text = app.screen.query_one("#logo").render()

        assert "██" in str(text)


@pytest.mark.asyncio
async def test_welcome_displays_mode_options():
    app = RiffApp()

    async with app.run_test() as _pilot:
        mode_list = app.screen.query_one("#modes")
        text = str(mode_list.render())

        assert "FREE" in text
        assert "COMPOSE" in text


@pytest.mark.asyncio
async def test_arrow_down_changes_selection():
    app = RiffApp()

    async with app.run_test() as pilot:
        await pilot.press("down")
        modes = app.screen.query_one("#modes")

        assert modes.selected_index == 1


@pytest.mark.asyncio
async def test_q_exits_app():
    app = RiffApp()

    async with app.run_test() as pilot:
        await pilot.press("q")

        assert app.return_code is not None or not app.is_running


@pytest.mark.asyncio
async def test_waveform_widget_present():
    app = RiffApp()

    async with app.run_test(size=(80, 24)) as _pilot:
        wf = app.screen.query_one("#waveform")

        assert wf is not None


@pytest.mark.asyncio
async def test_app_mounts_welcome_screen():
    app = RiffApp()

    async with app.run_test() as _pilot:
        screen = app.screen

        assert screen.__class__.__name__ == "WelcomeScreen"
