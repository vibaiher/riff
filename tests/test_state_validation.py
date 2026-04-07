"""Tests for AppState validation and thread-safety improvements."""

import pytest

from riff.core.state import AppState


def test_update_valid_field_works():
    state = AppState()

    state.update(note="C", octave=5)

    snap = state.snapshot()
    assert snap["note"] == "C"
    assert snap["octave"] == 5


def test_update_underscore_field_raises():
    state = AppState()

    with pytest.raises(ValueError):
        state.update(_lock="bad")


def test_snapshot_resolves_engine_without_deadlock():
    state = AppState()

    snap = state.snapshot()

    assert "engine" in snap
    assert isinstance(snap["engine"], str)


def test_update_invalid_field_raises():
    state = AppState()

    with pytest.raises(ValueError, match="typo_field"):
        state.update(typo_field=42)
