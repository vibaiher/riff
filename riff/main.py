"""RIFF — Real-time Intelligent Frequency Follower.

Entry point.  Run with:
    riff                  # if installed via pip / uv
    python -m riff        # from the project root
    uv run riff           # with uv
"""

from __future__ import annotations

import warnings

warnings.filterwarnings("ignore", message="Couldn't find ffmpeg", category=RuntimeWarning)


def main() -> None:
    from riff.ui.app import RiffApp
    app = RiffApp()
    app.run()


if __name__ == "__main__":
    main()
