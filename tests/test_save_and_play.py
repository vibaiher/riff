"""Tests for save and play-together via ComposeCommands."""

import os
import tempfile

import numpy as np

from riff.core.commands import ComposeCommands
from riff.core.state import AppState


class TestSave:
    def test_save_does_nothing_without_generated_audio(self):
        state = AppState(mode_index=1)
        cmds = ComposeCommands(state)

        cmds.save()

        snap = state.snapshot()
        assert "no audio" in snap["status_msg"].lower()

    def test_save_writes_wav_file(self):
        state = AppState(mode_index=1)
        cmds = ComposeCommands(state)
        cmds.generated_audio = np.array([0.5, -0.5], dtype=np.float32)

        with tempfile.TemporaryDirectory() as tmp:
            cmds._save_dir = tmp
            cmds.save()

            snap = state.snapshot()
            assert "saved" in snap["status_msg"].lower()
            wav_files = [f for f in os.listdir(tmp) if f.endswith(".wav")]
            assert len(wav_files) == 1

    def test_save_mixes_when_both_audios_available(self):
        state = AppState(mode_index=1)
        cmds = ComposeCommands(state)
        cmds.source_audio = np.array([0.3, 0.2], dtype=np.float32)
        cmds.generated_audio = np.array([0.1, 0.4], dtype=np.float32)

        with tempfile.TemporaryDirectory() as tmp:
            cmds._save_dir = tmp
            cmds.save()

            wav_files = [f for f in os.listdir(tmp) if f.endswith(".wav")]
            assert len(wav_files) == 1


class TestPlayMix:
    def test_play_mix_does_nothing_without_both_audios(self):
        state = AppState(mode_index=1)
        cmds = ComposeCommands(state)

        cmds.play_mix()

        snap = state.snapshot()
        assert "no audio" in snap["status_msg"].lower()

    def test_play_mix_with_both_audios_starts_playback(self):
        state = AppState(mode_index=1)
        cmds = ComposeCommands(state)
        cmds.source_audio = np.array([0.5, 0.3], dtype=np.float32)
        cmds.generated_audio = np.array([0.2, 0.1], dtype=np.float32)

        cmds.play_mix()

        snap = state.snapshot()
        assert "playing" in snap["status_msg"].lower() or "mix" in snap["status_msg"].lower()
        state.update(running=False)
