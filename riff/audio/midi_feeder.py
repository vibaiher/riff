from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .chords import detect_chord
from .song import SongData

SAMPLE_RATE = 44100
WAVEFORM_WINDOW = SAMPLE_RATE // 3
WAVEFORM_POINTS = 48


@dataclass
class TimedChord:
    chord: str
    start: float
    duration: float


def extract_timed_chords(song: SongData, resolution: float = 0.5) -> list[TimedChord]:
    if not song.notes:
        return []
    result: list[TimedChord] = []
    t = 0.0
    while t < song.total_duration:
        notes_at = song.notes_at(t)
        if notes_at:
            names = [n.note for n in notes_at]
            chord = detect_chord(names)
            if chord:
                if result and result[-1].chord == chord:
                    result[-1].duration = t + resolution - result[-1].start
                else:
                    result.append(TimedChord(chord=chord, start=t, duration=resolution))
        t += resolution
    return result


class MidiFeeder:
    def __init__(self, state, song: SongData, audio: np.ndarray | None = None) -> None:
        self._state = state
        self._song = song
        self._audio = audio

    def is_finished(self, position: float) -> bool:
        return position >= self._song.total_duration

    def tick(self, position: float) -> None:
        current_notes = self._song.notes_at(position)
        waveform, db = self._read_audio_chunk(position)

        if current_notes:
            first = current_notes[0]
            note_names = [n.note for n in current_notes]
            chord = detect_chord(note_names)
            self._state.update(
                note=first.note,
                octave=first.octave,
                bpm=self._song.bpm,
                waveform=waveform,
                db=db,
            )
            if chord and self._state.snapshot().get("mode") == "COMPOSE":
                self._state.add_chord(chord)
        else:
            self._state.update(note="—", waveform=waveform, db=db)

    def _read_audio_chunk(self, position: float) -> tuple[list[float], float]:
        if self._audio is None or len(self._audio) == 0:
            return [0.0] * WAVEFORM_POINTS, -80.0
        center = int(position * SAMPLE_RATE)
        start = max(0, center - WAVEFORM_WINDOW // 2)
        end = min(len(self._audio), start + WAVEFORM_WINDOW)
        chunk = self._audio[start:end]
        if len(chunk) == 0:
            return [0.0] * WAVEFORM_POINTS, -80.0
        rms = float(np.sqrt(np.mean(chunk**2)))
        db = float(20.0 * np.log10(max(rms, 1e-10)))
        abs_chunk = np.abs(chunk)
        segments = np.array_split(abs_chunk, WAVEFORM_POINTS)
        wf = [float(np.max(s)) if len(s) else 0.0 for s in segments]
        return wf, db
