"""Logo header widget."""

from __future__ import annotations

from rich.align import Align
from rich.console import Group
from rich.text import Text
from textual.widgets import Static

from riff.ui.palette import LOGO, YOU_COLOR, META_VAL


class LogoHeader(Static):
    def render(self) -> Group:
        logo = Text(LOGO, style=f"bold {YOU_COLOR}")
        subtitle = Text(
            "real-time intelligent frequency follower",
            style=META_VAL,
            justify="center",
        )
        return Group(Align.center(logo), Align.center(subtitle))
