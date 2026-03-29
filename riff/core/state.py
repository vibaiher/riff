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

MODES = ["FREE", "PRACTICE", "EAR_TRAINING"]

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

    # ── System ────────────────────────────────────────────────────────────────
    device_name: str = "Detecting..."
    device_index: int = -1
    latency_ms: float = 0.0
    mode_index: int = 0  # default: FREE (MODES index 0)
    timbre_index: int = 0  # default: CLEAN (TIMBRES index 0)
    muted: bool = False
    running: bool = True
    status_msg: str = ""  # transient flash message (footer)

    _lock: Lock = field(default_factory=Lock, compare=False, repr=False)

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def mode(self) -> str:
        return MODES[self.mode_index % len(MODES)]

    @property
    def timbre(self) -> str:
        return TIMBRES[self.timbre_index % len(TIMBRES)]

    # ── Thread-safe mutations ─────────────────────────────────────────────────

    def update(self, **kwargs) -> None:
        """Atomically set one or more fields."""
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self, k) and not k.startswith("_"):
                    setattr(self, k, v)

    def next_mode(self) -> None:
        with self._lock:
            self.mode_index = (self.mode_index + 1) % len(MODES)
            self.status_msg = f"Mode → {MODES[self.mode_index]}"

    def next_timbre(self) -> None:
        with self._lock:
            self.timbre_index = (self.timbre_index + 1) % len(TIMBRES)
            self.status_msg = f"Timbre → {TIMBRES[self.timbre_index % len(TIMBRES)]}"

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

    def toggle_mute(self) -> None:
        with self._lock:
            self.muted = not self.muted
            self.status_msg = "MUTED" if self.muted else "UNMUTED"

    def snapshot(self) -> dict:
        """Return a consistent, immutable copy of all state for rendering."""
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
                "mode": self.mode,
                "device_name": self.device_name,
                "latency_ms": self.latency_ms,
                "timbre": self.timbre,
                "muted": self.muted,
                "running": self.running,
                "status_msg": self.status_msg,
            }
