"""Tests for chord accumulation and generation state in AppState."""

from riff.core.state import AppState


class TestChordAccumulation:
    def test_add_chord(self):
        state = AppState()
        state.add_chord("Am")
        snap = state.snapshot()
        assert snap["captured_chords"] == ["Am"]

    def test_add_multiple_chords(self):
        state = AppState()
        state.add_chord("Am")
        state.add_chord("F")
        state.add_chord("C")
        assert state.snapshot()["captured_chords"] == ["Am", "F", "C"]

    def test_no_consecutive_duplicates(self):
        state = AppState()
        state.add_chord("Am")
        state.add_chord("Am")
        state.add_chord("Am")
        assert state.snapshot()["captured_chords"] == ["Am"]

    def test_non_consecutive_duplicates_allowed(self):
        state = AppState()
        state.add_chord("Am")
        state.add_chord("F")
        state.add_chord("Am")
        assert state.snapshot()["captured_chords"] == ["Am", "F", "Am"]

    def test_clear_chords(self):
        state = AppState()
        state.add_chord("Am")
        state.add_chord("F")
        state.clear_chords()
        snap = state.snapshot()
        assert snap["captured_chords"] == []
        assert snap["gen_status"] == ""

    def test_gen_status_in_snapshot(self):
        state = AppState()
        state.update(gen_status="playing")
        assert state.snapshot()["gen_status"] == "playing"

    def test_attached_file_in_snapshot(self):
        state = AppState()
        state.update(attached_file="/tmp/song.mid")
        assert state.snapshot()["attached_file"] == "/tmp/song.mid"
