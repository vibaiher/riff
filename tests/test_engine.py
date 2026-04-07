"""Tests for the pluggable melody engine system."""

from riff.ai.engine import MelodyEngine, get_engine, list_engines, register_engine
from riff.core.state import refresh_engines
from riff.audio.chords import Chord, parse_progression
from riff.audio.song import SongNote


class DummyEngine:
    """Minimal engine for testing the registry."""

    name = "dummy"

    def generate(
        self, chords: list[Chord], bars: int = 4, bpm: int = 120
    ) -> list[SongNote]:
        return [SongNote(note="C", octave=4, start=0.0, duration=0.5)]


class TestEngineRegistry:
    def test_register_and_get(self):
        register_engine(DummyEngine())
        engine = get_engine("dummy")
        assert engine.name == "dummy"

    def test_get_unknown_raises(self):
        import pytest

        with pytest.raises(KeyError):
            get_engine("nonexistent_engine_xyz")

    def test_list_engines_returns_names(self):
        register_engine(DummyEngine())
        names = list_engines()
        assert "dummy" in names

    def test_engine_generate_returns_song_notes(self):
        engine = DummyEngine()
        chords = parse_progression("Am | F | C | G")
        notes = engine.generate(chords, bars=4, bpm=120)
        assert len(notes) > 0
        assert isinstance(notes[0], SongNote)

    def test_phrase_registered_by_default(self):
        names = list_engines()
        assert "phrase" in names


class TestAppStateEngine:
    def test_engine_property(self):
        from riff.core.state import AppState

        state = AppState()
        assert state.engine in list_engines()

    def test_next_engine_cycles(self):
        from riff.core.state import AppState

        # Ensure at least 2 engines
        register_engine(DummyEngine())
        refresh_engines()

        state = AppState()
        engines = list_engines()
        assert len(engines) >= 2

        first = state.engine
        state.next_engine()
        second = state.engine
        assert first != second

    def test_engine_in_snapshot(self):
        from riff.core.state import AppState

        state = AppState()
        snap = state.snapshot()
        assert "engine" in snap
