"""Tests for timed chord extraction and synchronized generation."""

from riff.audio.chords import detect_chord
from riff.audio.midi_feeder import extract_timed_chords, TimedChord
from riff.audio.song import SongData, SongNote


class TestExtractTimedChords:
    def test_extracts_chords_with_timing(self):
        song = SongData(notes=[
            SongNote(note="C", octave=4, start=0.0, duration=2.0),
            SongNote(note="E", octave=4, start=0.0, duration=2.0),
            SongNote(note="G", octave=4, start=0.0, duration=2.0),
            SongNote(note="A", octave=4, start=2.0, duration=2.0),
            SongNote(note="C", octave=5, start=2.0, duration=2.0),
            SongNote(note="E", octave=5, start=2.0, duration=2.0),
        ], bpm=120.0)

        result = extract_timed_chords(song)

        assert len(result) == 2
        assert result[0].chord == "C"
        assert result[0].start == 0.0
        assert result[0].duration == 2.0
        assert result[1].chord == "Am"
        assert result[1].start == 2.0

    def test_consecutive_same_chords_merged(self):
        song = SongData(notes=[
            SongNote(note="C", octave=4, start=0.0, duration=4.0),
            SongNote(note="E", octave=4, start=0.0, duration=4.0),
            SongNote(note="G", octave=4, start=0.0, duration=4.0),
        ], bpm=120.0)

        result = extract_timed_chords(song)

        assert len(result) == 1
        assert result[0].chord == "C"
        assert result[0].duration == 4.0

    def test_real_midi_produces_reasonable_chords(self):
        import os
        path = os.path.expanduser("~/Documents/riff/Linkin Park - Numb.mid")
        if not os.path.isfile(path):
            import pytest
            pytest.skip("Test MIDI not available")
        song = SongData.from_file(path)

        result = extract_timed_chords(song)

        assert len(result) > 20
        total_covered = sum(tc.duration for tc in result)
        assert total_covered > song.total_duration * 0.5

    def test_empty_song_returns_empty(self):
        song = SongData(notes=[], bpm=120.0)

        result = extract_timed_chords(song)

        assert result == []


class TestGenerateTimed:
    def test_notes_aligned_with_chord_boundaries(self):
        import random
        from riff.ai.phrase import PhraseEngine
        from riff.audio.chords import parse_progression

        random.seed(42)
        engine = PhraseEngine()
        timed = [
            TimedChord(chord="C", start=0.0, duration=2.0),
            TimedChord(chord="Am", start=2.0, duration=2.0),
            TimedChord(chord="F", start=4.0, duration=2.0),
        ]

        notes = engine.generate_timed(timed, bpm=120)

        assert len(notes) > 0
        for n in notes:
            assert n.start >= 0.0
            assert n.start < 6.01

    def test_chord_changes_happen_at_source_times(self):
        import random
        from riff.ai.phrase import PhraseEngine

        random.seed(42)
        engine = PhraseEngine()
        timed = [
            TimedChord(chord="C", start=0.0, duration=2.0),
            TimedChord(chord="Am", start=2.0, duration=3.0),
        ]

        notes = engine.generate_timed(timed, bpm=120)

        notes_first_half = [n for n in notes if n.start < 2.0]
        notes_second_half = [n for n in notes if n.start >= 2.0]
        assert len(notes_first_half) > 0
        assert len(notes_second_half) > 0

    def test_total_duration_matches_source(self):
        import random
        from riff.ai.phrase import PhraseEngine

        random.seed(42)
        engine = PhraseEngine()
        timed = [
            TimedChord(chord="E", start=0.0, duration=4.0),
            TimedChord(chord="A", start=4.0, duration=4.0),
        ]

        notes = engine.generate_timed(timed, bpm=110)

        total = max(n.start + n.duration for n in notes)
        assert total <= 8.01

    def test_single_timed_chord(self):
        import random
        from riff.ai.phrase import PhraseEngine

        random.seed(42)
        engine = PhraseEngine()
        timed = [TimedChord(chord="G", start=0.0, duration=3.0)]

        notes = engine.generate_timed(timed, bpm=120)

        assert len(notes) > 0
