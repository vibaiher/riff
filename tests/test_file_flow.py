"""Integration test: load MIDI → feed YOU → auto-generate."""

import os
import time

from riff.audio.midi_feeder import MidiFeeder
from riff.audio.song import SongData, SongNote
from riff.core.state import AppState
from riff.ui.display import KeyboardHandler


def _short_song() -> SongData:
    """A tiny C major chord lasting 0.1s — fast for testing."""
    return SongData(
        notes=[
            SongNote(note="C", octave=4, start=0.0, duration=0.1),
            SongNote(note="E", octave=4, start=0.0, duration=0.1),
            SongNote(note="G", octave=4, start=0.0, duration=0.1),
        ],
        bpm=120.0,
    )


class TestFileLoadFlow:
    def test_feeder_populates_you_panel_and_chords(self):
        state = AppState(mode_index=1)
        song = _short_song()
        feeder = MidiFeeder(state, song)

        feeder.tick(position=0.05)

        snap = state.snapshot()
        assert snap["note"] == "C"
        assert snap["octave"] == 4
        assert snap["bpm"] == 120.0
        assert "C" in snap["captured_chords"]

    def test_feeder_reports_finished_after_song_ends(self):
        song = _short_song()
        state = AppState(mode_index=1)
        feeder = MidiFeeder(state, song)

        assert not feeder.is_finished(0.05)
        assert feeder.is_finished(0.2)

    def test_multiple_chords_accumulated_across_ticks(self):
        state = AppState(mode_index=1)
        song = SongData(
            notes=[
                SongNote(note="C", octave=4, start=0.0, duration=0.5),
                SongNote(note="E", octave=4, start=0.0, duration=0.5),
                SongNote(note="G", octave=4, start=0.0, duration=0.5),
                SongNote(note="A", octave=4, start=1.0, duration=0.5),
                SongNote(note="C", octave=5, start=1.0, duration=0.5),
                SongNote(note="E", octave=5, start=1.0, duration=0.5),
            ],
            bpm=120.0,
        )
        feeder = MidiFeeder(state, song)

        feeder.tick(position=0.2)
        feeder.tick(position=1.2)

        chords = state.snapshot()["captured_chords"]
        assert "C" in chords
        assert "Am" in chords

    def test_confirm_file_not_found_shows_error_and_resets_phase(self):
        state = AppState(mode_index=1)
        state.update(compose_phase="loaded")
        kb = KeyboardHandler(state)

        kb._confirm_file_input_path("/nonexistent/path/song.mid")

        snap = state.snapshot()
        assert "not found" in snap["status_msg"].lower()
        assert snap["compose_phase"] == ""

    def test_confirm_file_load_error_resets_phase(self, tmp_path):
        bad_file = tmp_path / "corrupt.mid"
        bad_file.write_text("not a real midi")
        state = AppState(mode_index=1)
        state.update(compose_phase="loaded")
        kb = KeyboardHandler(state)

        kb._confirm_file_input_path(str(bad_file))

        snap = state.snapshot()
        assert "error" in snap["status_msg"].lower()
        assert snap["compose_phase"] == ""

    def test_load_midi_auto_listens(self):
        state = AppState(mode_index=1)
        kb = KeyboardHandler(state)
        midi_path = os.path.join(
            os.path.dirname(__file__), "..", "riff", "assets", "zombie.mid"
        )

        kb._confirm_file_input_path(midi_path)

        snap = state.snapshot()
        assert snap["compose_phase"] == "listening"
        state.update(running=False)
        time.sleep(0.15)
