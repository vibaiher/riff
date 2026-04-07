"""Textual application for RIFF."""

from __future__ import annotations

from textual.app import App

from .screens.welcome import WelcomeScreen


class RiffApp(App):
    def on_mount(self) -> None:
        self.push_screen(WelcomeScreen())
