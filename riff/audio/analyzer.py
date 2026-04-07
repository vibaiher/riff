"""Real-time audio analysis: pitch · BPM · level.

Runs in a dedicated background thread.  Consumes blocks from
AudioCapture.audio_queue and writes results into AppState.

Analysis schedule
─────────────────
  Every block  (~23 ms)  → RMS / dBFS + waveform display data
  Every 4 blocks (~93 ms) → pitch via librosa.pyin  (only when signal > SILENCE_DB)
  Every 3 s               → BPM via librosa.beat.beat_track
"""

from __future__ import annotations

import collections
import queue
import threading

import librosa
import numpy as np

from .capture import BLOCK_SIZE, SAMPLE_RATE

# ── Analysis constants ────────────────────────────────────────────────────────

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Suggested chords per root note (tonic, relative minor, subdominant, dominant7)
_NOTE_CHORDS: dict[str, list[str]] = {
    "C": ["C", "Am", "F", "G7"],
    "C#": ["C#", "A#m", "F#", "G#7"],
    "D": ["D", "Bm", "G", "A7"],
    "D#": ["D#", "Cm", "G#", "A#7"],
    "E": ["E", "C#m", "A", "B7"],
    "F": ["F", "Dm", "Bb", "C7"],
    "F#": ["F#", "D#m", "B", "C#7"],
    "G": ["G", "Em", "C", "D7"],
    "G#": ["G#", "Fm", "C#", "D#7"],
    "A": ["A", "F#m", "D", "E7"],
    "A#": ["A#", "Gm", "D#", "F7"],
    "B": ["B", "G#m", "E", "F#7"],
}

# Below this level pitch detection is skipped (avoids noise false positives)
# -65 dBFS accommodates room/speaker capture (mic picking up iPad through air)
SILENCE_DB = -65.0

# Number of consecutive blocks to accumulate before running pyin
# 4 × 1024 = 4096 samples ≈ 93 ms — good balance of latency vs accuracy
PITCH_FRAMES = 4

# Rolling buffer length for BPM estimation (~4 seconds of audio)
BPM_BUFFER_SAMPLES = SAMPLE_RATE * 4

# Rolling buffer for the waveform display (~300 ms)
WAVEFORM_BUFFER_SAMPLES = SAMPLE_RATE // 3

# Number of amplitude bins in the waveform display strip
WAVEFORM_POINTS = 48

# How many blocks between BPM re-estimates (~3 s)
BPM_UPDATE_BLOCKS = int(SAMPLE_RATE * 3 / BLOCK_SIZE)


# ── Helpers ───────────────────────────────────────────────────────────────────


def note_to_chords(note: str) -> list[str]:
    """Return the 4 most contextual chords for a given root note."""
    return _NOTE_CHORDS.get(note, [])


def freq_to_note(freq: float) -> tuple[str, int]:
    """Convert Hz → (note_name, octave).  E.g. 440 Hz → ('A', 4)."""
    if freq <= 0:
        return "—", 0
    midi = 12.0 * np.log2(freq / 440.0) + 69.0
    midi_int = int(round(midi))
    if not (0 <= midi_int <= 127):
        return "—", 0
    return NOTE_NAMES[midi_int % 12], (midi_int // 12) - 1


def rms_to_db(rms: float) -> float:
    """RMS amplitude → dBFS.  Floor at -80 dB."""
    return 20.0 * np.log10(max(rms, 1e-10))


def downsample_peaks(audio: np.ndarray, n_points: int) -> list[float]:
    """Reduce *audio* to *n_points* values by taking peak per segment."""
    if len(audio) == 0:
        return [0.0] * n_points
    audio = np.abs(audio)
    segments = np.array_split(audio, n_points)
    return [float(np.max(s)) if len(s) else 0.0 for s in segments]


# ── Analyzer ─────────────────────────────────────────────────────────────────


class AudioAnalyzer:
    """
    Consumes raw audio blocks and writes analysis results to AppState.

    Usage::

        analyzer = AudioAnalyzer(state, capture.audio_queue)
        analyzer.start()
        # runs until analyzer.stop() or state.running becomes False
        analyzer.stop()
    """

    def __init__(self, state, audio_queue: queue.Queue) -> None:
        self.state = state
        self._queue = audio_queue
        self._running = False
        self._thread: threading.Thread | None = None

        # Accumulation buffers
        self._pitch_buf: list[np.ndarray] = []
        self._bpm_buf: collections.deque = collections.deque(maxlen=BPM_BUFFER_SAMPLES)
        self._waveform_buf: collections.deque = collections.deque(maxlen=WAVEFORM_BUFFER_SAMPLES)

        self._bpm_counter = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="riff-analyzer",
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    # ── Private ───────────────────────────────────────────────────────────────

    def _loop(self) -> None:
        # Pre-compile numba kernels used by librosa.pyin so the first
        # real note doesn't stutter.
        self._warmup()

        while self._running:
            try:
                chunk = self._queue.get(timeout=0.05)
            except queue.Empty:
                continue
            self._process(chunk)

    def _warmup(self) -> None:
        """Run pyin on a silent buffer to trigger JIT compilation."""
        silence = np.zeros(BLOCK_SIZE * PITCH_FRAMES, dtype=np.float32)
        try:
            librosa.pyin(
                silence,
                fmin=librosa.note_to_hz("C2"),
                fmax=librosa.note_to_hz("C8"),
                sr=SAMPLE_RATE,
            )
        except Exception:
            pass

    def _process(self, chunk: np.ndarray) -> None:
        if not self.state.snapshot().get("capture_enabled", True):
            return

        # ── 1. Feed rolling buffers ───────────────────────────────────────────
        self._waveform_buf.extend(chunk)
        self._bpm_buf.extend(chunk)
        self._pitch_buf.append(chunk)
        self._bpm_counter += 1

        # ── 2. Per-block: waveform display + level ────────────────────────────
        wf_data = downsample_peaks(np.array(self._waveform_buf), WAVEFORM_POINTS)
        rms = float(np.sqrt(np.mean(chunk**2)))
        db = rms_to_db(rms)

        updates: dict = {"db": db, "waveform": wf_data}

        # ── 3. Every PITCH_FRAMES blocks: pitch detection ─────────────────────
        if len(self._pitch_buf) >= PITCH_FRAMES:
            audio = np.concatenate(self._pitch_buf)
            self._pitch_buf.clear()

            if db > SILENCE_DB:
                freq = self._detect_pitch(audio)
                if freq is not None:
                    note, octave = freq_to_note(freq)
                    chords = note_to_chords(note)
                    updates.update(
                        frequency=freq,
                        note=note,
                        octave=octave,
                        chords=chords,
                    )
                    # Feed first suggested chord into accumulation buffer (COMPOSE mode only)
                    if chords and self.state.snapshot().get("mode") == "COMPOSE":
                        self.state.add_chord(chords[0])
                else:
                    updates.update(note="—", frequency=0.0, chords=[])
            else:
                # Silence — clear note display
                updates.update(note="—", frequency=0.0, chords=[])

        # ── 4. Every BPM_UPDATE_BLOCKS: tempo estimation ──────────────────────
        if self._bpm_counter >= BPM_UPDATE_BLOCKS:
            self._bpm_counter = 0
            bpm = self._estimate_bpm()
            if bpm > 0:
                updates["bpm"] = bpm

        self.state.update(**updates)

    def _detect_pitch(self, audio: np.ndarray) -> float | None:
        """
        Probabilistic YIN (pyin) pitch detection for monophonic instruments.

        Covers guitar (low E ≈ 82 Hz) to above ukulele high A (≈ 880 Hz)
        and well into the harmonic range used by soprano voices / whistles.
        """
        try:
            f0, voiced_flag, _ = librosa.pyin(
                audio,
                fmin=librosa.note_to_hz("C2"),  # ~65 Hz
                fmax=librosa.note_to_hz("C8"),  # ~4186 Hz
                sr=SAMPLE_RATE,
            )
            # Use median of voiced frames to suppress transient noise
            voiced = f0[voiced_flag & ~np.isnan(f0)]
            return float(np.median(voiced)) if len(voiced) > 0 else None
        except Exception:
            return None

    def _estimate_bpm(self) -> float:
        """Beat-track the rolling BPM buffer (~4 s of audio)."""
        try:
            audio = np.array(self._bpm_buf, dtype=np.float32)
            tempo, _ = librosa.beat.beat_track(y=audio, sr=SAMPLE_RATE)
            # librosa 0.10 returns a scalar; older versions may return an array
            return float(tempo) if np.ndim(tempo) == 0 else float(tempo[0])
        except Exception:
            return 0.0
