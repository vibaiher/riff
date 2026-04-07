"""MIDI-to-audio synthesis via FluidSynth with guitar soundfont."""

from __future__ import annotations

import copy
import pathlib

import numpy as np
import pretty_midi

SAMPLE_RATE = 44100
SF2_PATH = str(pathlib.Path(__file__).parent.parent / "assets" / "clean_guitar_bank.sf2")


def render(midi: pretty_midi.PrettyMIDI, sf2_path: str = SF2_PATH) -> np.ndarray:
    try:
        import fluidsynth

        synth_midi = copy.deepcopy(midi)
        synth_midi.instruments = [
            inst for inst in synth_midi.instruments if not inst.is_drum
        ]
        for inst in synth_midi.instruments:
            inst.program = 0

        fs = fluidsynth.Synth(samplerate=float(SAMPLE_RATE))
        sfid = fs.sfload(sf2_path)
        try:
            audio = synth_midi.fluidsynth(fs=SAMPLE_RATE, synthesizer=fs, sfid=sfid)
        finally:
            fs.delete()
        return audio.astype(np.float32)
    except Exception:
        audio = midi.synthesize(fs=SAMPLE_RATE)
        return audio.astype(np.float32)
