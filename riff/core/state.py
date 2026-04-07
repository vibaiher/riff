"""Shared application state with thread-safe access.

AppState is the single source of truth for all panels and threads.
Every field is read/written through thread-safe helpers so no external
code needs to acquire a lock directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock

# Timbres — affect synthesis parameters only, not note choice
TIMBRES = ["CLEAN", "WARM", "BRIGHT", "PAD", "RAW"]

MODES = ["FREE", "COMPOSE"]

# Engine list is populated lazily from the registry to avoid circular imports
_engine_list: list[str] | None = None


def _get_engines() -> list[str]:
    global _engine_list
    if _engine_list is None:
        from riff.ai.engine import list_engines

        _engine_list = list_engines()
    return _engine_list


def refresh_engines() -> None:
    """Force re-read of engine list (call after registering new engines)."""
    global _engine_list
    _engine_list = None


SPEEDS = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5]


@dataclass
class AppState:
    # ── YOU panel ─────────────────────────────────────────────────────────────
    frequency: float = 0.0  # detected fundamental frequency (Hz)
    note: str = "—"  # e.g. "C#"
    octave: int = 4  # e.g. 4  →  "C#4"
    bpm: float = 0.0  # estimated tempo
    db: float = -80.0  # signal level in dBFS
    waveform: list[float] = field(default_factory=list)  # amplitude per bin
    chords: list[str] = field(default_factory=list)  # suggested chords

    # ── Song panel (when --file is a MIDI) ─────────────────────────────────────
    song_note: str = "—"
    song_octave: int = 4
    song_position: float = 0.0
    song_bpm: float = 0.0
    song_upcoming: list[str] = field(default_factory=list)
    song_waveform: list[float] = field(default_factory=list)
    song_db: float = -80.0
    song_speed: float = 1.0
    song_finished: bool = False

    # ── Chord accumulation & generation ─────────────────────────────────────────
    captured_chords: list[str] = field(default_factory=list)  # e.g. ["Am", "F", "C", "G"]
    gen_status: str = ""  # "", "generating...", "playing", "done"
    gen_note_count: int = 0
    gen_duration: float = 0.0
    attached_file: str = ""  # path to attached audio/MIDI file
    compose_phase: str = ""  # "", "loaded", "listening", "generated"

    # ── Input mode (file picker, etc.) ──────────────────────────────────────
    input_mode: str = ""  # "" = normal, "file" = typing a file path
    input_buffer: str = ""  # text being typed

    # ── System ────────────────────────────────────────────────────────────────
    device_name: str = "Detecting..."
    device_index: int = -1
    latency_ms: float = 0.0
    mode_index: int = 0  # default: FREE (MODES index 0)
    timbre_index: int = 0  # default: CLEAN (TIMBRES index 0)
    engine_index: int = 0  # cycles through registered engines
    muted: bool = False
    capture_enabled: bool = True
    running: bool = True
    status_msg: str = ""  # transient flash message (footer)

    _lock: Lock = field(default_factory=Lock, compare=False, repr=False)
    _audio_queue = None

    def set_audio_queue(self, q) -> None:
        self._audio_queue = q

    @property
    def audio_queue(self):
        return self._audio_queue

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def mode(self) -> str:
        return MODES[self.mode_index % len(MODES)]

    @property
    def timbre(self) -> str:
        return TIMBRES[self.timbre_index % len(TIMBRES)]

    @property
    def engine(self) -> str:
        engines = _get_engines()
        if not engines:
            return "none"
        return engines[self.engine_index % len(engines)]

    # ── Thread-safe mutations ─────────────────────────────────────────────────

    _VALID_FIELDS: set | None = field(default=None, init=False, repr=False, compare=False)

    def _get_valid_fields(self) -> set:
        cls = type(self)
        if not hasattr(cls, "_cached_fields") or cls._cached_fields is None:
            cls._cached_fields = {f for f in self.__dataclass_fields__ if not f.startswith("_")}
        return cls._cached_fields

    def update(self, **kwargs) -> None:
        """Atomically set one or more fields."""
        invalid = set(kwargs) - self._get_valid_fields()
        if invalid:
            raise ValueError(f"Unknown AppState fields: {invalid}")
        with self._lock:
            for k, v in kwargs.items():
                setattr(self, k, v)

    def next_mode(self) -> None:
        with self._lock:
            self.mode_index = (self.mode_index + 1) % len(MODES)
            self.status_msg = f"Mode → {MODES[self.mode_index]}"

    def next_timbre(self) -> None:
        with self._lock:
            self.timbre_index = (self.timbre_index + 1) % len(TIMBRES)
            self.status_msg = f"Timbre → {TIMBRES[self.timbre_index % len(TIMBRES)]}"

    def next_engine(self) -> None:
        with self._lock:
            engines = _get_engines()
            if engines:
                self.engine_index = (self.engine_index + 1) % len(engines)
                self.status_msg = f"Engine → {engines[self.engine_index]}"

    def speed_up(self) -> None:
        with self._lock:
            idx = SPEEDS.index(self.song_speed) if self.song_speed in SPEEDS else 3
            if idx < len(SPEEDS) - 1:
                self.song_speed = SPEEDS[idx + 1]
                self.status_msg = f"Speed → {self.song_speed}x"

    def speed_down(self) -> None:
        with self._lock:
            idx = SPEEDS.index(self.song_speed) if self.song_speed in SPEEDS else 3
            if idx > 0:
                self.song_speed = SPEEDS[idx - 1]
                self.status_msg = f"Speed → {self.song_speed}x"

    def add_chord(self, chord: str) -> None:
        """Append a detected chord to the captured progression (no consecutive dupes)."""
        with self._lock:
            if not self.captured_chords or self.captured_chords[-1] != chord:
                self.captured_chords.append(chord)
                self.status_msg = f"Captured: {' | '.join(self.captured_chords[-6:])}"

    def clear_chords(self) -> None:
        with self._lock:
            self.captured_chords = []
            self.gen_status = ""
            self.gen_note_count = 0
            self.gen_duration = 0.0
            self.status_msg = "Chords cleared"

    def start_input(self, mode: str) -> None:
        with self._lock:
            self.input_mode = mode
            self.input_buffer = ""

    def cancel_input(self) -> None:
        with self._lock:
            self.input_mode = ""
            self.input_buffer = ""

    def confirm_input(self) -> str:
        with self._lock:
            result = self.input_buffer
            self.input_mode = ""
            self.input_buffer = ""
            return result

    def toggle_mute(self) -> None:
        with self._lock:
            self.muted = not self.muted
            self.status_msg = "MUTED" if self.muted else "UNMUTED"

    def snapshot(self) -> dict:
        """Return a consistent, immutable copy of all state for rendering."""
        engine_name = self.engine
        with self._lock:
            return {
                "frequency": self.frequency,
                "note": self.note,
                "octave": self.octave,
                "bpm": self.bpm,
                "db": self.db,
                "waveform": list(self.waveform),
                "chords": list(self.chords),
                "song_note": self.song_note,
                "song_octave": self.song_octave,
                "song_position": self.song_position,
                "song_bpm": self.song_bpm,
                "song_upcoming": list(self.song_upcoming),
                "song_waveform": list(self.song_waveform),
                "song_db": self.song_db,
                "song_speed": self.song_speed,
                "song_finished": self.song_finished,
                "captured_chords": list(self.captured_chords),
                "gen_status": self.gen_status,
                "gen_note_count": self.gen_note_count,
                "gen_duration": self.gen_duration,
                "attached_file": self.attached_file,
                "compose_phase": self.compose_phase,
                "input_mode": self.input_mode,
                "input_buffer": self.input_buffer,
                "mode": self.mode,
                "engine": engine_name,
                "device_name": self.device_name,
                "latency_ms": self.latency_ms,
                "timbre": self.timbre,
                "muted": self.muted,
                "capture_enabled": self.capture_enabled,
                "running": self.running,
                "status_msg": self.status_msg,
            }
