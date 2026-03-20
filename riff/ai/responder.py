"""Markov-based melodic responder for RIFF.

Listens for note events from AudioAnalyzer and generates a musically
coherent response melody using Markov interval transitions per mode.

Architecture mirrors AudioAnalyzer: daemon thread, AppState writes,
start()/stop() lifecycle.
"""
from __future__ import annotations

import queue
import random
import threading
import time
from collections import deque, namedtuple
from typing import List, Optional

import librosa
import numpy as np
import sounddevice as sd

from ..audio.analyzer import WAVEFORM_POINTS, downsample_peaks
from ..audio.capture import SAMPLE_RATE

# ── Data ─────────────────────────────────────────────────────────────────────

NoteEvent = namedtuple("NoteEvent", ["note", "octave", "bpm", "db", "time"])

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Order-0 interval weights (semitones above root) per mode.
TRANSITIONS: dict[str, dict[int, int]] = {
    "BLUES":   {0: 2, 3: 5, 5: 4, 6: 2, 7: 5, 10: 4},
    "JAZZ":    {0: 1, 2: 3, 3: 2, 4: 4, 5: 2, 7: 5, 9: 2, 10: 3, 11: 3},
    "AMBIENT": {0: 5, 2: 4, 4: 3, 5: 3, 7: 4, 9: 2},
    "ROCK":    {0: 3, 2: 2, 4: 3, 5: 4, 7: 5},
    "FREE":    {i: 1 for i in range(12)},
}

# Order-1 Markov transitions: mode → prev_interval → {next_interval: weight}
TRANSITIONS_O1: dict[str, dict[int, dict[int, int]]] = {
    "BLUES": {
        0:  {3: 5, 5: 4, 7: 3, 10: 2},
        3:  {5: 4, 7: 3, 0: 3, 6: 2},
        5:  {7: 5, 10: 3, 0: 2, 3: 2},
        6:  {7: 8, 5: 2, 0: 1},
        7:  {10: 4, 0: 3, 5: 3, 3: 2},
        10: {0: 6, 3: 3, 7: 2},
    },
    "JAZZ": {
        0:  {4: 3, 7: 4, 9: 3, 2: 2, 11: 2},
        2:  {4: 4, 5: 3, 10: 2, 0: 2},
        4:  {5: 4, 7: 4, 11: 2, 2: 2},
        5:  {4: 3, 7: 4, 9: 3, 0: 2},
        7:  {9: 4, 10: 3, 0: 3, 5: 2},
        9:  {10: 3, 7: 3, 0: 2, 11: 2},
        10: {0: 4, 9: 3, 7: 2, 11: 2},
        11: {0: 6, 9: 3, 7: 2},
    },
    "AMBIENT": {
        0:  {2: 4, 5: 3, 7: 4, 9: 2},
        2:  {0: 3, 4: 4, 7: 3},
        4:  {2: 3, 5: 4, 7: 3},
        5:  {4: 3, 7: 4, 0: 2, 9: 2},
        7:  {5: 3, 9: 4, 0: 3},
        9:  {7: 4, 5: 3, 0: 3},
    },
    "ROCK": {
        0:  {4: 3, 5: 4, 7: 5},
        2:  {0: 3, 4: 4, 5: 3},
        4:  {2: 3, 5: 3, 7: 4},
        5:  {4: 3, 7: 5, 0: 2},
        7:  {5: 3, 0: 4, 2: 3},
    },
}

# Chord quality → semitone intervals from root
CHORD_INTERVALS: dict[str, list[int]] = {
    "":     [0, 4, 7],
    "m":    [0, 3, 7],
    "7":    [0, 4, 7, 10],
    "m7":   [0, 3, 7, 10],
    "maj7": [0, 4, 7, 11],
    "dim":  [0, 3, 6],
    "aug":  [0, 4, 8],
    "sus2": [0, 2, 7],
    "sus4": [0, 5, 7],
}

_FLAT_TO_SHARP = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}

SILENCE_TIMEOUT = 2.0   # seconds of silence before RIFF deactivates
PHRASE_GAP      = 0.8   # gap that resets melody context (new phrase)
HISTORY_LEN     = 8     # notes remembered to avoid obvious loops

# Density gating constants
DENSITY_WINDOW     = 2.0   # rolling window in seconds
DENSITY_GATE_LOW   = 2.0   # nps below this → always respond
DENSITY_GATE_HIGH  = 5.0   # nps above this → floor probability
DENSITY_GATE_FLOOR = 0.2   # minimum response probability

MID_OCTAVE = 4  # pivot for complementary register


# ── Density tracker ───────────────────────────────────────────────────────────

class DensityTracker:
    """Tracks notes-per-second over a rolling window and gates RIFF responses."""

    def __init__(self) -> None:
        self._timestamps: deque = deque()

    def record(self, ts: float) -> None:
        self._timestamps.append(ts)
        # Prune old entries outside the window
        cutoff = ts - DENSITY_WINDOW
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

    def notes_per_second(self) -> float:
        if not self._timestamps:
            return 0.0
        now = time.time()
        cutoff = now - DENSITY_WINDOW
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
        return len(self._timestamps) / DENSITY_WINDOW

    def should_respond(self) -> bool:
        density = self.notes_per_second()
        if density <= DENSITY_GATE_LOW:
            p = 1.0
        elif density >= DENSITY_GATE_HIGH:
            p = DENSITY_GATE_FLOOR
        else:
            p = max(DENSITY_GATE_FLOOR, 1.0 - (density - DENSITY_GATE_LOW) * 0.8 / 3.0)
        return random.random() < p

    def duration_multiplier(self) -> float:
        density = self.notes_per_second()
        if density <= DENSITY_GATE_LOW:
            return 1.0
        elif density >= DENSITY_GATE_HIGH:
            return 2.0
        else:
            t = (density - DENSITY_GATE_LOW) / (DENSITY_GATE_HIGH - DENSITY_GATE_LOW)
            return 1.0 + t * 1.0


# ── Chord window ──────────────────────────────────────────────────────────────

_CHORD_WINDOW_SECS = 1.5


class ChordWindow:
    """Detects chords by accumulating pitch classes over a rolling window."""

    def __init__(self) -> None:
        self._entries: deque = deque()  # (timestamp, pitch_class)

    def record(self, note_name: str, ts: float) -> None:
        note_name = _FLAT_TO_SHARP.get(note_name, note_name)
        if note_name not in NOTE_NAMES:
            return
        pc = NOTE_NAMES.index(note_name)
        self._entries.append((ts, pc))

    def _prune(self, now: float) -> None:
        cutoff = now - _CHORD_WINDOW_SECS
        while self._entries and self._entries[0][0] < cutoff:
            self._entries.popleft()

    def detect(self) -> List[str]:
        now = time.time()
        self._prune(now)
        if not self._entries:
            return []

        window_pcs = [pc for _, pc in self._entries]
        unique_pcs = set(window_pcs)

        best: List[tuple] = []  # (score, root_count, root, quality)

        for root in range(12):
            for quality, intervals in CHORD_INTERVALS.items():
                chord_pcs = {(root + i) % 12 for i in intervals}
                matched = chord_pcs & unique_pcs
                required = len(chord_pcs)
                n_matched = len(matched)

                if n_matched == required:
                    score = 1.0
                elif n_matched >= 2 and required >= 2:
                    score = n_matched / required
                else:
                    continue

                root_count = window_pcs.count(root)
                best.append((score, root_count, root, quality))

        if not best:
            return []

        best.sort(key=lambda x: (x[0], x[1]), reverse=True)
        results = []
        for score, root_count, root, quality in best[:2]:
            results.append(f"{NOTE_NAMES[root]}{quality}")
        return results


def _chord_pitch_classes(chord_name: str) -> set[int]:
    """Parse a chord name and return the set of pitch class indices (0–11)."""
    if len(chord_name) >= 2 and chord_name[1] in ("#", "b"):
        root_str = chord_name[:2]
        quality  = chord_name[2:]
    else:
        root_str = chord_name[:1]
        quality  = chord_name[1:]
    root_str = _FLAT_TO_SHARP.get(root_str, root_str)
    if root_str not in NOTE_NAMES:
        return set()
    root_idx = NOTE_NAMES.index(root_str)
    intervals = CHORD_INTERVALS.get(quality, CHORD_INTERVALS[""])
    return {(root_idx + i) % 12 for i in intervals}


def _db_to_scalar(db: float) -> float:
    """Map dBFS [-60, -20] to volume scalar [0.1, 1.0]."""
    clamped = max(-60.0, min(-20.0, db))
    return (clamped + 60.0) / 40.0 * 0.9 + 0.1


def _ks_string(hz: float, duration: float, sr: int, decay: float, warmth: float = 0.0) -> np.ndarray:
    """Karplus-Strong plucked string synthesis.

    warmth > 0 low-pass filters the initial noise burst (warmer = bassier tone).
    decay controls sustain: ~0.994 for guitar, ~0.9975 for bass.
    """
    period = max(2, int(round(sr / hz)))
    n = int(sr * duration)
    buf = np.random.uniform(-1.0, 1.0, period + n + 1)
    if warmth > 0.0:
        k = np.array([warmth * 0.5, 1.0 - warmth, warmth * 0.5])
        buf[:period] = np.convolve(buf[:period], k, mode="same")
    for i in range(n):
        buf[period + i] = decay * 0.5 * (buf[i] + buf[i + 1])
    return buf[period : period + n].astype(np.float32)


# ── Markov generator ─────────────────────────────────────────────────────────

class MarkovMelodyGen:
    """Generates note responses by sampling intervals relative to the root."""

    def generate(
        self,
        root_note: str,
        mode: str,
        history: List[str],
        user_octave: int = 4,
        last_interval: Optional[int] = None,
        chords: Optional[List[str]] = None,
    ) -> tuple[str, int, int]:
        """Return (note_name, octave, chosen_interval) for a melodic response.

        Uses order-1 transitions when last_interval is available, falling
        back to order-0.  Boosts chord tones x2 and penalises recent repeats.
        Mirrors the user's octave with a small random offset.
        """
        # Order-1 → order-0 fallback
        o1_table = TRANSITIONS_O1.get(mode, {})
        if last_interval is not None and last_interval in o1_table:
            weights = dict(o1_table[last_interval])
        else:
            weights = dict(TRANSITIONS.get(mode, TRANSITIONS["FREE"]))

        root_idx = NOTE_NAMES.index(root_note)

        # Chord tone boost x2
        if chords:
            chord_pcs: set[int] = set()
            for ch in chords:
                chord_pcs |= _chord_pitch_classes(ch)
            for interval in list(weights.keys()):
                if (root_idx + interval) % 12 in chord_pcs:
                    weights[interval] = weights[interval] * 2

        # Penalise most recent note to avoid monotone repetition
        if history:
            last = history[-1]
            for interval, w in list(weights.items()):
                if NOTE_NAMES[(root_idx + interval) % 12] == last:
                    weights[interval] = max(1, w // 3)

        intervals = list(weights.keys())
        raw_weights = np.array([weights[i] for i in intervals], dtype=float)
        raw_weights /= raw_weights.sum()

        chosen_interval = int(np.random.choice(intervals, p=raw_weights))
        note = NOTE_NAMES[(root_idx + chosen_interval) % 12]

        # Complementary register: reflect around MID_OCTAVE instead of mirroring
        target = 2 * MID_OCTAVE - user_octave
        offset = int(np.random.choice([-1, 0, 0, 1]))
        octave = int(np.clip(target + offset, 2, 7))

        return note, octave, chosen_interval


# ── Responder thread ──────────────────────────────────────────────────────────

class RiffResponder:
    """
    Daemon thread that reads NoteEvents from a queue and writes melodic
    responses into AppState's riff_* fields.

    Usage::

        responder = RiffResponder(state, note_queue)
        responder.start()
        # runs until responder.stop() or state.running becomes False
        responder.stop()
    """

    def __init__(self, state, note_queue: queue.Queue, melody_gen=None) -> None:
        self.state = state
        self._note_queue = note_queue
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._gen = melody_gen if melody_gen is not None else MarkovMelodyGen()
        self._history: List[str] = []
        self._last_event_time: float = 0.0
        self._last_riff_interval: Optional[int] = None
        self._density = DensityTracker()
        self._chord_window = ChordWindow()

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="riff-responder",
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    # ── Private ───────────────────────────────────────────────────────────────

    def _loop(self) -> None:
        while self._running and self.state.snapshot()["running"]:
            try:
                self._tick()
            except Exception as exc:
                self.state.update(status_msg=f"[responder] {exc}")
                break

    def _tick(self) -> None:
        # Drain queue to get latest note (discard stale ones)
        latest: Optional[NoteEvent] = None
        try:
            while True:
                latest = self._note_queue.get_nowait()
        except queue.Empty:
            pass

        now = time.time()

        if latest is not None:
            # Phrase gap detection: reset context on a new phrase
            gap = (now - self._last_event_time) if self._last_event_time > 0 else 0.0
            self._last_event_time = now
            if gap > PHRASE_GAP:
                self._history.clear()
                self._last_riff_interval = None

            # Record for density tracking and chord detection
            self._density.record(now)
            self._chord_window.record(latest.note, now)

        # Check for silence timeout
        if self._last_event_time > 0 and (now - self._last_event_time) > SILENCE_TIMEOUT:
            self.state.update(riff_active=False, riff_waveform=[], riff_note="—", riff_next_note="—",
                              riff_density=0.0, riff_listening=False)
            time.sleep(0.1)
            return

        if latest is None:
            time.sleep(0.05)
            return

        # Density gating: update display fields and skip response if too dense
        current_density = self._density.notes_per_second()
        if not self._density.should_respond():
            self.state.update(riff_density=current_density, riff_listening=True)
            time.sleep(0.05)
            return

        # Phrase rest: ~15% chance RIFF breathes (skips a slot musically)
        if random.random() < 0.15:
            self.state.update(riff_density=current_density, riff_listening=True)
            bpm = max(latest.bpm or 0.0, 60.0)
            time.sleep(60.0 / bpm / 2.0)
            return

        # Compute rhythmic grid interval (eighth note), scaled by density
        bpm = max(latest.bpm or 0.0, 60.0)
        eighth_note_dur = 60.0 / bpm / 2.0
        eighth_note_dur *= self._density.duration_multiplier()

        # Get current mode + instrument + chords from state
        snap = self.state.snapshot()
        mode       = snap["mode"]
        instrument = snap["instrument"]
        detected_chords = self._chord_window.detect()
        chords = detected_chords if detected_chords else snap["chords"]
        root_note = latest.note

        if root_note not in NOTE_NAMES:
            time.sleep(0.05)
            return

        # Generate primary response note
        note, octave, chosen_interval = self._gen.generate(
            root_note, mode, self._history,
            user_octave=latest.octave,
            last_interval=self._last_riff_interval,
            chords=chords,
        )
        # Bass always plays in the low register regardless of user octave
        if instrument == "BASS":
            octave = int(np.clip(octave - 2, 1, 3))

        # Generate next note for the "upcoming" display
        next_note, _, _ = self._gen.generate(
            root_note, mode, self._history + [note],
            user_octave=latest.octave,
            last_interval=chosen_interval,
            chords=chords,
        )

        # Update history and track last interval
        self._history.append(note)
        if len(self._history) > HISTORY_LEN:
            self._history.pop(0)
        self._last_riff_interval = chosen_interval

        # Compute dynamics scalar from user's input level + micro-variation
        volume_scalar = _db_to_scalar(latest.db)
        volume_scalar *= random.uniform(0.82, 1.08)

        # Articulation: vary note duration independently from grid slot
        # (staccato ↔ near-legato), so notes breathe instead of all sounding equal
        articulation = random.uniform(0.45, 0.92)
        play_dur = eighth_note_dur * articulation

        # Humanize: small pre-delay (0–30 ms) so notes don't land on the exact grid
        pre_delay = random.uniform(0.0, 0.03)

        # Build visual waveform
        waveform = self._make_waveform(note, octave)

        self.state.update(
            riff_note=note,
            riff_octave=octave,
            riff_waveform=waveform,
            riff_active=True,
            riff_next_note=next_note,
            riff_db=librosa.amplitude_to_db(np.array([volume_scalar]), ref=1.0)[0],
            riff_chords=chords,
            riff_density=current_density,
            riff_listening=False,
        )

        # Play the note only if not muted
        time.sleep(pre_delay)
        if not snap["muted"]:
            self._play_note(note, octave, play_dur, instrument, mode, volume_scalar)
        time.sleep(max(0.0, eighth_note_dur - pre_delay))

    def _play_note(
        self,
        note: str,
        octave: int,
        duration: float,
        instrument: str = "GUITAR",
        mode: str = "ROCK",
        volume_scalar: float = 1.0,
    ) -> None:
        """Synthesize and play a note. Timbre is driven by instrument; mode
        is passed through for SYNTH which keeps the old mode-specific additive
        synthesis."""
        try:
            hz = librosa.note_to_hz(f"{note}{octave}")
            n  = int(SAMPLE_RATE * duration)

            if instrument == "GUITAR":
                # Karplus-Strong acoustic/electric guitar
                wave   = _ks_string(hz, duration, SAMPLE_RATE, decay=0.994, warmth=0.0)
                # Light overdrive for character
                wave   = np.tanh(wave * 1.4) / np.tanh(np.array(1.4))
                volume = 0.35

            elif instrument == "BASS":
                # Karplus-Strong bass: warmer burst, longer decay
                wave   = _ks_string(hz, duration, SAMPLE_RATE, decay=0.9975, warmth=0.6)
                volume = 0.50

            elif instrument == "PERC":
                # Pitched transient: sharp noise click + short resonant tail
                t      = np.linspace(0, duration, n, endpoint=False)
                click  = np.random.uniform(-1.0, 1.0, n) * np.exp(-40.0 * t / duration)
                body   = np.sin(2 * np.pi * hz * t) * np.exp(-18.0 * t / duration)
                wave   = 0.7 * click + 0.3 * body
                volume = 0.40

            else:
                # SYNTH — keep the existing mode-based additive synthesis
                t = np.linspace(0, duration, n, endpoint=False)
                if mode == "ROCK":
                    wave = (
                        1.00 * np.sin(2 * np.pi * 1 * hz * t) +
                        0.70 * np.sin(2 * np.pi * 2 * hz * t) +
                        0.50 * np.sin(2 * np.pi * 3 * hz * t) +
                        0.30 * np.sin(2 * np.pi * 4 * hz * t) +
                        0.20 * np.sin(2 * np.pi * 5 * hz * t) +
                        0.10 * np.sin(2 * np.pi * 6 * hz * t)
                    )
                    env  = np.where(t < 0.008,
                                    t / 0.008,
                                    np.exp(-5.0 * (t - 0.008) / duration) * 0.6 + 0.4 * np.exp(-0.8 * t))
                    wave *= env
                    wave  = np.tanh(wave * 1.8) / np.tanh(np.array(1.8))
                    volume = 0.30
                elif mode == "BLUES":
                    wave = (
                        1.00 * np.sin(2 * np.pi * 1 * hz * t) +
                        0.55 * np.sin(2 * np.pi * 2 * hz * t) +
                        0.25 * np.sin(2 * np.pi * 3 * hz * t) +
                        0.10 * np.sin(2 * np.pi * 4 * hz * t)
                    )
                    wave *= np.exp(-3.5 * t / duration)
                    wave  = np.tanh(wave * 1.3) / np.tanh(np.array(1.3))
                    volume = 0.32
                elif mode == "JAZZ":
                    wave = (
                        1.00 * np.sin(2 * np.pi * 1 * hz * t) +
                        0.40 * np.sin(2 * np.pi * 2 * hz * t) +
                        0.15 * np.sin(2 * np.pi * 3 * hz * t)
                    )
                    wave *= np.exp(-2.5 * t / duration)
                    volume = 0.33
                elif mode == "AMBIENT":
                    attack_dur = min(0.05, duration * 0.2)
                    env = np.where(t < attack_dur,
                                   t / attack_dur,
                                   np.exp(-1.2 * (t - attack_dur) / duration))
                    wave   = np.sin(2 * np.pi * hz * t) + 0.2 * np.sin(2 * np.pi * 2 * hz * t)
                    wave  *= env
                    volume = 0.28
                else:
                    wave   = np.sin(2 * np.pi * hz * t)
                    wave  *= np.exp(-3.0 * t / duration)
                    volume = 0.30

            wave = wave.astype(np.float32)

            # Anti-click fade in/out (10 ms)
            fade = min(int(SAMPLE_RATE * 0.01), n // 4)
            wave[:fade]  *= np.linspace(0, 1, fade)
            wave[-fade:] *= np.linspace(1, 0, fade)

            wave *= volume * volume_scalar
            sd.play(wave, samplerate=SAMPLE_RATE)
        except Exception:
            pass

    def _make_waveform(self, note: str, octave: int) -> List[float]:
        """Generate a sine wave with exponential decay for visual display."""
        try:
            note_str = f"{note}{octave}"
            hz = librosa.note_to_hz(note_str)
            sr = 8000  # low rate is enough for display
            duration = 0.3
            t = np.linspace(0, duration, int(sr * duration), endpoint=False)
            wave = np.sin(2 * np.pi * hz * t)
            envelope = np.exp(-4.0 * t / duration)
            wave = wave * envelope
            return downsample_peaks(np.abs(wave), WAVEFORM_POINTS)
        except Exception:
            return [0.0] * WAVEFORM_POINTS
