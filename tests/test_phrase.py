"""Tests for the phrase-based melody engine."""

import random

import pytest

from riff.ai.phrase import PhraseEngine
from riff.audio.chords import Chord, parse_progression
from riff.audio.song import SongNote


@pytest.fixture(autouse=True)
def _isolate_random():
    state = random.getstate()
    yield
    random.setstate(state)


class TestPhraseEngine:
    def setup_method(self):
        self.engine = PhraseEngine()
        self.chords = parse_progression("Am | F | C | G")

    def test_returns_song_notes(self):
        notes = self.engine.generate(self.chords, bars=4, bpm=120)

        assert len(notes) > 0
        assert all(isinstance(n, SongNote) for n in notes)

    def test_notes_sorted_by_start(self):
        notes = self.engine.generate(self.chords, bars=4, bpm=120)

        starts = [n.start for n in notes]
        assert starts == sorted(starts)

    def test_notes_within_time_bounds(self):
        bpm = 120
        bars = 4
        total_beats = bars * len(self.chords)
        total_duration = total_beats * (60.0 / bpm)

        notes = self.engine.generate(self.chords, bars=bars, bpm=bpm)

        for n in notes:
            assert n.start >= 0.0
            assert n.start < total_duration + 0.01

    def test_all_notes_valid_names(self):
        valid = {
            "C",
            "C#",
            "D",
            "D#",
            "E",
            "F",
            "F#",
            "G",
            "G#",
            "A",
            "A#",
            "B",
            "Db",
            "Eb",
            "Gb",
            "Ab",
            "Bb",
        }

        notes = self.engine.generate(self.chords, bars=4, bpm=120)

        for n in notes:
            assert n.note in valid, f"Invalid note: {n.note}"

    def test_octaves_in_range(self):
        notes = self.engine.generate(self.chords, bars=4, bpm=120)

        for n in notes:
            assert 3 <= n.octave <= 5, f"Octave {n.octave} out of range"

    def test_durations_positive(self):
        notes = self.engine.generate(self.chords, bars=4, bpm=120)

        for n in notes:
            assert n.duration > 0

    def test_deterministic_with_seed(self):
        random.seed(42)
        notes1 = self.engine.generate(self.chords, bars=4, bpm=120)
        random.seed(42)
        notes2 = self.engine.generate(self.chords, bars=4, bpm=120)

        assert notes1 == notes2

    def test_different_seeds_differ(self):
        random.seed(1)
        notes1 = self.engine.generate(self.chords, bars=4, bpm=120)
        random.seed(99)
        notes2 = self.engine.generate(self.chords, bars=4, bpm=120)

        assert notes1 != notes2

    def test_most_notes_in_scale(self):
        random.seed(42)
        chords = parse_progression("C | C | C | C")

        notes = self.engine.generate(chords, bars=4, bpm=120)

        c_major_scale = {"C", "D", "E", "F", "G", "A", "B"}
        in_scale = sum(1 for n in notes if n.note in c_major_scale)
        ratio = in_scale / len(notes)
        assert ratio >= 0.8, f"Only {ratio:.0%} in scale"

    def test_single_chord(self):
        notes = self.engine.generate([Chord("C", "major")], bars=2, bpm=120)

        assert len(notes) > 0

    def test_different_bpm_affects_timing(self):
        random.seed(42)
        slow = self.engine.generate(self.chords, bars=4, bpm=60)
        random.seed(42)
        fast = self.engine.generate(self.chords, bars=4, bpm=180)

        slow_end = max(n.start + n.duration for n in slow)
        fast_end = max(n.start + n.duration for n in fast)
        assert slow_end > fast_end

    def test_beat_1_is_chord_tone(self):
        random.seed(42)
        chords = parse_progression("C | Am | F | G")

        notes = self.engine.generate(chords, bars=4, bpm=120)

        beat_dur = 60.0 / 120
        for i, chord in enumerate(chords):
            chord_start = i * 4 * beat_dur
            chord_tones = {n for n in chord.notes}
            first_notes = [n for n in notes if abs(n.start - chord_start) < 0.01]
            assert len(first_notes) > 0, f"No note at beat 1 of chord {i}"
            assert first_notes[0].note in chord_tones, (
                f"Beat 1 of chord {i}: {first_notes[0].note} not in {chord_tones}"
            )

    def test_has_rests(self):
        random.seed(42)
        notes = self.engine.generate(self.chords, bars=4, bpm=120)

        beat_dur = 60.0 / 120
        total_beats = 4 * len(self.chords)
        beats_with_notes = set()
        for n in notes:
            beat_idx = int(n.start / beat_dur)
            beats_with_notes.add(beat_idx)

        assert len(beats_with_notes) < total_beats, "Every beat has a note — no rests"

    def test_motifs_repeat(self):
        random.seed(42)
        chords = parse_progression("C | C | C | C")

        notes = self.engine.generate(chords, bars=4, bpm=120)

        beat_dur = 60.0 / 120
        phrases = [[], [], [], []]
        for n in notes:
            chord_idx = min(int(n.start / (4 * beat_dur)), 3)
            phrases[chord_idx].append(n.note)

        shared_01 = set(phrases[0]) & set(phrases[1])
        shared_23 = set(phrases[2]) & set(phrases[3])
        assert len(shared_01) > 0 or len(shared_23) > 0, "No motif repetition detected"
