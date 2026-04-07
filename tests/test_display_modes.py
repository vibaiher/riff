"""Tests for mode-aware display rendering."""

from rich.console import Console, Group

from riff.core.state import AppState
from riff.ui.display import _controls_bar, _mode_content, build_layout


def _snap_with_mode(mode: str) -> dict:
    state = AppState()
    while state.mode != mode:
        state.next_mode()
    return state.snapshot()


class TestRiffPanelTitle:
    def test_free_mode_panel_title_contains_free(self):
        snap = _snap_with_mode("FREE")

        layout = build_layout(snap, term_height=42, term_width=146)

        panel = layout["riff"].renderable
        assert "FREE" in str(panel.title)

    def test_compose_mode_panel_title_contains_compose(self):
        snap = _snap_with_mode("COMPOSE")

        layout = build_layout(snap, term_height=42, term_width=146)

        panel = layout["riff"].renderable
        assert "COMPOSE" in str(panel.title)


class TestControlsBar:
    def test_controls_bar_shows_m_mode(self):
        snap = AppState().snapshot()

        text = _controls_bar(snap)

        plain = text.plain
        assert "mode" in plain

    def test_controls_bar_shows_generate(self):
        snap = AppState().snapshot()

        text = _controls_bar(snap)

        plain = text.plain
        assert "generate" in plain


class TestControlsBarInputMode:
    def test_input_mode_shows_prompt_with_buffer(self):
        state = AppState(mode_index=1)
        state.start_input("file")
        state.update(input_buffer="/tmp/song")
        snap = state.snapshot()

        text = _controls_bar(snap)

        plain = text.plain
        assert "/tmp/song" in plain

    def test_controls_bar_shows_f_load(self):
        snap = AppState().snapshot()

        text = _controls_bar(snap)

        plain = text.plain
        assert "load" in plain


class TestKeyboardHandler:
    def test_m_key_changes_mode(self):
        state = AppState()
        from riff.ui.display import KeyboardHandler

        kb = KeyboardHandler(state)

        kb._handle("m")

        assert state.mode == "COMPOSE"

    def test_t_key_changes_timbre(self):
        state = AppState()
        from riff.ui.display import KeyboardHandler

        kb = KeyboardHandler(state)

        kb._handle("t")

        assert state.timbre == "WARM"

    def test_bracket_right_speeds_up(self):
        state = AppState()
        from riff.ui.display import KeyboardHandler

        kb = KeyboardHandler(state)

        kb._handle("]")

        assert state.snapshot()["song_speed"] == 1.25

    def test_bracket_left_slows_down(self):
        state = AppState()
        from riff.ui.display import KeyboardHandler

        kb = KeyboardHandler(state)

        kb._handle("[")

        assert state.snapshot()["song_speed"] == 0.75

    def test_speed_does_not_go_below_minimum(self):
        state = AppState()
        from riff.ui.display import KeyboardHandler

        kb = KeyboardHandler(state)
        for _ in range(10):
            kb._handle("[")

        assert state.snapshot()["song_speed"] == 0.25

    def test_speed_does_not_go_above_maximum(self):
        state = AppState()
        from riff.ui.display import KeyboardHandler

        kb = KeyboardHandler(state)
        for _ in range(10):
            kb._handle("]")

        assert state.snapshot()["song_speed"] == 1.5


def _render_parts(parts) -> str:
    renderable = Group(*parts) if isinstance(parts, list) else parts
    console = Console(file=None, force_terminal=True, width=100)
    with console.capture() as capture:
        console.print(renderable)
    return capture.get()


class TestFreeMode:
    def test_free_shows_play_prompt_when_silent(self):
        snap = _snap_with_mode("FREE")

        content = _mode_content("FREE", snap, wf_height=5, n_bars=40)
        rendered = _render_parts(content)

        assert "play something" in rendered

    def test_free_shows_note_when_playing(self):
        state = AppState()
        state.update(note="E", octave=4, bpm=120.0)
        snap = state.snapshot()

        content = _mode_content("FREE", snap, wf_height=5, n_bars=40)
        rendered = _render_parts(content)

        assert "E4" in rendered


class TestComposeMode:
    def _snap_with_chords(self, chords: list[str], **overrides) -> dict:
        state = AppState()
        state.update(mode_index=1)  # COMPOSE
        for ch in chords:
            state.add_chord(ch)
        if overrides:
            state.update(**overrides)
        return state.snapshot()

    def test_shows_captured_chords(self):
        snap = self._snap_with_chords(["Am", "F", "C", "G"])

        content = _mode_content("COMPOSE", snap, wf_height=5, n_bars=40)
        rendered = _render_parts(content)

        assert "Am" in rendered
        assert "G" in rendered

    def test_shows_generate_hint_with_chords(self):
        snap = self._snap_with_chords(["Am", "F"])

        content = _mode_content("COMPOSE", snap, wf_height=5, n_bars=40)
        rendered = _render_parts(content)

        assert "generate" in rendered or "[g]" in rendered

    def test_shows_engine_in_meta(self):
        snap = self._snap_with_chords(["Am"])

        content = _mode_content("COMPOSE", snap, wf_height=5, n_bars=40)
        rendered = _render_parts(content)

        assert "engine" in rendered
        assert "phrase" in rendered

    def test_shows_listening_when_no_chords(self):
        state = AppState()
        state.update(mode_index=1)
        snap = state.snapshot()

        content = _mode_content("COMPOSE", snap, wf_height=5, n_bars=40)
        rendered = _render_parts(content)

        assert "listening" in rendered or "play to capture" in rendered

    def test_shows_gen_status_playing(self):
        snap = self._snap_with_chords(["Am", "F"], gen_status="playing", gen_note_count=20, gen_duration=8.0)

        content = _mode_content("COMPOSE", snap, wf_height=5, n_bars=40)
        rendered = _render_parts(content)

        assert "playing" in rendered
