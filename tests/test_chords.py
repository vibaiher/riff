"""Tests for chord parsing and note resolution."""

from riff.audio.chords import Chord, parse_progression


class TestChord:
    def test_major_chord_notes(self):
        c = Chord("C", "major")
        assert c.root == "C"
        assert c.quality == "major"
        assert c.notes == ["C", "E", "G"]

    def test_minor_chord_notes(self):
        am = Chord("A", "minor")
        assert am.notes == ["A", "C", "E"]

    def test_dominant7_chord_notes(self):
        g7 = Chord("G", "7")
        assert g7.notes == ["G", "B", "D", "F"]

    def test_minor7_chord_notes(self):
        am7 = Chord("A", "m7")
        assert am7.notes == ["A", "C", "E", "G"]

    def test_major7_chord_notes(self):
        cmaj7 = Chord("C", "maj7")
        assert cmaj7.notes == ["C", "E", "G", "B"]

    def test_sharp_root(self):
        fs = Chord("F#", "minor")
        assert fs.root == "F#"
        assert fs.notes == ["F#", "A", "C#"]

    def test_flat_root(self):
        bb = Chord("Bb", "major")
        assert bb.root == "Bb"
        assert bb.notes == ["Bb", "D", "F"]

    def test_scale_notes_major(self):
        c = Chord("C", "major")
        assert c.scale_notes == ["C", "D", "E", "F", "G", "A", "B"]

    def test_scale_notes_minor(self):
        am = Chord("A", "minor")
        assert am.scale_notes == ["A", "B", "C", "D", "E", "F", "G"]


class TestParseProgression:
    def test_simple_major_chords(self):
        chords = parse_progression("C | F | G | C")
        assert len(chords) == 4
        assert chords[0].root == "C"
        assert chords[0].quality == "major"
        assert chords[1].root == "F"
        assert chords[2].root == "G"

    def test_minor_chords(self):
        chords = parse_progression("Am | Dm | Em")
        assert chords[0].quality == "minor"
        assert chords[0].root == "A"
        assert chords[1].root == "D"

    def test_seventh_chords(self):
        chords = parse_progression("G7 | Cmaj7 | Am7")
        assert chords[0].quality == "7"
        assert chords[1].quality == "maj7"
        assert chords[2].quality == "m7"

    def test_sharp_and_flat_roots(self):
        chords = parse_progression("F#m | Bb | C#7")
        assert chords[0].root == "F#"
        assert chords[0].quality == "minor"
        assert chords[1].root == "Bb"
        assert chords[2].root == "C#"
        assert chords[2].quality == "7"

    def test_whitespace_tolerance(self):
        chords = parse_progression("  Am  |  F  |  C  |  G  ")
        assert len(chords) == 4
        assert chords[0].root == "A"

    def test_empty_raises(self):
        import pytest

        with pytest.raises(ValueError):
            parse_progression("")

    def test_single_chord(self):
        chords = parse_progression("Am")
        assert len(chords) == 1
        assert chords[0].root == "A"
        assert chords[0].quality == "minor"

    def test_sus4_and_sus2(self):
        chords = parse_progression("Csus4 | Dsus2")
        assert chords[0].quality == "sus4"
        assert chords[0].notes == ["C", "F", "G"]
        assert chords[1].quality == "sus2"
        assert chords[1].notes == ["D", "E", "A"]

    def test_dim7(self):
        chords = parse_progression("Bdim7")
        assert chords[0].quality == "dim7"
        assert chords[0].notes == ["B", "D", "F", "G#"]
