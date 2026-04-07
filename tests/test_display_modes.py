"""Tests for mode-aware rendering and state operations."""

from rich.console import Console, Group

from riff.core.state import AppState
from riff.ui.widgets.riff_panel import RiffPanel, _free_content, _compose_content
from riff.ui.widgets.controls_bar import ControlsBar


def _render_to_str(renderable) -> str:
    r = Group(*renderable) if isinstance(renderable, list) else renderable
    console = Console(file=None, force_terminal=True, width=100)
    with console.capture() as capture:
        console.print(r)
    return capture.get()


class TestStateOperations:
    def test_m_changes_mode(self):
        state = AppState()

        state.next_mode()

        assert state.mode == "COMPOSE"

    def test_t_changes_timbre(self):
        state = AppState()

        state.next_timbre()

        assert state.timbre == "WARM"

    def test_speed_up(self):
        state = AppState()

        state.speed_up()

        assert state.snapshot()["song_speed"] == 1.25

    def test_speed_down(self):
        state = AppState()

        state.speed_down()

        assert state.snapshot()["song_speed"] == 0.75

    def test_speed_minimum(self):
        state = AppState()
        for _ in range(10):
            state.speed_down()

        assert state.snapshot()["song_speed"] == 0.25

    def test_speed_maximum(self):
        state = AppState()
        for _ in range(10):
            state.speed_up()

        assert state.snapshot()["song_speed"] == 1.5


class TestControlsBar:
    def test_controls_shows_quit(self):
        state = AppState()
        bar = ControlsBar()
        bar._snap = state.snapshot()

        rendered = _render_to_str(bar.render())

        assert "quit" in rendered

    def test_controls_shows_mode(self):
        state = AppState()
        bar = ControlsBar()
        bar._snap = state.snapshot()

        rendered = _render_to_str(bar.render())

        assert "mode" in rendered

    def test_controls_shows_load(self):
        state = AppState()
        bar = ControlsBar()
        bar._snap = state.snapshot()

        rendered = _render_to_str(bar.render())

        assert "load" in rendered


class TestFreeMode:
    def test_free_shows_play_prompt_when_silent(self):
        snap = AppState().snapshot()

        content = _free_content(snap, wf_height=5)
        rendered = _render_to_str(content)

        assert "play something" in rendered

    def test_free_shows_note_when_playing(self):
        state = AppState()
        state.update(note="E", octave=4, bpm=120.0)
        snap = state.snapshot()

        content = _free_content(snap, wf_height=5)
        rendered = _render_to_str(content)

        assert "E4" in rendered


class TestComposeMode:
    def _snap_with_chords(self, chords: list[str], **overrides) -> dict:
        state = AppState()
        state.update(mode_index=1)
        for ch in chords:
            state.add_chord(ch)
        if overrides:
            state.update(**overrides)
        return state.snapshot()

    def test_shows_captured_chords(self):
        snap = self._snap_with_chords(["Am", "F", "C", "G"])

        content = _compose_content(snap, wf_height=5)
        rendered = _render_to_str(content)

        assert "Am" in rendered
        assert "G" in rendered

    def test_shows_generate_hint_with_chords(self):
        snap = self._snap_with_chords(["Am", "F"])

        content = _compose_content(snap, wf_height=5)
        rendered = _render_to_str(content)

        assert "generate" in rendered or "[g]" in rendered

    def test_shows_engine_in_meta(self):
        snap = self._snap_with_chords(["Am"])

        content = _compose_content(snap, wf_height=5)
        rendered = _render_to_str(content)

        assert "engine" in rendered
        assert "phrase" in rendered

    def test_shows_listening_when_no_chords(self):
        state = AppState()
        state.update(mode_index=1)
        snap = state.snapshot()

        content = _compose_content(snap, wf_height=5)
        rendered = _render_to_str(content)

        assert "listening" in rendered or "play to capture" in rendered

    def test_shows_gen_status_playing(self):
        snap = self._snap_with_chords(["Am", "F"], gen_status="playing", gen_note_count=20, gen_duration=8.0)

        content = _compose_content(snap, wf_height=5)
        rendered = _render_to_str(content)

        assert "playing" in rendered
