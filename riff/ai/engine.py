"""Pluggable melody engine system.

Engines are registered at import time. The UI cycles through them with 'e'.
To add a new engine:
  1. Create a class with `name: str` and `generate(chords, bars, bpm) -> list[SongNote]`
  2. Call `register_engine(YourEngine())` at module level
  3. Import the module in `riff/ai/__init__.py`
"""

from __future__ import annotations

from typing import Protocol

from riff.audio.chords import Chord
from riff.audio.song import SongNote


class MelodyEngine(Protocol):
    name: str

    def generate(
        self, chords: list[Chord], bars: int = 4, bpm: int = 120
    ) -> list[SongNote]: ...


_registry: dict[str, MelodyEngine] = {}


def register_engine(engine: MelodyEngine) -> None:
    _registry[engine.name] = engine


def get_engine(name: str) -> MelodyEngine:
    if name not in _registry:
        raise KeyError(f"Unknown engine: {name!r}. Available: {list(_registry)}")
    return _registry[name]


def list_engines() -> list[str]:
    return list(_registry.keys())


# Auto-register built-in engines
from riff.ai.phrase import PhraseEngine  # noqa: E402

register_engine(PhraseEngine())
