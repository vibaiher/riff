"""Tests for the welcome / start screen."""

from riff.core.state import MODES
from riff.ui.welcome import WelcomeScreen


# [TEST] Default selection is the first mode (FREE)
def test_move_down_selects_next_mode():
    screen = WelcomeScreen()

    screen.move_down()

    assert screen.selected_mode() == "COMPOSE"


# [was TEST] move_selection down moves to next mode
def test_move_up_selects_previous_mode():
    screen = WelcomeScreen()
    screen.move_down()  # COMPOSE

    screen.move_up()

    assert screen.selected_mode() == "FREE"


def test_move_down_wraps_at_bottom():
    screen = WelcomeScreen()
    for _ in range(len(MODES)):
        screen.move_down()

    assert screen.selected_mode() == "FREE"


def test_move_up_wraps_at_top():
    screen = WelcomeScreen()

    screen.move_up()

    assert screen.selected_mode() == "COMPOSE"


def test_confirm_returns_selected_mode():
    screen = WelcomeScreen()
    screen.move_down()  # COMPOSE

    result = screen.confirm_selection()

    assert result == "COMPOSE"


def test_all_modes_are_reachable():
    screen = WelcomeScreen()

    reachable = []
    for _ in range(len(MODES)):
        reachable.append(screen.selected_mode())
        screen.move_down()

    assert reachable == ["FREE", "COMPOSE"]
def test_fake_waveform_returns_data_of_expected_length():
    from riff.ui.welcome import fake_waveform

    data = fake_waveform(n_bars=28, t=0.0)

    assert len(data) == 28
    assert all(isinstance(v, float) for v in data)


def test_fake_waveform_changes_over_time():
    from riff.ui.welcome import fake_waveform

    data_a = fake_waveform(n_bars=28, t=30.0)
    data_b = fake_waveform(n_bars=28, t=31.0)

    assert data_a != data_b


def test_build_welcome_layout_has_expected_sections():
    from riff.ui.welcome import build_welcome_layout

    layout = build_welcome_layout(selected_index=0, term_height=42, term_width=146, t=0.0)

    assert layout["header"] is not None
    assert layout["modes"] is not None
    assert layout["waveform"] is not None


def test_selected_mode_has_arrow_indicator():
    from riff.ui.welcome import _mode_selector

    text = _mode_selector(selected_index=0)
    plain = text.plain

    lines = plain.strip().split("\n")
    assert "▸" in lines[0]
    assert "▸" not in lines[1]


def test_default_selection_is_free():
    screen = WelcomeScreen()

    result = screen.selected_mode()

    assert result == "FREE"
