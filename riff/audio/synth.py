"""MIDI-to-audio synthesis.

External MIDIs (loaded files) use pretty_midi's default synthesizer.
RIFF-generated melodies play through FluidSynth with Gibson LP guitar soundfont.
"""

from __future__ import annotations

import pathlib
import time

SAMPLE_RATE = 44100
SF2_GUITAR = str(pathlib.Path(__file__).parent.parent / "assets" / "clean_guitar_bank.sf2")

CHROMATIC = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_ENHARMONIC = {
    "Db": "C#",
    "Eb": "D#",
    "Fb": "E",
    "Gb": "F#",
    "Ab": "G#",
    "Bb": "A#",
    "Cb": "B",
}


def _note_to_pitch(note: str, octave: int) -> int:
    canonical = _ENHARMONIC.get(note, note)
    return CHROMATIC.index(canonical) + 12 * (octave + 1)


def play_guitar(notes, total_duration: float) -> None:
    try:
        import fluidsynth

        fs = fluidsynth.Synth()
        fs.start(driver="coreaudio")
        sfid = fs.sfload(SF2_GUITAR)
        fs.program_select(0, sfid, 0, 0)

        start = time.time()
        for n in notes:
            wait = n.start - (time.time() - start)
            if wait > 0:
                time.sleep(wait)
            pitch = _note_to_pitch(n.note, n.octave)
            fs.noteon(0, pitch, 90)
            time.sleep(n.duration)
            fs.noteoff(0, pitch)

        remaining = total_duration - (time.time() - start)
        if remaining > 0:
            time.sleep(remaining)

        fs.delete()
    except Exception:
        pass
