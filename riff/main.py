"""RIFF — Real-time Intelligent Frequency Follower.

Entry point.  Run with:
    riff                  # if installed via pip / uv
    python -m riff        # from the project root
    uv run riff           # with uv

Phase 1: listen, analyse, and visualise.
Phase 2 (next): plug in MelodyRNN after analyzer.start() and before display.run().
"""
from __future__ import annotations

import signal
import sys

from .audio.capture  import AudioCapture
from .audio.analyzer import AudioAnalyzer
from .core.state     import AppState
from .ui.display     import RiffDisplay


def main() -> None:
    state = AppState()

    # ── Clean shutdown on SIGINT / SIGTERM ────────────────────────────────────
    def _shutdown(sig, frame):
        state.update(running=False)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # ── Wire up the audio pipeline ────────────────────────────────────────────
    capture  = AudioCapture(state)
    analyzer = AudioAnalyzer(state, capture.audio_queue)

    # Phase 2: instantiate MelodyRNN here and pass it to a RiffResponder
    # riff_responder = RiffResponder(state, model_checkpoint="...")

    display = RiffDisplay(state)

    # ── Start everything ──────────────────────────────────────────────────────
    try:
        capture.start()
        analyzer.start()
        # Phase 2: riff_responder.start()
        display.run()          # blocks until user quits
    except Exception as exc:
        # Make sure we restore the terminal before printing the error
        print(f"\n[RIFF] Fatal error: {exc}", file=sys.stderr)
        raise
    finally:
        state.update(running=False)
        analyzer.stop()
        capture.stop()
        # Phase 2: riff_responder.stop()
        print("\n[RIFF] Goodbye 🎸")


if __name__ == "__main__":
    main()
