"""Tests for capture_enabled flag — disables live mic when MIDI is loaded."""

import queue
import numpy as np

from riff.core.state import AppState


class TestCaptureEnabled:
    def test_enabled_by_default(self):
        state = AppState()

        assert state.snapshot()["capture_enabled"] is True

    def test_analyzer_skips_when_disabled(self):
        state = AppState()
        q = queue.Queue()
        from riff.audio.analyzer import AudioAnalyzer
        analyzer = AudioAnalyzer(state, q)

        state.update(capture_enabled=False)
        tone = np.sin(2 * np.pi * 440 * np.arange(1024 * 4) / 44100).astype(np.float32)
        for i in range(4):
            analyzer._process(tone[i * 1024:(i + 1) * 1024])

        assert state.snapshot()["waveform"] == []

    def test_analyzer_updates_waveform_when_enabled(self):
        state = AppState()
        q = queue.Queue()
        from riff.audio.analyzer import AudioAnalyzer
        analyzer = AudioAnalyzer(state, q)

        tone = np.sin(2 * np.pi * 440 * np.arange(1024) / 44100).astype(np.float32)
        analyzer._process(tone)

        assert len(state.snapshot()["waveform"]) > 0

    def test_listen_source_disables_then_restores_capture(self):
        state = AppState(mode_index=1)
        from riff.core.commands import ComposeCommands
        from riff.audio.song import SongData, SongNote
        cmds = ComposeCommands(state)
        cmds._source_song = SongData(
            notes=[SongNote(note="C", octave=4, start=0.0, duration=0.05)],
            bpm=120.0,
        )
        cmds.source_audio = np.zeros(2205, dtype=np.float32)
        cmds.source_type = "midi"
        state.update(compose_phase="loaded")

        cmds._play_midi_source()

        assert state.snapshot()["capture_enabled"] is True
