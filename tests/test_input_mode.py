"""Tests for input mode integration in AppState."""

from riff.core.state import AppState


class TestInputModeState:
    def test_start_input_sets_mode_and_clears_buffer(self):
        state = AppState()

        state.start_input("file")

        snap = state.snapshot()
        assert snap["input_mode"] == "file"
        assert snap["input_buffer"] == ""

    def test_snapshot_includes_input_fields_by_default(self):
        state = AppState()

        snap = state.snapshot()

        assert snap["input_mode"] == ""
        assert snap["input_buffer"] == ""

    def test_cancel_input_clears_mode_and_buffer(self):
        state = AppState()
        state.start_input("file")
        state.update(input_buffer="/some/path")

        state.cancel_input()

        snap = state.snapshot()
        assert snap["input_mode"] == ""
        assert snap["input_buffer"] == ""

    def test_confirm_input_returns_buffer_and_clears(self):
        state = AppState()
        state.start_input("file")
        state.update(input_buffer="/my/song.mid")

        result = state.confirm_input()

        assert result == "/my/song.mid"
        snap = state.snapshot()
        assert snap["input_mode"] == ""
        assert snap["input_buffer"] == ""
