"""FluidSynth guitar player for RIFF-generated melodies."""

from __future__ import annotations

import pathlib
import time

from riff.audio.chords import _ENHARMONIC, CHROMATIC

SAMPLE_RATE = 44100
SF2_GUITAR = str(pathlib.Path(__file__).parent.parent / "assets" / "clean_guitar_bank.sf2")


def _note_to_pitch(note: str, octave: int) -> int:
    canonical = _ENHARMONIC.get(note, note)
    return CHROMATIC.index(canonical) + 12 * (octave + 1)


class RiffPlayer:
    def __init__(self, notes, total_duration: float) -> None:
        self._notes = notes
        self._total_duration = total_duration
        self._fs = None
        self._playing = False

    def start(self) -> None:
        import fluidsynth

        self._fs = fluidsynth.Synth()
        self._fs.start(driver="coreaudio")
        sfid = self._fs.sfload(SF2_GUITAR)
        self._fs.program_select(0, sfid, 0, 0)
        self._playing = True

        start = time.time()
        for n in self._notes:
            if not self._playing:
                break
            wait = n.start - (time.time() - start)
            if wait > 0:
                time.sleep(wait)
            pitch = _note_to_pitch(n.note, n.octave)
            self._fs.noteon(0, pitch, 90)
            time.sleep(n.duration)
            self._fs.noteoff(0, pitch)

        if self._playing:
            remaining = self._total_duration - (time.time() - start)
            if remaining > 0:
                time.sleep(remaining)

    def stop(self) -> None:
        self._playing = False
        if self._fs is not None:
            self._fs.delete()
            self._fs = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.stop()
