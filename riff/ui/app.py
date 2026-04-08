"""Textual application for RIFF."""

from __future__ import annotations

import time

from textual.app import App

from riff.core.commands import ComposeCommands
from riff.core.state import MODES, AppState

from .screens.main import MainScreen
from .screens.welcome import WelcomeScreen


class RiffApp(App):
    TITLE = "RIFF"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        if not hasattr(self, "state"):
            self.state = AppState()
        from riff.audio.synth import RiffPlayer

        self.commands = ComposeCommands(self.state, riff_player_factory=RiffPlayer)
        self._capture = None
        self._analyzer = None

    def on_mount(self) -> None:
        self.push_screen(WelcomeScreen(), callback=self._on_welcome_done)

    def _on_welcome_done(self, mode: str | None) -> None:
        if mode is None:
            self.exit()
            return
        mode_idx = MODES.index(mode) if mode in MODES else 0
        self.state.update(mode_index=mode_idx)
        self._start_audio()
        self.push_screen(MainScreen())

    def _start_audio(self) -> None:
        try:
            from riff.audio.analyzer import AudioAnalyzer
            from riff.audio.capture import AudioCapture

            self._capture = AudioCapture(self.state)
            self.state.set_audio_queue(self._capture.audio_queue)
            self._analyzer = AudioAnalyzer(self.state, self._capture.audio_queue)
            self._capture.start()
            self._analyzer.start()
        except Exception:
            pass

    def _stop_audio(self) -> None:
        self.state.update(running=False)
        time.sleep(0.1)
        if self._analyzer:
            self._analyzer.stop()
        if self._capture:
            try:
                self._capture.stop()
            except Exception:
                pass

    def on_unmount(self) -> None:
        self._stop_audio()
