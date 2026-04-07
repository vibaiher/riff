"""Tests for efficient note lookup in SongData."""

from riff.audio.song import SongData, SongNote


def _big_song(n: int = 2000) -> SongData:
    notes = [SongNote(note="C", octave=4, start=i * 0.1, duration=0.05) for i in range(n)]
    return SongData(notes=notes, bpm=120.0)


def test_notes_at_finds_active_note():
    song = _big_song()

    result = song.notes_at(50.0)

    assert len(result) == 1
    assert result[0].start == 50.0


def test_notes_at_returns_empty_in_gap():
    song = _big_song()

    result = song.notes_at(50.06)

    assert result == []


def test_notes_between_returns_range():
    song = _big_song()

    result = song.notes_between(10.0, 10.5)

    assert len(result) == 5
    assert all(10.0 <= n.start < 10.5 for n in result)


def test_note_at_or_before_finds_last():
    song = _big_song()

    result = song.note_at_or_before(100.05)

    assert result is not None
    assert result.start == 100.0
