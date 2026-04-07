"""Tests for the mode system in AppState."""

import pytest

from riff.core.state import AppState


class TestModeSystem:
    def test_default_mode_is_free(self):
        state = AppState()

        result = state.mode

        assert result == "FREE"

    def test_next_mode_cycles_free_to_compose(self):
        state = AppState()

        state.next_mode()

        assert state.mode == "COMPOSE"

    def test_next_mode_wraps_around_to_free(self):
        state = AppState()
        for _ in range(2):
            state.next_mode()

        assert state.mode == "FREE"

    def test_mode_is_included_in_snapshot(self):
        state = AppState()

        snap = state.snapshot()

        assert snap["mode"] == "FREE"

    def test_next_mode_sets_status_msg(self):
        state = AppState()

        state.next_mode()

        assert "COMPOSE" in state.snapshot()["status_msg"]


class TestRemovedResponderFields:
    REMOVED_KEYS = [
        "riff_note",
        "riff_octave",
        "riff_waveform",
        "riff_active",
        "riff_next_note",
        "riff_model",
        "riff_db",
        "riff_chords",
        "riff_density",
        "riff_listening",
        "markov_order",
        "markov_learned",
        "markov_phase",
        "markov_confidence",
    ]

    @pytest.mark.parametrize("key", REMOVED_KEYS)
    def test_responder_field_not_in_snapshot(self, key):
        state = AppState()

        snap = state.snapshot()

        assert key not in snap
