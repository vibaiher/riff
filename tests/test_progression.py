"""Tests for progression selection and duration matching."""

from riff.ai.generate import select_progression


class TestSelectProgression:
    def test_many_repeated_chords_returns_unique_cycle(self):
        chords = ["C", "Am", "F", "G", "C", "Am", "F", "G", "C", "Am"]

        result = select_progression(chords)

        assert result == ["C", "Am", "F", "G"]

    def test_preserves_order_of_first_appearance(self):
        chords = ["G", "Em", "C", "D", "G", "Em"]

        result = select_progression(chords)

        assert result == ["G", "Em", "C", "D"]

    def test_single_chord(self):
        result = select_progression(["Am", "Am", "Am"])

        assert result == ["Am"]

    def test_empty_raises(self):
        import pytest

        with pytest.raises(ValueError):
            select_progression([])


class TestCalculateBars:
    def test_returns_bars_for_target_duration(self):
        from riff.ai.generate import calculate_bars

        bars = calculate_bars(target_duration=10.0, n_chords=4, bpm=120)

        expected_duration = bars * 4 * (60.0 / 120)
        assert abs(expected_duration - 10.0) <= (60.0 / 120)

    def test_100_note_song_does_not_explode(self):
        from riff.ai.generate import calculate_bars, select_progression

        chords = ["C", "Am", "F", "G"] * 25
        unique = select_progression(chords)
        bars = calculate_bars(target_duration=30.0, n_chords=len(unique), bpm=120)

        total_duration = bars * len(unique) * (60.0 / 120)

        assert total_duration <= 60.0

    def test_zero_target_duration_uses_default(self):
        from riff.ai.generate import calculate_bars

        bars = calculate_bars(target_duration=0.0, n_chords=4, bpm=120)

        assert bars >= 1

    def test_very_short_target_returns_minimum_1(self):
        from riff.ai.generate import calculate_bars

        bars = calculate_bars(target_duration=0.1, n_chords=4, bpm=120)

        assert bars >= 1
