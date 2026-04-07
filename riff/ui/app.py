"""Textual application for RIFF."""

from __future__ import annotations

from textual.app import App

from riff.core.commands import ComposeCommands
from riff.core.state import AppState
from .screens.welcome import WelcomeScreen


class RiffApp(App):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        if not hasattr(self, "state"):
            self.state = AppState()
        self.commands = ComposeCommands(self.state)

    def on_mount(self) -> None:
        self.push_screen(WelcomeScreen())
