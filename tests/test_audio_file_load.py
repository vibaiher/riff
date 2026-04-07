"""Tests for loading audio files (mp3, wav, etc.) into the analyzer."""

import os
import queue
import tempfile
import time

import numpy as np
import pytest

from riff.core.state import AppState
from riff.ui.display import KeyboardHandler


class TestAudioFileLoad:
    @pytest.fixture(autouse=True)
    def _stop_state(self):
        """Ensure all background threads stop after each test."""
        self._states: list[AppState] = []
        yield
        for s in self._states:
            s.update(running=False)
        time.sleep(0.15)

    def _make(self, **kwargs) -> tuple[AppState, KeyboardHandler]:
        state = AppState(**kwargs)
        self._states.append(state)
        return state, KeyboardHandler(state)

    def test_state_accepts_audio_queue(self):
        q = queue.Queue()
        state = AppState()

        state.set_audio_queue(q)

        assert state.audio_queue is q

    def test_load_wav_sets_audio_source_type(self):
        state, handler = self._make(mode_index=1)

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.wav")
            _write_sine_wav(path, duration=0.1)

            handler._confirm_file_input_path(path)

            assert handler._source_type == "audio"
            assert handler._source_audio is not None

    def test_load_midi_sets_midi_source_type(self):
        import pretty_midi
        state, handler = self._make(mode_index=1)

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.mid")
            midi = pretty_midi.PrettyMIDI()
            inst = pretty_midi.Instrument(program=0)
            inst.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=0.0, end=0.5))
            midi.instruments.append(inst)
            midi.write(path)

            handler._confirm_file_input_path(path)

            assert handler._source_type == "midi"
            assert handler._source_song is not None

    def test_listen_audio_feeds_blocks_into_queue(self):
        q = queue.Queue()
        state, handler = self._make(mode_index=1)
        state.set_audio_queue(q)
        handler._source_type = "audio"
        handler._source_audio = np.sin(
            2 * np.pi * 440 * np.arange(44100) / 44100
        ).astype(np.float32)
        state.update(compose_phase="loaded")

        handler._handle("l")
        time.sleep(0.3)

        assert not q.empty()

    def test_g_after_audio_listen_uses_captured_chords(self):
        state, handler = self._make(mode_index=1)
        handler._source_type = "audio"
        handler._source_audio = np.zeros(1000, dtype=np.float32)
        state.add_chord("Am")
        state.add_chord("F")
        state.update(compose_phase="loaded")

        handler._handle("g")
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
