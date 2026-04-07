from __future__ import annotations

import wave

import numpy as np

SAMPLE_RATE = 44100


def mix_audio(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    if len(a) == 0:
        return b.copy()
    if len(b) == 0:
        return a.copy()
    length = max(len(a), len(b))
    padded_a = np.zeros(length, dtype=np.float32)
    padded_b = np.zeros(length, dtype=np.float32)
    padded_a[: len(a)] = a
    padded_b[: len(b)] = b
    mixed = padded_a + padded_b
    peak = np.max(np.abs(mixed))
    if peak > 1.0:
        mixed /= peak
    return mixed


def save_wav(audio: np.ndarray, path: str) -> None:
    samples = np.clip(audio, -1.0, 1.0)
    int_samples = (samples * 32767).astype(np.int16)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(int_samples.tobytes())
