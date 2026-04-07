"""Tests for the generate subcommand logic."""

from riff.ai.generate import generate_song
from riff.audio.song import SongData


class TestGenerateSong:
    def test_returns_song_data(self):
        song = generate_song("Am | F | C | G", bars=4, bpm=120, engine="phrase")
        assert isinstance(song, SongData)
        assert song.bpm == 120

    def test_has_notes(self):
        song = generate_song("C | G | Am | F", bars=4, bpm=120, engine="phrase")
        assert len(song.notes) > 0

    def test_total_duration_within_bounds(self):
        bpm = 120
        bars = 4
        n_chords = 4
        max_dur = bars * n_chords * (60.0 / bpm)
        song = generate_song("C | F | G | C", bars=bars, bpm=bpm, engine="phrase")
        assert song.total_duration > 0
        assert song.total_duration <= max_dur + 0.01

    def test_unknown_engine_raises(self):
        import pytest

        with pytest.raises(KeyError):
            generate_song("C | G", engine="nonexistent_xyz")

    def test_renders_audio(self):
        song = generate_song("Am | F | C | G", bars=2, bpm=120, engine="phrase")
        audio = song.render_audio()
        assert len(audio) > 0
