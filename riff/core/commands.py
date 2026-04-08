"""Application commands for COMPOSE mode — extracted from KeyboardHandler."""

from __future__ import annotations

import os
import threading
import time

import numpy as np

from .state import AppState


class ComposeCommands:
    def __init__(self, state: AppState, riff_player_factory=None) -> None:
        self._state = state
        self._riff_player_factory = riff_player_factory
        self.source_audio: np.ndarray | None = None
        self.generated_audio: np.ndarray | None = None
        self.source_type: str = ""
        self._source_song = None
        self._timed_chords = None
        self._save_dir: str = "."

    def load_file(self, path: str) -> None:
        if not os.path.isfile(path):
            self._state.update(status_msg=f"File not found: {path}", compose_phase="")
            return
        ext = os.path.splitext(path)[1].lower()
        try:
            self.generated_audio = None
            self._state.clear_chords()
            if ext in {".mid", ".midi"}:
                self._load_midi(path)
            else:
                self._load_audio(path)
        except Exception as exc:
            self._state.update(status_msg=f"Load error: {exc}", compose_phase="")

    def _load_midi(self, path: str) -> None:
        from riff.audio.midi_feeder import extract_timed_chords
        from riff.audio.song import SongData

        song = SongData.from_file(path)
        audio = song.render_audio()
        self._source_song = song
        self.source_audio = audio if len(audio) > 0 else None
        self._timed_chords = extract_timed_chords(song)
        self.source_type = "midi"
        self._state.update(
            attached_file=path,
            compose_phase="loaded",
            status_msg=f"Loaded {os.path.basename(path)}",
        )
        self.listen_source()

    def _load_audio(self, path: str) -> None:
        import warnings

        from riff.audio.capture import SAMPLE_RATE

        try:
            import soundfile as sf

            audio, sr = sf.read(path, dtype="float32", always_2d=False)
            if audio.ndim > 1:
                audio = audio[:, 0]
            if sr != SAMPLE_RATE:
                import librosa

                audio = librosa.resample(audio, orig_sr=sr, target_sr=SAMPLE_RATE)
        except Exception:
            import librosa

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                audio, _ = librosa.load(path, sr=SAMPLE_RATE, mono=True)
        self.source_audio = audio.astype(np.float32) if len(audio) > 0 else None
        self._source_song = None
        self._timed_chords = None
        self.source_type = "audio"
        self._state.update(
            attached_file=path,
            compose_phase="loaded",
            status_msg=f"Loaded {os.path.basename(path)}",
        )
        self.listen_source()

    def listen_source(self) -> None:
        if self.source_audio is None:
            return
        self._state.update(compose_phase="listening", capture_enabled=False)
        if self.source_type == "audio":
            threading.Thread(
                target=self._feed_audio_to_analyzer,
                daemon=True,
                name="riff-listen-audio",
            ).start()
        else:
            threading.Thread(
                target=self._play_midi_source,
                daemon=True,
                name="riff-listen-midi",
            ).start()

    def _play_midi_source(self) -> None:
        from riff.audio.midi_feeder import MidiFeeder
        from riff.audio.song import SongPlayer

        feeder = MidiFeeder(self._state, self._source_song, audio=self.source_audio)
        player = SongPlayer(self.source_audio)
        player.start()
        try:
            start = time.time()
            while not feeder.is_finished(time.time() - start):
                if not self._state.snapshot()["running"]:
                    break
                feeder.tick(time.time() - start)
                time.sleep(0.05)
            time.sleep(0.3)
        finally:
            player.stop()
        self._finish_listening()

    def _feed_audio_to_analyzer(self) -> None:
        from riff.audio.capture import BLOCK_SIZE, SAMPLE_RATE
        from riff.audio.song import SongPlayer

        audio = self.source_audio
        q = self._state.audio_queue
        if audio is None:
            self._finish_listening()
            return
        self._state.update(capture_enabled=True)
        player = SongPlayer(audio)
        player.start()
        try:
            if q is not None:
                block_dur = BLOCK_SIZE / SAMPLE_RATE
                total_blocks = len(audio) // BLOCK_SIZE
                for i in range(total_blocks):
                    if not self._state.snapshot()["running"]:
                        break
                    block = audio[i * BLOCK_SIZE : (i + 1) * BLOCK_SIZE]
                    try:
                        q.put_nowait(block)
                    except Exception:
                        pass
                    time.sleep(block_dur)
            else:
                duration = len(audio) / SAMPLE_RATE
                self._sleep_interruptible(duration)
            self._sleep_interruptible(0.3)
        finally:
            player.stop()
        self._finish_listening()

    def _finish_listening(self) -> None:
        prev_phase = "generated" if self.generated_audio is not None else "loaded"
        self._state.update(
            note="—",
            compose_phase=prev_phase,
            capture_enabled=True,
            status_msg="Finished — [l] listen  [g] generate",
        )

    def clear(self) -> None:
        self._state.clear_chords()
        self._source_song = None
        self.source_audio = None
        self.generated_audio = None
        self._timed_chords = None
        self.source_type = ""
        self._state.update(compose_phase="", attached_file="")

    def generate(self) -> None:
        snap = self._state.snapshot()
        chords = snap["captured_chords"]
        if not chords:
            self._state.update(status_msg="No chords captured — play something first")
            return
        if snap["gen_status"] == "generating...":
            return
        threading.Thread(
            target=self._generate_and_play,
            args=(chords, snap["engine"], snap.get("bpm", 120.0)),
            daemon=True,
            name="riff-generate",
        ).start()

    def _generate_and_play(self, chords: list[str], engine: str, bpm: float) -> None:
        from riff.ai.generate import generate_song, select_progression

        self._state.update(gen_status="generating...", status_msg="Generating melody...")
        try:
            unique = select_progression(chords)
            use_bpm = int(bpm) if bpm > 0 else 120
            progression = " | ".join(unique)
            song = generate_song(progression, bars=4, bpm=use_bpm, engine=engine)
            audio = song.render_audio()
            self.generated_audio = audio if len(audio) > 0 else None
            self._state.update(
                gen_status="playing",
                gen_note_count=len(song.notes),
                gen_duration=song.total_duration,
                status_msg=f"Playing {len(song.notes)} notes ({song.total_duration:.1f}s)",
            )
            self._play_riff(song.notes, song.total_duration + 0.3)
            self._state.update(
                gen_status="done",
                compose_phase="generated",
                status_msg="Melody finished — [s] save  [p] play mix  [g] regenerate",
            )
        except Exception as exc:
            self._state.update(gen_status="", status_msg=f"Generate error: {exc}")

    def generate_from_file(self) -> None:
        if not self._timed_chords:
            return
        threading.Thread(
            target=self._do_generate_timed,
            daemon=True,
            name="riff-generate",
        ).start()

    def _do_generate_timed(self) -> None:
        from riff.ai.generate import _notes_to_midi
        from riff.ai.phrase import PhraseEngine
        from riff.audio.song import SongData

        self._state.update(gen_status="generating...", status_msg="Generating...")
        try:
            engine = PhraseEngine()
            bpm = int(self._source_song.bpm) if self._source_song else 120
            notes = engine.generate_timed(self._timed_chords, bpm=bpm)
            midi = _notes_to_midi(notes, bpm)
            song = SongData(notes=notes, bpm=bpm, _midi=midi)
            audio = song.render_audio()
            self.generated_audio = audio if len(audio) > 0 else None
            self._state.update(
                compose_phase="generated",
                gen_status="playing",
                gen_note_count=len(notes),
                gen_duration=song.total_duration,
                status_msg=f"Playing {len(notes)} notes ({song.total_duration:.1f}s)",
            )
            self._play_riff(notes, song.total_duration + 0.3)
            self._state.update(
                gen_status="done",
                status_msg=(
                    f"{len(notes)} notes — [l] listen  [s] save  [p] play mix  [g] regenerate"
                ),
            )
        except Exception as exc:
            self._state.update(gen_status="", status_msg=f"Generate error: {exc}")

    def save(self) -> None:
        if self.generated_audio is None:
            self._state.update(status_msg="No audio to save — generate first")
            return
        from riff.audio.mix import mix_audio, save_wav

        if self.source_audio is not None:
            audio = mix_audio(self.source_audio, self.generated_audio)
        else:
            audio = self.generated_audio
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self._save_dir, f"riff_{timestamp}.wav")
        try:
            save_wav(audio, path)
            self._state.update(status_msg=f"Saved → {os.path.basename(path)}")
        except Exception as exc:
            self._state.update(status_msg=f"Save error: {exc}")

    def play_mix(self) -> None:
        if self.source_audio is None or self.generated_audio is None:
            self._state.update(status_msg="No audio to mix — load a file and generate first")
            return
        from riff.audio.mix import mix_audio

        mixed = mix_audio(self.source_audio, self.generated_audio)
        self._state.update(status_msg="Playing mix...")
        threading.Thread(
            target=self._play_mixed,
            args=(mixed,),
            daemon=True,
            name="riff-play-mix",
        ).start()

    def _play_mixed(self, audio) -> None:
        from riff.audio.song import SAMPLE_RATE, SongPlayer

        duration = len(audio) / SAMPLE_RATE
        player = SongPlayer(audio)
        player.start()
        try:
            self._sleep_interruptible(duration + 0.3)
        finally:
            player.stop()
        self._state.update(status_msg="Mix playback finished")

    def _play_riff(self, notes, duration: float) -> None:
        if self._riff_player_factory:
            player = self._riff_player_factory(notes, duration)
            try:
                player.start()
            finally:
                player.stop()

    def _sleep_interruptible(self, seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end:
            if not self._state.snapshot()["running"]:
                return
            time.sleep(min(0.1, end - time.time()))
