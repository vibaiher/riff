"""MIDI-to-audio synthesis.

External MIDIs (loaded files) use pretty_midi's default synthesizer.
RIFF-generated melodies use FluidSynth with the Gibson LP guitar soundfont.
"""

from __future__ import annotations

import pathlib

import numpy as np
import pretty_midi

SAMPLE_RATE = 44100
SF2_GUITAR = str(pathlib.Path(__file__).parent.parent / "assets" / "clean_guitar_bank.sf2")


def render_default(midi: pretty_midi.PrettyMIDI) -> np.ndarray:
    audio = midi.synthesize(fs=SAMPLE_RATE)
    return audio.astype(np.float32)


def render_guitar(midi: pretty_midi.PrettyMIDI) -> np.ndarray:
    try:
        import fluidsynth

        for inst in midi.instruments:
            inst.program = 0
        fs = fluidsynth.Synth(samplerate=float(SAMPLE_RATE))
        sfid = fs.sfload(SF2_GUITAR)
        try:
            audio = midi.fluidsynth(fs=SAMPLE_RATE, synthesizer=fs, sfid=sfid)
        finally:
            fs.delete()
        return audio.astype(np.float32)
    except Exception:
        return render_default(midi)
