"""Shared application state with thread-safe access.

AppState is the single source of truth for all panels and threads.
Every field is read/written through thread-safe helpers so no external
code needs to acquire a lock directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock

MODES = ["FREE", "COMPOSE"]

_engine_list: list[str] | None = None


def _get_engines() -> list[str]:
    global _engine_list
    if _engine_list is None:
        from riff.ai.engine import list_engines

        _engine_list = list_engines()
    return _engine_list


def refresh_engines() -> None:
    global _engine_list
    _engine_list = None


@dataclass
class AppState:
    # ── YOU panel ─────────────────────────────────────────────────────────────
    frequency: float = 0.0
    note: str = "—"
    octave: int = 4
    bpm: float = 0.0
    db: float = -80.0
    waveform: list[float] = field(default_factory=list)
    chords: list[str] = field(default_factory=list)

    # ── Chord accumulation & generation ───────────────────────────────────────
    captured_chords: list[str] = field(default_factory=list)
    gen_status: str = ""
    gen_note_count: int = 0
    gen_duration: float = 0.0
    attached_file: str = ""
    compose_phase: str = ""

    # ── System ────────────────────────────────────────────────────────────────
    device_name: str = "Detecting..."
    device_index: int = -1
    latency_ms: float = 0.0
    mode_index: int = 0
    engine_index: int = 0
    muted: bool = False
    capture_enabled: bool = True
    running: bool = True
    status_msg: str = ""

    _lock: Lock = field(default_factory=Lock, compare=False, repr=False)
    _audio_queue = None

    def set_audio_queue(self, q) -> None:
        self._audio_queue = q

    @property
    def audio_queue(self):
        return self._audio_queue

    @property
    def mode(self) -> str:
        return MODES[self.mode_index % len(MODES)]

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

    def next_engine(self) -> None:
        with self._lock:
            engines = _get_engines()
            if engines:
                self.engine_index = (self.engine_index + 1) % len(engines)
                self.status_msg = f"Engine → {engines[self.engine_index]}"

    def add_chord(self, chord: str) -> None:
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

    def toggle_mute(self) -> None:
        with self._lock:
            self.muted = not self.muted
            self.status_msg = "MUTED" if self.muted else "UNMUTED"

    def snapshot(self) -> dict:
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
                "captured_chords": list(self.captured_chords),
                "gen_status": self.gen_status,
                "gen_note_count": self.gen_note_count,
                "gen_duration": self.gen_duration,
                "attached_file": self.attached_file,
                "compose_phase": self.compose_phase,
                "mode": self.mode,
                "engine": engine_name,
                "device_name": self.device_name,
                "latency_ms": self.latency_ms,
                "muted": self.muted,
                "capture_enabled": self.capture_enabled,
                "running": self.running,
                "status_msg": self.status_msg,
            }
