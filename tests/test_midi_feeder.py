"""Tests for MidiFeeder — feeds loaded MIDI into YOU panel + chord accumulation."""

from riff.audio.song import SongData, SongNote
from riff.audio.midi_feeder import MidiFeeder
from riff.core.state import AppState


def _simple_song() -> SongData:
    return SongData(
        notes=[
            SongNote(note="C", octave=4, start=0.0, duration=1.0),
            SongNote(note="E", octave=4, start=0.0, duration=1.0),
            SongNote(note="G", octave=4, start=0.0, duration=1.0),
            SongNote(note="A", octave=4, start=1.5, duration=1.0),
            SongNote(note="C", octave=5, start=1.5, duration=1.0),
            SongNote(note="E", octave=5, start=1.5, duration=1.0),
        ],
        bpm=120.0,
    )


class TestMidiFeeder:
    def test_tick_updates_you_panel_note(self):
        state = AppState(mode_index=1)
        song = _simple_song()
        feeder = MidiFeeder(state, song)

        feeder.tick(position=0.5)

        snap = state.snapshot()
        assert snap["note"] == "C"
        assert snap["octave"] == 4

    def test_tick_with_no_notes_clears_display(self):
        state = AppState(mode_index=1)
        song = _simple_song()
        feeder = MidiFeeder(state, song)

        feeder.tick(position=1.2)

        snap = state.snapshot()
        assert snap["note"] == "—"

    def test_tick_accumulates_chords_in_compose_mode(self):
        state = AppState(mode_index=1)
        song = _simple_song()
        feeder = MidiFeeder(state, song)

        feeder.tick(position=0.5)

        snap = state.snapshot()
        assert "C" in snap["captured_chords"]

    def test_tick_detects_chord_from_simultaneous_notes(self):
        state = AppState(mode_index=1)
        song = _simple_song()
        feeder = MidiFeeder(state, song)

        feeder.tick(position=1.5)

        snap = state.snapshot()
        assert "Am" in snap["captured_chords"]

    def test_tick_updates_bpm(self):
        state = AppState(mode_index=1)
        song = _simple_song()
        feeder = MidiFeeder(state, song)

        feeder.tick(position=0.5)

        assert state.snapshot()["bpm"] == 120.0

    def test_is_finished_when_past_duration(self):
        state = AppState(mode_index=1)
        song = _simple_song()
        feeder = MidiFeeder(state, song)

        assert not feeder.is_finished(1.0)
        assert feeder.is_finished(3.0)

    def test_tick_updates_waveform_from_audio(self):
        import numpy as np
        state = AppState(mode_index=1)
        song = _simple_song()
        audio = np.sin(2 * np.pi * 440 * np.arange(44100 * 3) / 44100).astype(np.float32)
        feeder = MidiFeeder(state, song, audio=audio)

        feeder.tick(position=0.5)

        snap = state.snapshot()
        assert len(snap["waveform"]) > 0
        assert any(v > 0 for v in snap["waveform"])

    def test_tick_updates_db_from_audio(self):
        import numpy as np
        state = AppState(mode_index=1)
        song = _simple_song()
        audio = np.sin(2 * np.pi * 440 * np.arange(44100 * 3) / 44100).astype(np.float32)
        feeder = MidiFeeder(state, song, audio=audio)

        feeder.tick(position=0.5)

        snap = state.snapshot()
        assert snap["db"] > -80.0

    def test_tick_without_audio_sets_silence(self):
        state = AppState(mode_index=1)
        song = _simple_song()
        feeder = MidiFeeder(state, song)

        feeder.tick(position=0.5)

        snap = state.snapshot()
        assert snap["db"] == -80.0

    def test_tick_does_not_accumulate_outside_compose(self):
        state = AppState(mode_index=0)
        song = _simple_song()
        feeder = MidiFeeder(state, song)

        feeder.tick(position=0.5)

        assert state.snapshot()["captured_chords"] == []
