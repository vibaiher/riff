"""Tests for keyboard handling of file input mode."""

import tempfile
import os
import time

import numpy as np
import pretty_midi
import pytest

from riff.core.state import AppState
from riff.ui.display import KeyboardHandler


def _make_midi(tmp_dir: str) -> str:
    path = os.path.join(tmp_dir, "test.mid")
    midi = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=0)
    inst.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=0.0, end=1.0))
    midi.instruments.append(inst)
    midi.write(path)
    return path


class TestFileInputKeyboard:
    @pytest.fixture(autouse=True)
    def _cleanup(self):
        self._states: list[AppState] = []
        yield
        for s in self._states:
            s.update(running=False)
        time.sleep(0.2)

    def _make(self, **kwargs) -> tuple[AppState, KeyboardHandler]:
        state = AppState(**kwargs)
        self._states.append(state)
        return state, KeyboardHandler(state)

    def test_f_in_compose_enters_input_mode(self):
        state, handler = self._make(mode_index=1)

        handler._handle("f")

        snap = state.snapshot()
        assert snap["input_mode"] == "file"
        assert snap["input_buffer"] == ""

    def test_f_outside_compose_does_nothing(self):
        state, handler = self._make(mode_index=0)

        handler._handle("f")

        assert state.snapshot()["input_mode"] == ""

    def test_printable_chars_append_to_buffer(self):
        state, handler = self._make(mode_index=1)
        state.start_input("file")

        handler._handle("/")
        handler._handle("t")
        handler._handle("m")
        handler._handle("p")

        assert state.snapshot()["input_buffer"] == "/tmp"

    def test_backspace_removes_char(self):
        state, handler = self._make(mode_index=1)
        state.start_input("file")
        state.update(input_buffer="/tmp")

        handler._handle("\x7f")

        assert state.snapshot()["input_buffer"] == "/tm"

    def test_escape_cancels_input(self):
        state, handler = self._make(mode_index=1)
        state.start_input("file")
        state.update(input_buffer="/some/path")

        handler._handle("\x1b")

        snap = state.snapshot()
        assert snap["input_mode"] == ""
        assert snap["input_buffer"] == ""

    def test_enter_with_valid_midi_loads_file(self):
        state, handler = self._make(mode_index=1)
        with tempfile.TemporaryDirectory() as tmp:
            path = _make_midi(tmp)
            state.start_input("file")
            state.update(input_buffer=path)

            handler._handle("\n")

            snap = state.snapshot()
            assert snap["input_mode"] == ""
            assert snap["attached_file"] == path

    def test_loading_file_clears_previous_chords(self):
        state, handler = self._make(mode_index=1)
        state.add_chord("Am")
        state.add_chord("F")
        state.update(gen_status="done", gen_note_count=50, gen_duration=10.0)

        with tempfile.TemporaryDirectory() as tmp:
            path = _make_midi(tmp)
            state.start_input("file")
            state.update(input_buffer=path)

            handler._handle("\n")

            snap = state.snapshot()
            assert snap["captured_chords"] == []
            assert snap["gen_status"] == ""
            assert snap["gen_note_count"] == 0
            assert snap["gen_duration"] == 0.0

    def test_loading_file_clears_audio_buffers(self):
        state, handler = self._make(mode_index=1)
        handler._source_audio = np.array([0.5], dtype=np.float32)
        handler._generated_audio = np.array([0.3], dtype=np.float32)

        with tempfile.TemporaryDirectory() as tmp:
            path = _make_midi(tmp)
            state.start_input("file")
            state.update(input_buffer=path)

            handler._handle("\n")

            assert handler._generated_audio is None

    def test_enter_with_invalid_path_shows_error(self):
        state, handler = self._make(mode_index=1)
        state.start_input("file")
        state.update(input_buffer="/nonexistent/file.mid")

        handler._handle("\n")

        snap = state.snapshot()
        assert snap["input_mode"] == ""
        assert "error" in snap["status_msg"].lower() or "not found" in snap["status_msg"].lower()

    def test_tab_completes_path(self, tmp_path):
        (tmp_path / "unique_song.mid").touch()
        state, handler = self._make(mode_index=1)
        state.start_input("file")
        state.update(input_buffer=str(tmp_path / "unique"))

        handler._handle("\t")

        assert state.snapshot()["input_buffer"] == str(tmp_path / "unique_song.mid")

    def test_enter_with_corrupt_file_shows_error(self):
        state, handler = self._make(mode_index=1)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "song.xyz")
            with open(path, "w") as f:
                f.write("not audio")
            state.start_input("file")
            state.update(input_buffer=path)

            handler._handle("\n")

            snap = state.snapshot()
            assert "error" in snap["status_msg"].lower()

    def test_input_mode_blocks_normal_shortcuts(self):
        state, handler = self._make(mode_index=1)
        state.start_input("file")

        handler._handle("q")

        assert state.snapshot()["running"] is True
        assert state.snapshot()["input_buffer"] == "q"
