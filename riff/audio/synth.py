"""MIDI-to-audio synthesis via FluidSynth with guitar soundfont."""

from __future__ import annotations

import pathlib

import numpy as np
import pretty_midi

SAMPLE_RATE = 44100
SF2_PATH = str(pathlib.Path(__file__).parent.parent / "assets" / "clean_guitar_bank.sf2")


def render(midi: pretty_midi.PrettyMIDI, sf2_path: str = SF2_PATH) -> np.ndarray:
    try:
        import fluidsynth

        fs = fluidsynth.Synth(samplerate=float(SAMPLE_RATE))
        sfid = fs.sfload(sf2_path)
        try:
            audio = midi.fluidsynth(fs=SAMPLE_RATE, synthesizer=fs, sfid=sfid)
        finally:
            fs.delete()
        return audio.astype(np.float32)
    except Exception:
        audio = midi.synthesize(fs=SAMPLE_RATE)
        return audio.astype(np.float32)
