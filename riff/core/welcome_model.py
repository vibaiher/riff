"""Welcome screen domain model — pure logic, no UI."""

from __future__ import annotations

from riff.core.state import MODES

_SAMPLE_RATE = 44100
_WAVEFORM_WINDOW = _SAMPLE_RATE // 3

_audio = None
_audio_duration: float = 310.0


class WelcomeModel:
    def __init__(self) -> None:
        self._index = 0

    def move_down(self) -> None:
        self._index = (self._index + 1) % len(MODES)

    def move_up(self) -> None:
        self._index = (self._index - 1) % len(MODES)

    def selected_mode(self) -> str:
        return MODES[self._index]

    def confirm_selection(self) -> str:
        return self.selected_mode()


def _load_audio():
    global _audio, _audio_duration

    if _audio is not None:
        return _audio

    import pathlib
    import numpy as np
    from riff.audio.song import SongData

    midi_path = pathlib.Path(__file__).parent.parent / "assets" / "zombie.mid"
    song = SongData.from_file(str(midi_path))
    audio = song.render_audio()
    _audio_duration = song.total_duration
    _audio = np.abs(audio) if len(audio) > 0 else np.zeros(1, dtype=np.float32)
    return _audio


def fake_waveform(n_bars: int = 28, t: float = 0.0) -> list[float]:
    import numpy as np

    audio = _load_audio()
    position = t % _audio_duration
    center = int(position * _SAMPLE_RATE)
    start = max(0, center - _WAVEFORM_WINDOW // 2)
    end = min(len(audio), start + _WAVEFORM_WINDOW)
    chunk = audio[start:end]

    if len(chunk) == 0:
        return [0.0] * n_bars

    segments = np.array_split(chunk, n_bars)
    return [float(np.max(s)) if len(s) > 0 else 0.0 for s in segments]
