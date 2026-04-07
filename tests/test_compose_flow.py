"""Tests for the compose mode state machine: loaded → listening/generated."""

import os
import tempfile
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
    inst.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=0.0, end=0.5))
    inst.notes.append(pretty_midi.Note(velocity=100, pitch=64, start=0.0, end=0.5))
    inst.notes.append(pretty_midi.Note(velocity=100, pitch=67, start=0.0, end=0.5))
    midi.instruments.append(inst)
    midi.write(path)
    return path


def _dummy_song():
    from riff.audio.song import SongData, SongNote
    return SongData(
        notes=[SongNote(note="C", octave=4, start=0.0, duration=0.05)],
        bpm=120.0,
    )


def _dummy_timed_chord():
    from riff.audio.midi_feeder import TimedChord
    return TimedChord(chord="C", start=0.0, duration=1.0)


class TestComposePhase:
    @pytest.fixture(autouse=True)
    def _cleanup(self):
        self._states: list[AppState] = []
        yield
        for s in self._states:
            s.update(running=False)
        time.sleep(0.2)

    def _make(self, **kwargs) -> tuple[AppState, ComposeCommands]:
        state = AppState(**kwargs)
        self._states.append(state)
        return state, ComposeCommands(state)

    def test_defaults_to_empty(self):
        state = AppState()

        assert state.snapshot()["compose_phase"] == ""

    def test_loading_file_auto_listens(self):
        state, cmds = self._make(mode_index=1)
        with tempfile.TemporaryDirectory() as tmp:
            path = _make_midi(tmp)

            cmds.load_file(path)

            snap = state.snapshot()
            assert snap["compose_phase"] == "listening"
            assert cmds._timed_chords is not None
            assert len(cmds._timed_chords) > 0

    def test_listen_in_loaded_sets_listening(self):
        state, cmds = self._make(mode_index=1)
        state.update(compose_phase="loaded")
        cmds._source_song = _dummy_song()
        cmds.source_audio = np.zeros(1000, dtype=np.float32)
        cmds.source_type = "midi"

        cmds.listen_source()

        assert state.snapshot()["compose_phase"] == "listening"

    def test_generate_from_file_sets_generated(self):
        state, cmds = self._make(mode_index=1)
        state.update(compose_phase="loaded")
        cmds._timed_chords = [_dummy_timed_chord()]
        cmds.source_type = "midi"
        cmds._source_song = _dummy_song()

        cmds.generate_from_file()

        time.sleep(0.5)
        assert state.snapshot()["compose_phase"] == "generated"
        assert cmds.generated_audio is not None

    def test_save_in_generated(self):
        state, cmds = self._make(mode_index=1)
        cmds.generated_audio = np.array([0.5, -0.5], dtype=np.float32)

        with tempfile.TemporaryDirectory() as tmp:
            cmds._save_dir = tmp
            cmds.save()

            wav_files = [f for f in os.listdir(tmp) if f.endswith(".wav")]
            assert len(wav_files) == 1

    def test_play_mix_in_generated(self):
        state, cmds = self._make(mode_index=1)
        cmds.source_audio = np.array([0.3], dtype=np.float32)
        cmds.generated_audio = np.array([0.2], dtype=np.float32)

        cmds.play_mix()

        assert "mix" in state.snapshot()["status_msg"].lower() or "playing" in state.snapshot()["status_msg"].lower()

    def test_listen_in_generated_listens_again(self):
        state, cmds = self._make(mode_index=1)
        state.update(compose_phase="generated")
        cmds._source_song = _dummy_song()
        cmds.source_audio = np.zeros(1000, dtype=np.float32)
        cmds.source_type = "midi"

        cmds.listen_source()

        assert state.snapshot()["compose_phase"] == "listening"

    def test_clear_resets_to_empty(self):
        state, cmds = self._make(mode_index=1)
        state.update(compose_phase="loaded")
        cmds._timed_chords = [_dummy_timed_chord()]
        cmds.source_audio = np.zeros(100, dtype=np.float32)

        cmds.clear()

        snap = state.snapshot()
        assert snap["compose_phase"] == ""
        assert snap["attached_file"] == ""
        assert cmds._timed_chords is None
