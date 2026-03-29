"""RIFF — Real-time Intelligent Frequency Follower.

Entry point.  Run with:
    riff                  # if installed via pip / uv
    python -m riff        # from the project root
    uv run riff           # with uv
"""

from __future__ import annotations

import argparse
import os
import signal
import threading
import time
import warnings

warnings.filterwarnings("ignore", message="Couldn't find ffmpeg", category=RuntimeWarning)
import sys

from .audio.analyzer import AudioAnalyzer
from .audio.capture import AudioCapture, FilePlayback
from .audio.song import SUPPORTED_EXTENSIONS, SongData, SongPlayer, SongTracker, SongUpdater
from .core.state import AppState
from .ui.display import RiffDisplay


def main() -> None:
    parser = argparse.ArgumentParser(prog="riff", description="RIFF — real-time jam companion")
    parser.add_argument("--file", metavar="PATH", help="audio or MIDI file (mp3, wav, mid, ...)")
    args = parser.parse_args()

    state = AppState()

    def _shutdown(sig, frame):
        state.update(running=False)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # ── Wire up the audio pipeline ────────────────────────────────────────────
    is_midi = args.file and os.path.splitext(args.file)[1].lower() in SUPPORTED_EXTENSIONS

    if is_midi:
        song = SongData.from_file(args.file)
        rendered_audio = song.render_audio()
        tracker = SongTracker(song)
        song_updater = SongUpdater(state, tracker, audio=rendered_audio)
        song_player = SongPlayer(rendered_audio)
        capture = AudioCapture(state)
    elif args.file:
        capture = FilePlayback(state, args.file)
    else:
        capture = AudioCapture(state)

    analyzer = AudioAnalyzer(state, capture.audio_queue)
    display = RiffDisplay(state)

    # ── Song tracking thread (MIDI only) ──────────────────────────────────────
    def _song_loop():
        tracker.start()
        song_player.start()
        was_muted = False
        current_speed = 1.0

        while state.snapshot()["running"] and not tracker.is_finished:
            snap = state.snapshot()
            muted = snap["muted"]
            speed = snap["song_speed"]

            if muted and not was_muted:
                tracker.pause()
                song_player.pause()
            elif not muted and was_muted:
                tracker.resume()
                song_player.resume(tracker.position)
            was_muted = muted

            if speed != current_speed and not muted:
                tracker.set_speed(speed)
                song_player.set_speed(speed, tracker.position)
                current_speed = speed

            if not muted:
                song_updater.tick()
            time.sleep(0.05)

        song_updater.tick()
        song_player.stop()

    # ── Start everything ──────────────────────────────────────────────────────
    try:
        capture.start()
        analyzer.start()
        if is_midi:
            threading.Thread(target=_song_loop, daemon=True, name="riff-song").start()
        display.run()
    except Exception as exc:
        print(f"\n[RIFF] Fatal error: {exc}", file=sys.stderr)
        raise
    finally:
        state.update(running=False)
        if is_midi:
            song_player.stop()
        time.sleep(0.1)
        analyzer.stop()
        try:
            capture.stop()
        except Exception:
            pass
        print("\n[RIFF] Goodbye 🎸")


if __name__ == "__main__":
    main()
