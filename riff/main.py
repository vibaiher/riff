"""RIFF — Real-time Intelligent Frequency Follower.

Entry point.  Run with:
    riff                  # if installed via pip / uv
    python -m riff        # from the project root
    uv run riff           # with uv

Phase 1: listen, analyse, and visualise.
Phase 2: Adaptive Markov melodic responder.
"""
from __future__ import annotations

import argparse
import queue
import signal
import warnings

warnings.filterwarnings("ignore", message="Couldn't find ffmpeg", category=RuntimeWarning)
import sys

from .audio.capture  import AudioCapture, FilePlayback
from .audio.analyzer import AudioAnalyzer
from .ai.responder   import RiffResponder
from .core.state     import AppState
from .ui.display     import RiffDisplay


def main() -> None:
    parser = argparse.ArgumentParser(prog="riff", description="RIFF — real-time jam companion")
    parser.add_argument("--file", metavar="PATH", help="audio file to jam over (mp3, flac, wav, …)")
    args = parser.parse_args()

    state = AppState()

    # ── Clean shutdown on SIGINT / SIGTERM ────────────────────────────────────
    def _shutdown(sig, frame):
        state.update(running=False)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # ── Wire up the audio pipeline ────────────────────────────────────────────
    note_queue = queue.Queue(maxsize=32)
    if args.file:
        capture = FilePlayback(state, args.file)
    else:
        capture = AudioCapture(state)
    analyzer   = AudioAnalyzer(state, capture.audio_queue, note_queue)
    responder  = RiffResponder(state, note_queue)

    display = RiffDisplay(state)

    # ── Start everything ──────────────────────────────────────────────────────
    try:
        capture.start()
        analyzer.start()
        responder.start()
        display.run()          # blocks until user quits
    except Exception as exc:
        # Make sure we restore the terminal before printing the error
        print(f"\n[RIFF] Fatal error: {exc}", file=sys.stderr)
        raise
    finally:
        state.update(running=False)
        responder.stop()
        analyzer.stop()
        capture.stop()
        print("\n[RIFF] Goodbye 🎸")


if __name__ == "__main__":
    main()
