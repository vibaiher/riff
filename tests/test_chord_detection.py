"""Tests for detecting chords from a set of note names."""

from riff.audio.chords import detect_chord


class TestDetectChord:
    def test_c_major_triad(self):
        result = detect_chord(["C", "E", "G"])

        assert result == "C"

    def test_a_minor_triad(self):
        result = detect_chord(["A", "C", "E"])

        assert result == "Am"

    def test_single_note_returns_root(self):
        result = detect_chord(["G"])

        assert result == "G"

    def test_empty_notes_returns_none(self):
        result = detect_chord([])

        assert result is None

    def test_dominant_7th(self):
        result = detect_chord(["G", "B", "D", "F"])

        assert result == "G7"

    def test_notes_in_any_order(self):
        result = detect_chord(["G", "C", "E"])

        assert result == "C"

    def test_duplicate_notes_ignored(self):
        result = detect_chord(["C", "E", "G", "C", "E"])

        assert result == "C"

    def test_unrecognized_returns_first_note(self):
        result = detect_chord(["C", "F#", "B"])

        assert result == "C"

    def test_superset_matches_best_chord(self):
        result = detect_chord(["G", "C", "E", "B"])

        assert result == "Cmaj7"

    def test_sus4_chord(self):
        result = detect_chord(["C", "F", "G"])

        assert result == "Csus4"

    def test_sus2_chord(self):
        result = detect_chord(["C", "D", "G"])

        assert result == "Csus2"

    def test_dim7_chord(self):
        result = detect_chord(["B", "D", "F", "G#"])

        assert result == "Bdim7"
