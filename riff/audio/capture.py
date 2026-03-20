"""Audio capture via sounddevice, plus FilePlayback for offline files.

AudioCapture  — live microphone/interface input (default mode)
FilePlayback  — reads an audio file and feeds it block-by-block at real-time
                pace into the same audio_queue interface.

Both expose: audio_queue, start(), stop()
"""
from __future__ import annotations

import os
import queue
import threading
import time
from typing import Optional

import numpy as np
import sounddevice as sd

# ── Stream parameters ─────────────────────────────────────────────────────────
SAMPLE_RATE = 44100      # Hz — Scarlett native rate
CHANNELS    = 1          # mono input
BLOCK_SIZE  = 1024       # ~23 ms per callback at 44 100 Hz
DTYPE       = np.float32


def find_input_device() -> tuple[int, str]:
    """
    Return (device_index, device_name) for the preferred input device.

    Search order:
      1. Focusrite Scarlett Solo (or any Focusrite/Scarlett device)
      2. sounddevice system default input
      3. First device with at least one input channel
    """
    devices = sd.query_devices()

    for idx, dev in enumerate(devices):
        name_lower = dev["name"].lower()
        if ("scarlett" in name_lower or "focusrite" in name_lower) \
                and dev["max_input_channels"] > 0:
            return idx, dev["name"]

    default_idx = sd.default.device[0]
    if isinstance(default_idx, int) and default_idx >= 0:
        return default_idx, devices[default_idx]["name"]

    for idx, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            return idx, dev["name"]

    return 0, "Default"


class AudioCapture:
    """
    Wraps a sounddevice InputStream and exposes `audio_queue`.

    Usage::

        capture = AudioCapture(state)
        capture.start()
        # consumer reads from capture.audio_queue
        capture.stop()
    """

    def __init__(self, state) -> None:
        self.state = state
        # maxsize prevents the queue from growing unbounded if the
        # analyzer falls behind; old blocks are silently dropped.
        self.audio_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=64)
        self._stream: Optional[sd.InputStream] = None

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        device_idx, device_name = find_input_device()
        self.state.update(device_name=device_name, device_index=device_idx)

        self._stream = sd.InputStream(
            device=device_idx,
            channels=CHANNELS,
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            dtype=DTYPE,
            callback=self._callback,
            latency="low",
        )
        self._stream.start()

        # Report actual hardware latency to UI
        latency_ms = self._stream.latency * 1000
        self.state.update(latency_ms=round(latency_ms, 1))

    def stop(self) -> None:
        if self._stream and self._stream.active:
            self._stream.stop()
            self._stream.close()

    # ── Private ───────────────────────────────────────────────────────────────

    def _callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info,
        status,
    ) -> None:
        """sounddevice real-time callback — runs on the audio thread.

        Must be as fast as possible; no heavy work here.
        """
        try:
            # indata shape: (frames, channels) — take mono channel 0
            self.audio_queue.put_nowait(indata[:, 0].copy())
        except queue.Full:
            pass  # silently drop if analyzer is behind


class FilePlayback:
    """
    Reads an audio file and pushes mono float32 blocks into audio_queue at
    real-time pace, mimicking the AudioCapture interface.

    Supports any format librosa can load (mp3, flac, wav, ogg, m4a, …).
    Automatically resamples to SAMPLE_RATE and converts to mono.

    When the file ends, sets state.running = False so RIFF exits cleanly.
    """

    def __init__(self, state, path: str) -> None:
        self.state = state
        self._path = path
        self.audio_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=64)
        self._thread: Optional[threading.Thread] = None
        self._stop_flag = False

    def start(self) -> None:
        name = os.path.basename(self._path)
        self.state.update(device_name=f"file: {name}", latency_ms=0.0)
        self._thread = threading.Thread(
            target=self._feed,
            daemon=True,
            name="riff-file-playback",
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_flag = True

    def _feed(self) -> None:
        import librosa  # local import — not needed in live-mic path

        try:
            audio, _ = librosa.load(self._path, sr=SAMPLE_RATE, mono=True)
        except Exception as exc:
            self.state.update(status_msg=f"[file] load error: {exc}", running=False)
            return

        block_dur = BLOCK_SIZE / SAMPLE_RATE
        total_blocks = len(audio) // BLOCK_SIZE

        for i in range(total_blocks):
            if self._stop_flag or not self.state.snapshot()["running"]:
                return
            block = audio[i * BLOCK_SIZE : (i + 1) * BLOCK_SIZE].astype(np.float32)
            try:
                self.audio_queue.put_nowait(block)
            except queue.Full:
                pass
            time.sleep(block_dur)

        # File finished — let RIFF drain and then quit
        time.sleep(2.0)
        self.state.update(running=False)
