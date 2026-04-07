"""Tests for SongPlayer as context manager."""

import numpy as np

from riff.audio.song import SongPlayer


def test_song_player_is_context_manager():
    audio = np.zeros(100, dtype=np.float32)

    with SongPlayer(audio) as player:
        assert player is not None

    assert not player._playing


def test_song_player_stops_on_exception():
    audio = np.zeros(100, dtype=np.float32)

    try:
        with SongPlayer(audio) as player:
            player.start()
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    assert not player._playing
