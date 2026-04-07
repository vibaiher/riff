"""Tests for loading audio files (mp3, wav, etc.) into the analyzer."""

import os
import queue
import tempfile
import time

import numpy as np
import pytest

from riff.core.commands import ComposeCommands
from riff.core.state import AppState


class TestAudioFileLoad:
    @pytest.fixture(autouse=True)
    def _stop_state(self):
        self._states: list[AppState] = []
        yield
        for s in self._states:
            s.update(running=False)
        time.sleep(0.15)

    def _make(self, **kwargs) -> tuple[AppState, ComposeCommands]:
        state = AppState(**kwargs)
        self._states.append(state)
        return state, ComposeCommands(state)

    def test_state_accepts_audio_queue(self):
        q = queue.Queue()
        state = AppState()

        state.set_audio_queue(q)

        assert state.audio_queue is q

    def test_load_wav_sets_audio_source_type(self):
        state, cmds = self._make(mode_index=1)

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.wav")
            _write_sine_wav(path, duration=0.1)

            cmds.load_file(path)

            assert cmds.source_type == "audio"
            assert cmds.source_audio is not None

    def test_load_midi_sets_midi_source_type(self):
        import pretty_midi
        state, cmds = self._make(mode_index=1)

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.mid")
            midi = pretty_midi.PrettyMIDI()
            inst = pretty_midi.Instrument(program=0)
            inst.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=0.0, end=0.5))
            midi.instruments.append(inst)
            midi.write(path)

            cmds.load_file(path)

            assert cmds.source_type == "midi"
            assert cmds._source_song is not None

    def test_listen_audio_feeds_blocks_into_queue(self):
        q = queue.Queue()
        state, cmds = self._make(mode_index=1)
        state.set_audio_queue(q)
        cmds.source_type = "audio"
        cmds.source_audio = np.sin(
            2 * np.pi * 440 * np.arange(44100) / 44100
        ).astype(np.float32)
        state.update(compose_phase="loaded")

        cmds.listen_source()
        time.sleep(0.3)

        assert not q.empty()

    def test_generate_with_captured_chords(self):
        state, cmds = self._make(mode_index=1)
        cmds.source_type = "audio"
        cmds.source_audio = np.zeros(1000, dtype=np.float32)
        state.add_chord("Am")
        state.add_chord("F")
        state.update(compose_phase="loaded")

        cmds.generate()
        time.sleep(0.3)

        snap = state.snapshot()
        assert snap["gen_status"] in ("generating...", "playing", "done")


def _write_sine_wav(path: str, duration: float = 1.0, freq: float = 440.0):
    import wave
    import struct
    sr = 44100
    n = int(sr * duration)
    samples = [int(32767 * np.sin(2 * np.pi * freq * i / sr)) for i in range(n)]
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(struct.pack(f"<{n}h", *samples))
