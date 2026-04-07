"""Tests for audio mixing and saving."""

import os
import tempfile
import wave

import numpy as np

from riff.audio.mix import mix_audio, save_wav, SAMPLE_RATE


class TestMixAudio:
    def test_mix_equal_length_sums(self):
        a = np.array([0.5, 0.3], dtype=np.float32)
        b = np.array([0.2, 0.1], dtype=np.float32)

        result = mix_audio(a, b)

        np.testing.assert_allclose(result, [0.7, 0.4], atol=1e-6)

    def test_mix_different_lengths_pads_shorter(self):
        a = np.array([0.5, 0.3, 0.1], dtype=np.float32)
        b = np.array([0.2], dtype=np.float32)

        result = mix_audio(a, b)

        assert len(result) == 3
        np.testing.assert_allclose(result, [0.7, 0.3, 0.1], atol=1e-6)

    def test_mix_with_empty_returns_other(self):
        a = np.array([0.5, 0.3], dtype=np.float32)
        b = np.array([], dtype=np.float32)

        result = mix_audio(a, b)

        np.testing.assert_allclose(result, [0.5, 0.3], atol=1e-6)

    def test_mix_both_empty(self):
        a = np.array([], dtype=np.float32)
        b = np.array([], dtype=np.float32)

        result = mix_audio(a, b)

        assert len(result) == 0

    def test_mix_normalizes_to_prevent_clipping(self):
        a = np.array([0.8, 0.9], dtype=np.float32)
        b = np.array([0.8, 0.9], dtype=np.float32)

        result = mix_audio(a, b)

        assert np.max(np.abs(result)) <= 1.0


class TestSaveWav:
    def test_save_creates_valid_wav(self):
        audio = np.array([0.5, -0.5, 0.3], dtype=np.float32)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.wav")

            save_wav(audio, path)

            assert os.path.isfile(path)
            with wave.open(path, "r") as wf:
                assert wf.getnframes() > 0

    def test_saved_file_has_correct_sample_rate(self):
        audio = np.array([0.1, 0.2], dtype=np.float32)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.wav")

            save_wav(audio, path)

            with wave.open(path, "r") as wf:
                assert wf.getframerate() == SAMPLE_RATE
