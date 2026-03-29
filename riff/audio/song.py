from __future__ import annotations

import os
import time as _time
from collections.abc import Callable
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

    @property
    def total_duration(self) -> float:
        if not self.notes:
            return 0.0
        return max(n.start + n.duration for n in self.notes)

    def note_at_or_before(self, time: float) -> SongNote | None:
        result = None
        for n in self.notes:
            if n.start <= time:
                result = n
            else:
                break
        return result

    def notes_between(self, start: float, end: float) -> list[SongNote]:
        return [n for n in self.notes if start <= n.start < end]

    def notes_at(self, time: float) -> list[SongNote]:
        return [n for n in self.notes if n.start <= time < n.start + n.duration]

    def render_audio(self) -> np.ndarray:
        if self._midi is None or not self.notes:
            return np.array([], dtype=np.float32)
        audio = self._midi.synthesize(fs=SAMPLE_RATE)
        return audio.astype(np.float32)

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


class SongTracker:
    def __init__(self, song: SongData, clock: Callable[[], float] = _time.time) -> None:
        self._song = song
        self._clock = clock
        self._start_time: float | None = None
        self._paused = False
        self._paused_position: float = 0.0
        self._speed: float = 1.0

    @property
    def position(self) -> float:
        if self._paused:
            return self._paused_position
        if self._start_time is None:
            return 0.0
        return (self._clock() - self._start_time) * self._speed

    def set_speed(self, speed: float) -> None:
        current_pos = self.position
        self._speed = speed
        if self._start_time is not None and not self._paused:
            self._start_time = self._clock() - current_pos / self._speed

    @property
    def speed(self) -> float:
        return self._speed

    @property
    def is_paused(self) -> bool:
        return self._paused

    def pause(self) -> None:
        if not self._paused:
            self._paused_position = self.position
            self._paused = True

    def resume(self) -> None:
        if self._paused:
            self._start_time = self._clock() - self._paused_position / self._speed
            self._paused = False

    @property
    def is_finished(self) -> bool:
        return self.position >= self._song.total_duration

    def upcoming_notes(self, count: int) -> list[SongNote]:
        pos = self.position
        return [n for n in self._song.notes if n.start > pos][:count]

    @property
    def current_notes(self) -> list[SongNote]:
        return self._song.notes_at(self.position)

    @property
    def song(self) -> SongData:
        return self._song

    def start(self) -> None:
        self._start_time = self._clock()


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

    def _play_from(self, position: float) -> None:
        sample_offset = int(position * SAMPLE_RATE)
        if len(self.audio) == 0 or sample_offset >= len(self.audio):
            return
        import sounddevice as sd

        remaining = self.audio[sample_offset:]
        sd.play(remaining, samplerate=int(SAMPLE_RATE * self._speed))
        self._playing = True


WAVEFORM_WINDOW = SAMPLE_RATE // 3


class SongUpdater:
    def __init__(self, state, tracker: SongTracker, audio: np.ndarray | None = None) -> None:
        self._state = state
        self._tracker = tracker
        self._audio = audio

    def tick(self) -> None:
        current = self._tracker.current_notes
        upcoming = self._tracker.upcoming_notes(4)
        first = current[0] if current else None
        waveform, db = self._read_audio_chunk()
        self._state.update(
            song_note=first.note if first else "—",
            song_octave=first.octave if first else 4,
            song_position=self._tracker.position,
            song_bpm=self._tracker.song.bpm,
            song_upcoming=[f"{n.note}{n.octave}" for n in upcoming],
            song_waveform=waveform,
            song_db=db,
            song_finished=self._tracker.is_finished,
        )

    def _read_audio_chunk(self) -> tuple[list[float], float]:
        if self._audio is None or len(self._audio) == 0:
            return [0.0] * WAVEFORM_POINTS, -80.0
        pos = self._tracker.position
        center = int(pos * SAMPLE_RATE)
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
