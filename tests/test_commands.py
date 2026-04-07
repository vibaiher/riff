"""Tests for ComposeCommands — application logic extracted from KeyboardHandler."""

import os
import tempfile
import time

import numpy as np
import pretty_midi
import pytest

from riff.core.commands import ComposeCommands
from riff.core.state import AppState


class TestComposeCommands:
    @pytest.fixture(autouse=True)
    def _cleanup(self):
        self._states: list[AppState] = []
        yield
        for s in self._states:
            s.update(running=False)
        time.sleep(0.2)

    def _make(self) -> tuple[AppState, ComposeCommands]:
        state = AppState(mode_index=1)
        self._states.append(state)
        return state, ComposeCommands(state)

    def test_starts_with_empty_source_state(self):
        state, cmds = self._make()

        assert cmds.source_type == ""
        assert cmds.source_audio is None
        assert cmds.generated_audio is None

    def test_load_file_nonexistent_sets_error(self):
        state, cmds = self._make()
        state.update(compose_phase="loaded")

        cmds.load_file("/nonexistent/path/song.mid")

        snap = state.snapshot()
        assert "not found" in snap["status_msg"].lower()
        assert snap["compose_phase"] == ""

    def test_load_file_corrupt_sets_error(self):
        state, cmds = self._make()

        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            f.write(b"not a midi")
            path = f.name
        try:
            cmds.load_file(path)

            snap = state.snapshot()
            assert "error" in snap["status_msg"].lower()
            assert snap["compose_phase"] == ""
        finally:
            os.unlink(path)

    def test_load_valid_midi_sets_source_and_auto_listens(self):
        state, cmds = self._make()
        path = _make_midi_file()

        cmds.load_file(path)

        assert cmds.source_type == "midi"
        assert cmds.source_audio is not None
        assert state.snapshot()["compose_phase"] == "listening"
        os.unlink(path)

    def test_load_file_clears_previous_generation(self):
        state, cmds = self._make()
        cmds.generated_audio = np.array([0.5], dtype=np.float32)
        state.add_chord("Am")
        state.update(gen_status="done")
        path = _make_midi_file()

        cmds.load_file(path)

        assert cmds.generated_audio is None
        assert state.snapshot()["gen_status"] == ""
        os.unlink(path)

    def test_clear_resets_all_state(self):
        state, cmds = self._make()
        cmds.source_audio = np.zeros(100, dtype=np.float32)
        cmds.generated_audio = np.zeros(50, dtype=np.float32)
        cmds.source_type = "midi"
        state.add_chord("C")
        state.update(compose_phase="generated", attached_file="/tmp/x.mid")

        cmds.clear()

        assert cmds.source_audio is None
        assert cmds.generated_audio is None
        assert cmds.source_type == ""
        snap = state.snapshot()
        assert snap["compose_phase"] == ""
        assert snap["attached_file"] == ""
        assert snap["captured_chords"] == []

    def test_generate_with_no_chords_sets_error(self):
        state, cmds = self._make()

        cmds.generate()

        assert "no chords" in state.snapshot()["status_msg"].lower()

    def test_generate_with_chords_starts_generation(self):
        state, cmds = self._make()
        state.add_chord("Am")
        state.add_chord("F")

        cmds.generate()
        time.sleep(0.5)

        snap = state.snapshot()
        assert snap["gen_status"] in ("generating...", "playing", "done")

    def test_save_with_no_audio_sets_error(self):
        state, cmds = self._make()

        cmds.save()

        assert "no audio" in state.snapshot()["status_msg"].lower()

    def test_save_writes_wav_file(self):
        state, cmds = self._make()
        cmds.generated_audio = np.array([0.5, -0.5], dtype=np.float32)

        with tempfile.TemporaryDirectory() as tmp:
            cmds._save_dir = tmp
            cmds.save()

            wav_files = [f for f in os.listdir(tmp) if f.endswith(".wav")]
            assert len(wav_files) == 1

    def test_play_mix_with_no_source_sets_error(self):
        state, cmds = self._make()
        cmds.generated_audio = np.array([0.5], dtype=np.float32)

        cmds.play_mix()

        assert "no audio" in state.snapshot()["status_msg"].lower()


def _make_midi_file() -> str:
    f = tempfile.NamedTemporaryFile(suffix=".mid", delete=False)
    midi = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=0)
    inst.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=0.0, end=0.5))
    midi.instruments.append(inst)
    midi.write(f.name)
    f.close()
    return f.name
