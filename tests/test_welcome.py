"""Tests for the welcome screen domain model."""

from riff.core.state import MODES
from riff.core.welcome_model import WelcomeModel, fake_waveform


def test_move_down_selects_next_mode():
    screen = WelcomeModel()

    screen.move_down()

    assert screen.selected_mode() == "COMPOSE"


def test_move_up_selects_previous_mode():
    screen = WelcomeModel()
    screen.move_down()

    screen.move_up()

    assert screen.selected_mode() == "FREE"


def test_move_down_wraps_at_bottom():
    screen = WelcomeModel()
    for _ in range(len(MODES)):
        screen.move_down()

    assert screen.selected_mode() == "FREE"


def test_move_up_wraps_at_top():
    screen = WelcomeModel()

    screen.move_up()

    assert screen.selected_mode() == "COMPOSE"


def test_confirm_returns_selected_mode():
    screen = WelcomeModel()
    screen.move_down()

    result = screen.confirm_selection()

    assert result == "COMPOSE"


def test_all_modes_are_reachable():
    screen = WelcomeModel()

    reachable = []
    for _ in range(len(MODES)):
        reachable.append(screen.selected_mode())
        screen.move_down()

    assert reachable == ["FREE", "COMPOSE"]


def test_default_selection_is_free():
    screen = WelcomeModel()

    result = screen.selected_mode()

    assert result == "FREE"


def test_fake_waveform_returns_data_of_expected_length():
    data = fake_waveform(n_bars=28, t=30.0)

    assert len(data) == 28
    assert all(isinstance(v, float) for v in data)


def test_fake_waveform_changes_over_time():
    data_a = fake_waveform(n_bars=28, t=30.0)
    data_b = fake_waveform(n_bars=28, t=31.0)

    assert data_a != data_b
