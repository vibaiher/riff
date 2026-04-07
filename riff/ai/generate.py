"""High-level generate function: progression string → SongData ready to play."""

from __future__ import annotations

import pretty_midi

from riff.ai.engine import get_engine
from riff.audio.chords import CHROMATIC, _ENHARMONIC, parse_progression
from riff.audio.song import SongData, SongNote


def _notes_to_midi(notes: list[SongNote], bpm: float) -> pretty_midi.PrettyMIDI:
    """Convert SongNotes to a PrettyMIDI object for synthesis."""
    midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    instrument = pretty_midi.Instrument(program=0)  # Acoustic Grand Piano

    for n in notes:
        canonical = _ENHARMONIC.get(n.note, n.note)
        pitch = CHROMATIC.index(canonical) + 12 * (n.octave + 1)
        midi_note = pretty_midi.Note(
            velocity=90,
            pitch=pitch,
            start=n.start,
            end=n.start + n.duration,
        )
        instrument.notes.append(midi_note)

    midi.instruments.append(instrument)
    return midi


def calculate_bars(target_duration: float, n_chords: int, bpm: int) -> int:
    beat_dur = 60.0 / bpm
    total_beats = target_duration / beat_dur
    bars = round(total_beats / n_chords)
    return max(1, bars)


def select_progression(chords: list[str]) -> list[str]:
    if not chords:
        raise ValueError("No chords to build progression")
    seen: dict[str, None] = {}
    for c in chords:
        if c not in seen:
            seen[c] = None
    return list(seen.keys())


def generate_song(
    progression: str,
    bars: int = 4,
    bpm: int = 120,
    engine: str = "phrase",
) -> SongData:
    """Parse a chord progression, generate a melody, return a playable SongData."""
    chords = parse_progression(progression)
    eng = get_engine(engine)
    notes = eng.generate(chords, bars=bars, bpm=bpm)
    midi = _notes_to_midi(notes, bpm)
    return SongData(notes=notes, bpm=bpm, _midi=midi)
