from __future__ import annotations

import bisect
import os
from dataclasses import dataclass, field

import numpy as np
import pretty_midi

SUPPORTED_EXTENSIONS = {".mid", ".midi"}
SAMPLE_RATE = 44100
WAVEFORM_POINTS = 48

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


@dataclass
class SongNote:
    note: str
    octave: int
    start: float
    duration: float


@dataclass
class SongData:
    notes: list[SongNote] = field(default_factory=list)
    bpm: float = 120.0
    _midi: pretty_midi.PrettyMIDI | None = field(default=None, repr=False, compare=False)
    _starts: list[float] = field(default_factory=list, init=False, repr=False, compare=False)

    def _ensure_index(self) -> list[float]:
        if not self._starts and self.notes:
            self._starts = [n.start for n in self.notes]
        return self._starts

    @property
    def total_duration(self) -> float:
        if not self.notes:
            return 0.0
        return max(n.start + n.duration for n in self.notes)

    def note_at_or_before(self, time: float) -> SongNote | None:
        starts = self._ensure_index()
        if not starts:
            return None
        idx = bisect.bisect_right(starts, time) - 1
        return self.notes[idx] if idx >= 0 else None

    def notes_between(self, start: float, end: float) -> list[SongNote]:
        starts = self._ensure_index()
        if not starts:
            return []
        lo = bisect.bisect_left(starts, start)
        hi = bisect.bisect_left(starts, end)
        return self.notes[lo:hi]

    def notes_at(self, time: float) -> list[SongNote]:
        starts = self._ensure_index()
        if not starts:
            return []
        hi = bisect.bisect_right(starts, time)
        result = []
        for i in range(hi):
            n = self.notes[i]
            if n.start <= time < n.start + n.duration:
                result.append(n)
        return result

    def render_audio(self) -> np.ndarray:
        if self._midi is None or not self.notes:
            return np.array([], dtype=np.float32)
        from riff.audio.synth import render

        return render(self._midi)

    @classmethod
    def from_file(cls, path: str) -> SongData:
        ext = os.path.splitext(path)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file format: {ext}")
        midi = pretty_midi.PrettyMIDI(path)
        tempos = midi.get_tempo_changes()[1]
        bpm = float(tempos[0]) if len(tempos) > 0 else 120.0
        notes: list[SongNote] = []
        for instrument in midi.instruments:
            if instrument.is_drum:
                continue
            for note in instrument.notes:
                name = NOTE_NAMES[note.pitch % 12]
                octave = (note.pitch // 12) - 1
                notes.append(
                    SongNote(
                        note=name,
                        octave=octave,
                        start=note.start,
                        duration=note.end - note.start,
                    )
                )
        notes.sort(key=lambda n: n.start)
        return cls(notes=notes, bpm=bpm, _midi=midi)


class SongPlayer:
    def __init__(self, audio: np.ndarray) -> None:
        self.audio = audio
        self._playing = False
        self._speed = 1.0

    def start(self, offset: float = 0.0) -> None:
        self._play_from(offset)

    def pause(self) -> None:
        if self._playing:
            import sounddevice as sd

            sd.stop()
            self._playing = False

    def resume(self, position: float) -> None:
        if not self._playing:
            self._play_from(position)

    def set_speed(self, speed: float, position: float) -> None:
        was_playing = self._playing
        if was_playing:
            self.pause()
        self._speed = speed
        if was_playing:
            self._play_from(position)

    def stop(self) -> None:
        if self._playing:
            import sounddevice as sd

            sd.stop()
            self._playing = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.stop()

    def _play_from(self, position: float) -> None:
        sample_offset = int(position * SAMPLE_RATE)
        if len(self.audio) == 0 or sample_offset >= len(self.audio):
            return
        import sounddevice as sd

        remaining = self.audio[sample_offset:]
        sd.play(remaining, samplerate=int(SAMPLE_RATE * self._speed))
        self._playing = True
