"""RIFF — Real-time Intelligent Frequency Follower.

Entry point.  Run with:
    riff                  # if installed via pip / uv
    python -m riff        # from the project root
    uv run riff           # with uv
"""

from __future__ import annotations

import argparse
import signal
import time
import warnings

warnings.filterwarnings("ignore", message="Couldn't find ffmpeg", category=RuntimeWarning)
import sys

from .audio.analyzer import AudioAnalyzer
from .audio.capture import AudioCapture
from .core.state import AppState, MODES
from .ui.display import RiffDisplay
from .ui.welcome import run_welcome


def main() -> None:
    parser = argparse.ArgumentParser(prog="riff", description="RIFF — real-time jam companion")
    parser.parse_args()

    # ── Welcome screen — pick a mode ─────────────────────────────────────────
    selected = run_welcome()
    if selected is None:
        print("\n[RIFF] Goodbye 🎸")
        return

    state = AppState()
    mode_idx = MODES.index(selected) if selected in MODES else 0
    state.update(mode_index=mode_idx)

    def _shutdown(sig, frame):
        state.update(running=False)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # ── Wire up the audio pipeline ────────────────────────────────────────────
    capture = AudioCapture(state)
    state.set_audio_queue(capture.audio_queue)
    analyzer = AudioAnalyzer(state, capture.audio_queue)
    display = RiffDisplay(state)

    # ── Start everything ──────────────────────────────────────────────────────
    try:
        capture.start()
        analyzer.start()
        display.run()
    except Exception as exc:
        print(f"\n[RIFF] Fatal error: {exc}", file=sys.stderr)
        raise
    finally:
        state.update(running=False)
        time.sleep(0.1)
        analyzer.stop()
        try:
            capture.stop()
        except Exception:
            pass
        print("\n[RIFF] Goodbye 🎸")


if __name__ == "__main__":
    main()
