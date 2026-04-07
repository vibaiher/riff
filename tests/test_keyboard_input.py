"""Tests for file loading via ComposeCommands (migrated from KeyboardHandler)."""

import tempfile
import os
import time

import numpy as np
import pretty_midi
import pytest

from riff.core.commands import ComposeCommands
from riff.core.state import AppState


def _make_midi(tmp_dir: str) -> str:
    path = os.path.join(tmp_dir, "test.mid")
    midi = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=0)
    inst.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=0.0, end=1.0))
    midi.instruments.append(inst)
    midi.write(path)
    return path


class TestFileLoading:
    @pytest.fixture(autouse=True)
    def _cleanup(self):
        self._states: list[AppState] = []
        yield
        for s in self._states:
            s.update(running=False)
        time.sleep(0.3)

    def _make(self, **kwargs) -> tuple[AppState, ComposeCommands]:
        state = AppState(**kwargs)
        self._states.append(state)
        return state, ComposeCommands(state)

    def test_load_valid_midi(self):
        state, cmds = self._make(mode_index=1)
        with tempfile.TemporaryDirectory() as tmp:
            path = _make_midi(tmp)

            cmds.load_file(path)

            assert cmds.source_type == "midi"

    def test_loading_clears_previous_chords(self):
        state, cmds = self._make(mode_index=1)
        state.add_chord("Am")
        state.add_chord("F")
        state.update(gen_status="done", gen_note_count=50, gen_duration=10.0)

        with tempfile.TemporaryDirectory() as tmp:
            path = _make_midi(tmp)

            cmds.load_file(path)

            snap = state.snapshot()
            assert snap["captured_chords"] == []
            assert snap["gen_status"] == ""
            assert snap["gen_note_count"] == 0
            assert snap["gen_duration"] == 0.0

    def test_loading_clears_generated_audio(self):
        state, cmds = self._make(mode_index=1)
        cmds.source_audio = np.array([0.5], dtype=np.float32)
        cmds.generated_audio = np.array([0.3], dtype=np.float32)

        with tempfile.TemporaryDirectory() as tmp:
            path = _make_midi(tmp)

            cmds.load_file(path)

            assert cmds.generated_audio is None

    def test_invalid_path_shows_error(self):
        state, cmds = self._make(mode_index=1)

        cmds.load_file("/nonexistent/file.mid")

        snap = state.snapshot()
        assert "not found" in snap["status_msg"].lower()

    def test_tab_complete_path(self, tmp_path):
        from riff.ui.file_input import complete_path
        (tmp_path / "unique_song.mid").touch()

        matches = complete_path(str(tmp_path / "unique"))

        assert matches == [str(tmp_path / "unique_song.mid")]

    def test_corrupt_file_shows_error(self):
        state, cmds = self._make(mode_index=1)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "song.xyz")
            with open(path, "w") as f:
                f.write("not audio")

            cmds.load_file(path)

            snap = state.snapshot()
            assert "error" in snap["status_msg"].lower()
