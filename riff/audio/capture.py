"""Audio capture via sounddevice.

Finds the Focusrite Scarlett Solo automatically (falls back to system default),
opens a low-latency InputStream, and pushes mono float32 blocks into
`audio_queue` for the downstream analyzer thread.
"""
from __future__ import annotations

import queue
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
