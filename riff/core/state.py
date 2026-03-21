"""Shared application state with thread-safe access.

AppState is the single source of truth for all panels and threads.
Every field is read/written through thread-safe helpers so no external
code needs to acquire a lock directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import List

# Timbres — affect synthesis parameters only, not note choice
TIMBRES = ["CLEAN", "WARM", "BRIGHT", "PAD", "RAW"]


@dataclass
class AppState:
    # ── YOU panel ─────────────────────────────────────────────────────────────
    frequency: float = 0.0          # detected fundamental frequency (Hz)
    note: str = "—"                 # e.g. "C#"
    octave: int = 4                 # e.g. 4  →  "C#4"
    bpm: float = 0.0                # estimated tempo
    db: float = -80.0               # signal level in dBFS
    waveform: List[float] = field(default_factory=list)   # amplitude per bin
    chords: List[str] = field(default_factory=list)       # suggested chords

    # ── RIFF IS PLAYING panel ─────────────────────────────────────────────────
    riff_note: str = "—"
    riff_octave: int = 4
    riff_waveform: List[float] = field(default_factory=list)
    riff_active: bool = False
    riff_next_note: str = "—"
    riff_model: str = "Markov"
    riff_db: float = -80.0          # synth output level (dBFS)
    riff_chords: List[str] = field(default_factory=list)  # chords RIFF is using
    riff_density: float = 0.0       # notes-per-second of user input (for display)
    riff_listening: bool = False    # True when RIFF deliberately stays silent
    markov_order: int = 4           # current max N-gram order
    markov_learned: int = 0         # total notes learned
    markov_phase: int = 1           # learning phase (1-4)
    markov_confidence: float = 0.0  # % exact matches (no fallback needed)

    # ── System ────────────────────────────────────────────────────────────────
    device_name: str = "Detecting..."
    device_index: int = -1
    latency_ms: float = 0.0
    timbre_index: int = 0           # default: CLEAN (TIMBRES index 0)
    muted: bool = False
    running: bool = True
    status_msg: str = ""            # transient flash message (footer)

    _lock: Lock = field(default_factory=Lock, compare=False, repr=False)

    # ── Properties ────────────────────────────────────────────────────────────

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

    def next_timbre(self) -> None:
        with self._lock:
            self.timbre_index = (self.timbre_index + 1) % len(TIMBRES)
            self.status_msg = f"Timbre → {TIMBRES[self.timbre_index % len(TIMBRES)]}"

    def toggle_mute(self) -> None:
        with self._lock:
            self.muted = not self.muted
            self.status_msg = "MUTED" if self.muted else "UNMUTED"

    def snapshot(self) -> dict:
        """Return a consistent, immutable copy of all state for rendering."""
        with self._lock:
            return {
                "frequency":      self.frequency,
                "note":           self.note,
                "octave":         self.octave,
                "bpm":            self.bpm,
                "db":             self.db,
                "waveform":       list(self.waveform),
                "chords":         list(self.chords),
                "riff_note":      self.riff_note,
                "riff_octave":    self.riff_octave,
                "riff_waveform":  list(self.riff_waveform),
                "riff_active":    self.riff_active,
                "riff_next_note": self.riff_next_note,
                "riff_model":     self.riff_model,
                "riff_db":        self.riff_db,
                "riff_chords":    list(self.riff_chords),
                "riff_density":   self.riff_density,
                "riff_listening": self.riff_listening,
                "markov_order":   self.markov_order,
                "markov_learned": self.markov_learned,
                "markov_phase":   self.markov_phase,
                "markov_confidence": self.markov_confidence,
                "device_name":    self.device_name,
                "latency_ms":     self.latency_ms,
                "timbre":         self.timbre,
                "muted":          self.muted,
                "running":        self.running,
                "status_msg":     self.status_msg,
            }
