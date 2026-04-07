"""Chord parsing and note resolution for melody generation."""

from __future__ import annotations

import re
from dataclasses import dataclass

CHROMATIC = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Enharmonic mapping for flats → sharps (internal representation)
_ENHARMONIC = {
    "Db": "C#", "Eb": "D#", "Fb": "E", "Gb": "F#",
    "Ab": "G#", "Bb": "A#", "Cb": "B",
}

# Intervals as semitones from root
_QUALITY_INTERVALS: dict[str, list[int]] = {
    "major": [0, 4, 7],
    "minor": [0, 3, 7],
    "7":     [0, 4, 7, 10],
    "m7":    [0, 3, 7, 10],
    "maj7":  [0, 4, 7, 11],
    "dim":   [0, 3, 6],
    "dim7":  [0, 3, 6, 9],
    "aug":   [0, 4, 8],
    "sus4":  [0, 5, 7],
    "sus2":  [0, 2, 7],
}

# Scale intervals (semitones from root)
_SCALE_INTERVALS: dict[str, list[int]] = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
}

# Regex: root (letter + optional # or b) + quality suffix
_CHORD_RE = re.compile(r"^([A-G][#b]?)(m7|maj7|dim7|7|m|dim|aug|sus4|sus2)?$")

_SUFFIX_MAP = {
    None: "major",
    "m": "minor",
    "7": "7",
    "m7": "m7",
    "maj7": "maj7",
    "dim": "dim",
    "dim7": "dim7",
    "aug": "aug",
    "sus4": "sus4",
    "sus2": "sus2",
}


def _root_index(root: str) -> int:
    canonical = _ENHARMONIC.get(root, root)
    return CHROMATIC.index(canonical)


def _note_at(root: str, semitones: int) -> str:
    idx = (_root_index(root) + semitones) % 12
    note = CHROMATIC[idx]
    # Preserve flat notation if root uses flats
    if "b" in root:
        inv_enharmonic = {v: k for k, v in _ENHARMONIC.items()}
        note = inv_enharmonic.get(note, note)
    return note


@dataclass
class Chord:
    root: str
    quality: str

    @property
    def notes(self) -> list[str]:
        intervals = _QUALITY_INTERVALS[self.quality]
        return [_note_at(self.root, i) for i in intervals]

    @property
    def scale_notes(self) -> list[str]:
        base = "minor" if self.quality in ("minor", "m7") else "major"
        intervals = _SCALE_INTERVALS[base]
        return [_note_at(self.root, i) for i in intervals]


_QUALITY_SUFFIX = {
    "major": "", "minor": "m", "7": "7", "m7": "m7", "maj7": "maj7",
    "dim": "dim", "dim7": "dim7", "aug": "aug", "sus4": "sus4", "sus2": "sus2",
}


def detect_chord(notes: list[str]) -> str | None:
    if not notes:
        return None
    unique = list(dict.fromkeys(notes))
    if len(unique) == 1:
        return unique[0]
    note_set = {_ENHARMONIC.get(n, n) for n in unique}
    input_roots = [_ENHARMONIC.get(n, n) for n in unique]
    best = None
    best_size = 0
    for root in input_roots:
        for quality_name, intervals in _QUALITY_INTERVALS.items():
            chord_notes = {CHROMATIC[(_root_index(root) + i) % 12] for i in intervals}
            if chord_notes <= note_set and len(intervals) > best_size:
                best = root + _QUALITY_SUFFIX[quality_name]
                best_size = len(intervals)
    if best is not None:
        return best
    for root in CHROMATIC:
        for quality_name, intervals in _QUALITY_INTERVALS.items():
            chord_notes = {CHROMATIC[(_root_index(root) + i) % 12] for i in intervals}
            if chord_notes <= note_set and len(intervals) > best_size:
                best = root + _QUALITY_SUFFIX[quality_name]
                best_size = len(intervals)
    return best or unique[0]


def parse_progression(text: str) -> list[Chord]:
    text = text.strip()
    if not text:
        raise ValueError("Empty progression")

    tokens = [t.strip() for t in text.split("|")]
    tokens = [t for t in tokens if t]

    chords = []
    for token in tokens:
        m = _CHORD_RE.match(token)
        if not m:
            raise ValueError(f"Cannot parse chord: {token!r}")
        root, suffix = m.group(1), m.group(2)
        quality = _SUFFIX_MAP[suffix]
        chords.append(Chord(root=root, quality=quality))

    return chords
