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

    def test_practice_mode_panel_title_contains_practice(self):
        snap = _snap_with_mode("PRACTICE")

        layout = build_layout(snap, term_height=42, term_width=146)

        panel = layout["riff"].renderable
        assert "PRACTICE" in str(panel.title)

    def test_ear_training_mode_panel_title_contains_ear_training(self):
        snap = _snap_with_mode("EAR_TRAINING")

        layout = build_layout(snap, term_height=42, term_width=146)

        panel = layout["riff"].renderable
        assert "EAR TRAINING" in str(panel.title)


class TestControlsBar:
    def test_controls_bar_shows_m_mode(self):
        snap = AppState().snapshot()

        text = _controls_bar(snap)

        plain = text.plain
        assert "mode" in plain

    def test_controls_bar_shows_speed(self):
        snap = AppState().snapshot()

        text = _controls_bar(snap)

        plain = text.plain
        assert "speed" in plain


class TestKeyboardHandler:
    def test_m_key_changes_mode(self):
        state = AppState()
        from riff.ui.display import KeyboardHandler

        kb = KeyboardHandler(state)

        kb._handle("m")

        assert state.mode == "PRACTICE"

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


class TestFreeModeWithSong:
    def _snap_with_song(self, **overrides) -> dict:
        state = AppState()
        defaults = {
            "song_note": "E",
            "song_octave": 4,
            "song_db": -30.0,
            "song_waveform": [0.5] * 48,
            "song_bpm": 120.0,
            "song_position": 10.0,
            "song_upcoming": ["F4", "G4", "A4"],
        }
        defaults.update(overrides)
        state.update(**defaults)
        return state.snapshot()

    def test_shows_note_badge(self):
        snap = self._snap_with_song(song_note="E", song_octave=4)

        content = _mode_content("FREE", snap, wf_height=5, n_bars=40)
        rendered = _render_parts(content)

        assert "E4" in rendered

    def test_shows_db_level_bar(self):
        snap = self._snap_with_song(song_db=-30.0)

        content = _mode_content("FREE", snap, wf_height=5, n_bars=40)
        rendered = _render_parts(content)

        assert "dB" in rendered

    def test_shows_waveform_blocks(self):
        snap = self._snap_with_song(song_waveform=[0.8] * 48)

        content = _mode_content("FREE", snap, wf_height=5, n_bars=40)
        rendered = _render_parts(content)

        assert "█" in rendered or "▇" in rendered or "▆" in rendered

    def test_shows_upcoming_as_chord_pills(self):
        snap = self._snap_with_song(song_upcoming=["D4", "E4", "F4"])

        content = _mode_content("FREE", snap, wf_height=5, n_bars=40)
        rendered = _render_parts(content)

        assert "[D4]" in rendered
        assert "[E4]" in rendered

    def test_shows_meta_with_bpm_and_position(self):
        snap = self._snap_with_song(song_bpm=140.0, song_position=65.0)

        content = _mode_content("FREE", snap, wf_height=5, n_bars=40)
        rendered = _render_parts(content)

        assert "140" in rendered
        assert "1:05" in rendered

    def test_shows_placeholder_when_no_song(self):
        snap = _snap_with_mode("FREE")

        content = _mode_content("FREE", snap, wf_height=5, n_bars=40)
        rendered = _render_parts(content)

        assert "metrics coming soon" in rendered
