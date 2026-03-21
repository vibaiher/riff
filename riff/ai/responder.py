"""Adaptive Markov melodic responder for RIFF.

Listens for note events from AudioAnalyzer, learns the user's playing style
via an adaptive Markov model, and generates musically coherent phrase responses.

Architecture: daemon thread, AppState writes, start()/stop() lifecycle.
"""
from __future__ import annotations

import queue
import random
import threading
import time
from collections import defaultdict, deque, namedtuple
from typing import Dict, List, Optional, Tuple

import librosa
import numpy as np
import sounddevice as sd

from ..audio.analyzer import WAVEFORM_POINTS, downsample_peaks
from ..audio.capture import SAMPLE_RATE

# ── Data ─────────────────────────────────────────────────────────────────────

NoteEvent = namedtuple("NoteEvent", ["note", "octave", "bpm", "db", "time"])

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

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

SILENCE_TIMEOUT    = 5.0   # seconds of silence → new song (reset phrase, keep model)
LISTEN_DURATION    = 8.0   # seconds of listening before first response
LISTEN_MIN_NOTES   = 12    # minimum notes to collect during listening phase
DENSITY_WINDOW     = 2.0   # rolling window in seconds
MID_OCTAVE         = 4     # pivot for complementary register

RESOLUTION_DEGREES = {0, 4, 7}  # I, III, V (semitones from scale root)

# Timbre synthesis parameters
TIMBRE_PARAMS = {
    "CLEAN":  {"decay": 0.994,  "warmth": 0.0, "drive": 0.0,  "attack_ms": 5,  "release": 1.0},
    "WARM":   {"decay": 0.9975, "warmth": 0.6, "drive": 0.0,  "attack_ms": 8,  "release": 1.2},
    "BRIGHT": {"decay": 0.994,  "warmth": 0.0, "drive": 1.4,  "attack_ms": 3,  "release": 0.8},
    "PAD":    {"decay": 0.997,  "warmth": 0.3, "drive": 0.0,  "attack_ms": 50, "release": 2.0},
    "RAW":    {"decay": 0.990,  "warmth": 0.0, "drive": 2.5,  "attack_ms": 2,  "release": 0.6},
}


# ── Adaptive Markov model ────────────────────────────────────────────────────

class AdaptiveMarkov:
    """N-gram Markov model with variable order and intelligent fallback.

    Order grows with accumulated notes:
      Phase 1 (0-49 notes)    → N=4
      Phase 2 (50-149 notes)  → N=8
      Phase 3 (150-299 notes) → N=12
      Phase 4 (300+ notes)    → N=16

    Fallback chain: N=16 → 12 → 8 → 4 → scale tones.
    Never silence, never out of scale.

    Thread-safe: learn() and generate() can run from different threads.
    """

    _FALLBACK_CHAIN = [16, 12, 8, 4]

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tables: Dict[int, Dict[tuple, Dict[int, int]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(int))
        )
        self._interval_history: List[int] = []
        self._note_count = 0
        self._generate_attempts = 0
        self._generate_exact_hits = 0

    @property
    def current_order(self) -> int:
        return self._phase_max_order()

    @property
    def notes_learned(self) -> int:
        return self._note_count

    @property
    def phase(self) -> int:
        n = self._note_count
        if n >= 300:
            return 4
        if n >= 150:
            return 3
        if n >= 50:
            return 2
        return 1

    @property
    def confidence(self) -> float:
        if self._generate_attempts == 0:
            return 0.0
        return self._generate_exact_hits / self._generate_attempts

    def learn(self, note_pc: int, prev_pc: Optional[int]) -> None:
        """Feed one note (pitch class 0-11) into the model. Thread-safe."""
        with self._lock:
            if prev_pc is not None:
                interval = (note_pc - prev_pc) % 12
                self._interval_history.append(interval)
                max_order = self._phase_max_order()
                for order in range(1, max_order + 1):
                    if len(self._interval_history) >= order + 1:
                        ctx = tuple(self._interval_history[-(order + 1):-1])
                        self._tables[order][ctx][interval] += 1
                self._tables[0][()][interval] += 1
            self._note_count += 1

    def generate(self, scale_pcs: set[int], root_pc: int) -> int:
        """Generate next interval via fallback chain. Thread-safe."""
        with self._lock:
            self._generate_attempts += 1
            max_order = self._phase_max_order()
            history_len = len(self._interval_history)
            chain = [o for o in self._FALLBACK_CHAIN if o <= max_order]
            is_first = True

            for cap in chain:
                start_order = min(cap, history_len)
                result = self._try_range(start_order, scale_pcs, root_pc)
                if result is not None:
                    if is_first:
                        self._generate_exact_hits += 1
                    return result
                is_first = False

            return self._scale_fallback(scale_pcs, root_pc)

    def _phase_max_order(self) -> int:
        n = self._note_count
        if n >= 300:
            return 16
        if n >= 150:
            return 12
        if n >= 50:
            return 8
        return 4

    def _try_range(self, start_order: int, scale_pcs: set[int], root_pc: int) -> Optional[int]:
        for order in range(start_order, -1, -1):
            if order == 0:
                ctx = ()
            else:
                if len(self._interval_history) < order:
                    continue
                ctx = tuple(self._interval_history[-order:])
            table = self._tables[order].get(ctx)
            if not table:
                continue
            filtered = {iv: cnt for iv, cnt in table.items()
                        if (root_pc + iv) % 12 in scale_pcs}
            if not filtered:
                continue
            intervals = list(filtered.keys())
            weights = np.array([filtered[i] for i in intervals], dtype=float)
            weights /= weights.sum()
            return int(np.random.choice(intervals, p=weights))
        return None

    def _scale_fallback(self, scale_pcs: set[int], root_pc: int) -> int:
        scale_list = sorted(scale_pcs)
        target = random.choice(scale_list)
        return (target - root_pc) % 12


# ── Density tracker ──────────────────────────────────────────────────────────

class DensityTracker:
    """Tracks notes-per-second over a rolling window."""

    def __init__(self) -> None:
        self._timestamps: deque = deque()

    def record(self, ts: float) -> None:
        self._timestamps.append(ts)
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


# ── Chord window ─────────────────────────────────────────────────────────────

_CHORD_WINDOW_SECS = 1.5


class ChordWindow:
    """Detects chords by accumulating pitch classes over a rolling window."""

    def __init__(self) -> None:
        self._entries: deque = deque()

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
        best: List[tuple] = []
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
        return [f"{NOTE_NAMES[r]}{q}" for _, _, r, q in best[:2]]


def _db_to_scalar(db: float) -> float:
    """Map dBFS [-60, -20] to volume scalar [0.1, 1.0]."""
    clamped = max(-60.0, min(-20.0, db))
    return (clamped + 60.0) / 40.0 * 0.9 + 0.1


def _detect_scale(pcs: List[int]) -> set[int]:
    """Detect the most likely scale from accumulated pitch classes."""
    if not pcs:
        return set(range(12))
    unique = set(pcs)
    major = [0, 2, 4, 5, 7, 9, 11]
    minor = [0, 2, 3, 5, 7, 8, 10]
    best_root = 0
    best_mode = major
    best_score = -1
    for root in range(12):
        for mode in (major, minor):
            scale_pcs = {(root + s) % 12 for s in mode}
            score = len(unique & scale_pcs)
            if score > best_score:
                best_score = score
                best_root = root
                best_mode = mode
    return {(best_root + s) % 12 for s in best_mode}


def _ks_string(hz: float, duration: float, sr: int, decay: float, warmth: float = 0.0) -> np.ndarray:
    """Karplus-Strong plucked string synthesis."""
    period = max(2, int(round(sr / hz)))
    n = int(sr * duration)
    buf = np.random.uniform(-1.0, 1.0, period + n + 1)
    if warmth > 0.0:
        k = np.array([warmth * 0.5, 1.0 - warmth, warmth * 0.5])
        buf[:period] = np.convolve(buf[:period], k, mode="same")
    for i in range(n):
        buf[period + i] = decay * 0.5 * (buf[i] + buf[i + 1])
    return buf[period : period + n].astype(np.float32)


# ── Responder thread ─────────────────────────────────────────────────────────

class RiffResponder:
    """Daemon thread that reads NoteEvents, learns the user's style via
    AdaptiveMarkov, and generates melodic phrase responses."""

    def __init__(self, state, note_queue: queue.Queue) -> None:
        self.state = state
        self._note_queue = note_queue
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._markov = AdaptiveMarkov()

        self._listening = True
        self._listen_start: float = 0.0
        self._listen_notes: int = 0
        self._accumulated_pcs: List[int] = []
        self._prev_pc: Optional[int] = None

        self._current_phrase: List[Tuple[str, int]] = []
        self._phrase_index: int = 0

        self._last_event_time: float = 0.0
        self._last_user_note: Optional[NoteEvent] = None
        self._density = DensityTracker()
        self._chord_window = ChordWindow()
        self._volume_ema: float = 0.5
        self._recent_midi: deque = deque(maxlen=12)

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._running = True
        self._listening = True
        self._listen_start = time.time()
        self.state.update(riff_listening=True, riff_model="Markov")
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="riff-responder",
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
        events: List[NoteEvent] = []
        try:
            while True:
                events.append(self._note_queue.get_nowait())
        except queue.Empty:
            pass

        now = time.time()

        for ev in events:
            if ev.note not in NOTE_NAMES:
                continue
            pc = NOTE_NAMES.index(ev.note)
            self._markov.learn(pc, self._prev_pc)
            self._accumulated_pcs.append(pc)
            self._prev_pc = pc
            self._last_event_time = now
            self._last_user_note = ev
            self._density.record(now)
            self._chord_window.record(ev.note, now)
            self._recent_midi.append(pc + ev.octave * 12)

            if self._listening:
                self._listen_notes += 1

        # Silence timeout → new song (reset phrase, keep model)
        if self._last_event_time > 0 and (now - self._last_event_time) > SILENCE_TIMEOUT:
            self._current_phrase = []
            self._phrase_index = 0
            self._prev_pc = None
            self._listening = True
            self._listen_start = now
            self._listen_notes = 0
            self.state.update(
                riff_active=False, riff_waveform=[], riff_note="—",
                riff_next_note="—", riff_density=0.0, riff_listening=True,
            )
            time.sleep(0.1)
            return

        # Listening phase
        if self._listening:
            elapsed = now - self._listen_start
            if elapsed >= LISTEN_DURATION or self._listen_notes >= LISTEN_MIN_NOTES:
                if self._listen_notes >= 3:
                    self._listening = False
                    self.state.update(riff_listening=False)
            self.state.update(
                riff_listening=True,
                riff_density=self._density.notes_per_second(),
                markov_order=self._markov.current_order,
                markov_learned=self._markov.notes_learned,
                markov_phase=self._markov.phase,
                markov_confidence=self._markov.confidence,
            )
            time.sleep(0.05)
            return

        if not self._last_user_note:
            time.sleep(0.05)
            return

        if self._phrase_index >= len(self._current_phrase):
            self._generate_phrase()

        if events and self._phrase_index < len(self._current_phrase):
            self._adapt_phrase()

        if self._phrase_index < len(self._current_phrase):
            self._play_phrase_note()
        else:
            time.sleep(0.05)

    # ── Phrase generation ─────────────────────────────────────────────────────

    def _phrase_length_for_bpm(self, bpm: float) -> int:
        if bpm < 80:
            return random.randint(6, 8)
        elif bpm <= 120:
            return random.randint(4, 6)
        else:
            return random.randint(3, 4)

    def _detect_user_contour(self) -> int:
        """Return +1 (ascending), -1 (descending), 0 (flat)."""
        if len(self._recent_midi) < 3:
            return 0
        recent = list(self._recent_midi)[-6:]
        diffs = [recent[i + 1] - recent[i] for i in range(len(recent) - 1)]
        total = sum(diffs)
        if total > 2:
            return 1
        elif total < -2:
            return -1
        return 0

    def _generate_phrase(self) -> None:
        user = self._last_user_note
        if not user or user.note not in NOTE_NAMES:
            return

        bpm = max(user.bpm or 60.0, 60.0)
        length = self._phrase_length_for_bpm(bpm)
        scale_pcs = _detect_scale(self._accumulated_pcs)
        root_pc = NOTE_NAMES.index(user.note)

        user_contour = self._detect_user_contour()
        riff_direction = -user_contour

        phrase: List[Tuple[str, int]] = []
        prev_oct = user.octave
        target_oct = 2 * MID_OCTAVE - user.octave

        for pos in range(length):
            interval = self._markov.generate(scale_pcs, root_pc)

            # Contour steering
            if riff_direction != 0 and pos < length - 1:
                if riff_direction > 0 and interval > 6:
                    small_up = [i for i in range(1, 6) if (root_pc + i) % 12 in scale_pcs]
                    if small_up:
                        interval = random.choice(small_up)
                elif riff_direction < 0 and interval < 6 and interval > 0:
                    down = [i for i in range(7, 12) if (root_pc + i) % 12 in scale_pcs]
                    if down:
                        interval = random.choice(down)

            # Last note: always resolve to I, III, or V
            if pos == length - 1:
                resolution = [i for i in RESOLUTION_DEGREES if (root_pc + i) % 12 in scale_pcs]
                if resolution:
                    interval = random.choice(resolution)

            note_pc = (root_pc + interval) % 12
            note_name = NOTE_NAMES[note_pc]

            oct_offset = int(np.random.choice([-1, 0, 0, 0, 1]))
            octave = np.clip(target_oct + oct_offset, max(2, prev_oct - 1), min(7, prev_oct + 1))
            octave = int(np.clip(octave, 2, 7))
            prev_oct = octave

            phrase.append((note_name, octave))
            root_pc = note_pc

        self._current_phrase = phrase
        self._phrase_index = 0

    def _adapt_phrase(self) -> None:
        """Recalculate remaining notes based on new user input."""
        user = self._last_user_note
        if not user or user.note not in NOTE_NAMES:
            return
        remaining = len(self._current_phrase) - self._phrase_index
        if remaining <= 0:
            return

        scale_pcs = _detect_scale(self._accumulated_pcs)
        root_pc = NOTE_NAMES.index(user.note)
        if self._phrase_index > 0:
            _, prev_oct = self._current_phrase[self._phrase_index - 1]
        else:
            prev_oct = user.octave
        target_oct = 2 * MID_OCTAVE - user.octave
        total_len = len(self._current_phrase)

        new_notes: List[Tuple[str, int]] = []
        for i in range(remaining):
            pos = self._phrase_index + i
            interval = self._markov.generate(scale_pcs, root_pc)
            if pos == total_len - 1:
                resolution = [iv for iv in RESOLUTION_DEGREES if (root_pc + iv) % 12 in scale_pcs]
                if resolution:
                    interval = random.choice(resolution)
            note_pc = (root_pc + interval) % 12
            note_name = NOTE_NAMES[note_pc]
            oct_offset = int(np.random.choice([-1, 0, 0, 0, 1]))
            octave = np.clip(target_oct + oct_offset, max(2, prev_oct - 1), min(7, prev_oct + 1))
            octave = int(np.clip(octave, 2, 7))
            prev_oct = octave
            new_notes.append((note_name, octave))
            root_pc = note_pc
        self._current_phrase[self._phrase_index:] = new_notes

    # ── Playback ──────────────────────────────────────────────────────────────

    def _velocity_shape(self, pos: int, length: int) -> float:
        """soft → crescendo → decrescendo. Returns [0.6, 1.0]."""
        if length <= 1:
            return 0.85
        t = pos / (length - 1)
        if t <= 0.6:
            shape = t / 0.6
        else:
            shape = 1.0 - (t - 0.6) / 0.4
        return 0.6 + 0.4 * shape

    def _play_phrase_note(self) -> None:
        snap = self.state.snapshot()
        if snap["muted"]:
            self._phrase_index += 1
            time.sleep(0.1)
            return

        note, octave = self._current_phrase[self._phrase_index]
        timbre = snap["timbre"]
        user = self._last_user_note
        phrase_len = len(self._current_phrase)

        bpm = max(user.bpm if user else 60.0, 60.0)
        eighth = 60.0 / bpm / 2.0
        quarter = 60.0 / bpm
        dotted_eighth = eighth * 1.5
        note_dur = random.choice([eighth, eighth, quarter, dotted_eighth])

        raw_vol = _db_to_scalar(user.db if user else -40.0)
        self._volume_ema = 0.3 * raw_vol + 0.7 * self._volume_ema
        vel_shape = self._velocity_shape(self._phrase_index, phrase_len)
        volume = self._volume_ema * vel_shape * random.uniform(0.92, 1.04)

        articulation = random.uniform(0.50, 0.90)
        play_dur = note_dur * articulation
        pre_delay = random.uniform(0.0, 0.025)

        next_idx = self._phrase_index + 1
        next_note = self._current_phrase[next_idx][0] if next_idx < phrase_len else "—"

        waveform = self._make_waveform(note, octave)
        density = self._density.notes_per_second()
        chords = self._chord_window.detect()

        self.state.update(
            riff_note=note, riff_octave=octave, riff_waveform=waveform,
            riff_active=True, riff_next_note=next_note,
            riff_db=librosa.amplitude_to_db(np.array([volume]), ref=1.0)[0],
            riff_chords=chords, riff_density=density, riff_listening=False,
            markov_order=self._markov.current_order,
            markov_learned=self._markov.notes_learned,
            markov_phase=self._markov.phase,
            markov_confidence=self._markov.confidence,
        )

        time.sleep(pre_delay)
        self._synthesize(note, octave, play_dur, timbre, volume)
        self._phrase_index += 1
        time.sleep(max(0.0, note_dur - pre_delay))

    def _synthesize(
        self, note: str, octave: int, duration: float, timbre: str, volume: float,
    ) -> None:
        try:
            hz = librosa.note_to_hz(f"{note}{octave}")
            n = int(SAMPLE_RATE * duration)
            params = TIMBRE_PARAMS.get(timbre, TIMBRE_PARAMS["CLEAN"])

            if timbre == "PAD":
                t = np.linspace(0, duration, n, endpoint=False)
                wave = (
                    np.sin(2 * np.pi * hz * t) +
                    0.3 * np.sin(2 * np.pi * 2 * hz * t) +
                    0.1 * np.sin(2 * np.pi * 3 * hz * t)
                )
                attack_s = params["attack_ms"] / 1000.0
                env = np.where(
                    t < attack_s,
                    t / max(attack_s, 0.001),
                    np.exp(-1.0 / params["release"] * (t - attack_s) / duration),
                )
                wave *= env
                base_vol = 0.28
            elif timbre == "RAW":
                wave = _ks_string(hz, duration, SAMPLE_RATE,
                                  decay=params["decay"], warmth=params["warmth"])
                noise = np.random.uniform(-0.15, 0.15, len(wave))
                wave = wave + noise[:len(wave)]
                drive = params["drive"]
                wave = np.tanh(wave * drive) / np.tanh(np.array(drive))
                base_vol = 0.32
            else:
                wave = _ks_string(hz, duration, SAMPLE_RATE,
                                  decay=params["decay"], warmth=params["warmth"])
                if params["drive"] > 0:
                    drive = params["drive"]
                    wave = np.tanh(wave * drive) / np.tanh(np.array(drive))
                base_vol = 0.35

            wave = wave.astype(np.float32)
            fade = min(int(SAMPLE_RATE * 0.01), n // 4)
            if fade > 0 and len(wave) >= 2 * fade:
                wave[:fade] *= np.linspace(0, 1, fade)
                wave[-fade:] *= np.linspace(1, 0, fade)

            wave *= base_vol * volume
            sd.play(wave, samplerate=SAMPLE_RATE)
        except Exception:
            pass

    def _make_waveform(self, note: str, octave: int) -> List[float]:
        try:
            hz = librosa.note_to_hz(f"{note}{octave}")
            sr = 8000
            duration = 0.3
            t = np.linspace(0, duration, int(sr * duration), endpoint=False)
            wave = np.sin(2 * np.pi * hz * t)
            envelope = np.exp(-4.0 * t / duration)
            wave = wave * envelope
            return downsample_peaks(np.abs(wave), WAVEFORM_POINTS)
        except Exception:
            return [0.0] * WAVEFORM_POINTS
