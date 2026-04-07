"""Tests for save [s] and play-together [p] keys."""

import os
import tempfile
import wave

import numpy as np
import pretty_midi

from riff.core.state import AppState
from riff.ui.display import KeyboardHandler


class TestSaveKey:
    def test_s_does_nothing_without_generated_audio(self):
        state = AppState(mode_index=1)
        handler = KeyboardHandler(state)
        state.update(compose_phase="generated")

        handler._handle("s")

        snap = state.snapshot()
        assert "nothing" in snap["status_msg"].lower() or "no audio" in snap["status_msg"].lower()

    def test_s_saves_generated_audio_to_file(self):
        state = AppState(mode_index=1)
        handler = KeyboardHandler(state)
        state.update(compose_phase="generated")
        handler._generated_audio = np.array([0.5, -0.5], dtype=np.float32)

        with tempfile.TemporaryDirectory() as tmp:
            handler._save_dir = tmp
            handler._handle("s")

            snap = state.snapshot()
            assert "saved" in snap["status_msg"].lower()
            wav_files = [f for f in os.listdir(tmp) if f.endswith(".wav")]
            assert len(wav_files) == 1

    def test_s_outside_compose_does_nothing(self):
        state = AppState(mode_index=0)
        handler = KeyboardHandler(state)
        handler._generated_audio = np.array([0.5], dtype=np.float32)

        handler._handle("s")

        assert "saved" not in state.snapshot()["status_msg"].lower()

    def test_s_saves_mix_when_both_audios_available(self):
        state = AppState(mode_index=1)
        handler = KeyboardHandler(state)
        state.update(compose_phase="generated")
        handler._source_audio = np.array([0.3, 0.2], dtype=np.float32)
        handler._generated_audio = np.array([0.1, 0.4], dtype=np.float32)

        with tempfile.TemporaryDirectory() as tmp:
            handler._save_dir = tmp
            handler._handle("s")

            wav_files = [f for f in os.listdir(tmp) if f.endswith(".wav")]
            assert len(wav_files) == 1


class TestPlayTogetherKey:
    def test_p_does_nothing_without_both_audios(self):
        state = AppState(mode_index=1)
        handler = KeyboardHandler(state)
        state.update(compose_phase="generated")

        handler._handle("p")

        snap = state.snapshot()
        assert "no audio" in snap["status_msg"].lower() or "nothing" in snap["status_msg"].lower()

    def test_p_with_both_audios_starts_playback(self):
        state = AppState(mode_index=1)
        handler = KeyboardHandler(state)
        state.update(compose_phase="generated")
        handler._source_audio = np.array([0.5, 0.3], dtype=np.float32)
        handler._generated_audio = np.array([0.2, 0.1], dtype=np.float32)

        handler._handle("p")

        snap = state.snapshot()
        assert "playing" in snap["status_msg"].lower() or "mix" in snap["status_msg"].lower()

    def test_p_outside_compose_does_nothing(self):
        state = AppState(mode_index=0)
        handler = KeyboardHandler(state)
        handler._source_audio = np.array([0.5], dtype=np.float32)
        handler._generated_audio = np.array([0.2], dtype=np.float32)

        handler._handle("p")

        assert "playing" not in state.snapshot()["status_msg"].lower()
