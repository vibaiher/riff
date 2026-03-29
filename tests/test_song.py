"""Tests for MIDI/song parsing into common note representation."""

import tempfile

import numpy as np
import pretty_midi
import pytest

from riff.audio.song import SongData
from riff.core.state import AppState


def _write_midi(midi: pretty_midi.PrettyMIDI) -> str:
    path = tempfile.mktemp(suffix=".mid")
    midi.write(path)
    return path


class TestMidiParsing:
    def test_empty_midi_returns_empty_note_list(self):
        midi = pretty_midi.PrettyMIDI()
        path = _write_midi(midi)

        song = SongData.from_file(path)

        assert song.notes == []

    def test_one_note_returns_correct_pitch(self):
        midi = pretty_midi.PrettyMIDI()
        inst = pretty_midi.Instrument(program=0)
        inst.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=0.0, end=1.0))
        midi.instruments.append(inst)
        path = _write_midi(midi)

        song = SongData.from_file(path)

        assert len(song.notes) == 1
        assert song.notes[0].note == "C"

    def test_one_note_returns_correct_octave(self):
        midi = pretty_midi.PrettyMIDI()
        inst = pretty_midi.Instrument(program=0)
        inst.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=0.0, end=1.0))
        midi.instruments.append(inst)
        path = _write_midi(midi)

        song = SongData.from_file(path)

        assert song.notes[0].octave == 4

    def test_one_note_returns_correct_start_time(self):
        midi = pretty_midi.PrettyMIDI()
        inst = pretty_midi.Instrument(program=0)
        inst.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=0.5, end=1.5))
        midi.instruments.append(inst)
        path = _write_midi(midi)

        song = SongData.from_file(path)

        assert song.notes[0].start == pytest.approx(0.5, abs=0.01)

    def test_one_note_returns_correct_duration(self):
        midi = pretty_midi.PrettyMIDI()
        inst = pretty_midi.Instrument(program=0)
        inst.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=0.5, end=1.5))
        midi.instruments.append(inst)
        path = _write_midi(midi)

        song = SongData.from_file(path)

        assert song.notes[0].duration == pytest.approx(1.0, abs=0.01)

    def test_multiple_notes_sorted_by_time(self):
        midi = pretty_midi.PrettyMIDI()
        inst1 = pretty_midi.Instrument(program=0)
        inst1.notes.append(pretty_midi.Note(velocity=100, pitch=64, start=1.0, end=2.0))
        inst2 = pretty_midi.Instrument(program=25)
        inst2.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=0.0, end=0.5))
        inst2.notes.append(pretty_midi.Note(velocity=100, pitch=67, start=2.0, end=3.0))
        midi.instruments.append(inst1)
        midi.instruments.append(inst2)
        path = _write_midi(midi)

        song = SongData.from_file(path)

        assert len(song.notes) == 3
        assert [n.note for n in song.notes] == ["C", "E", "G"]
        assert song.notes[0].start < song.notes[1].start < song.notes[2].start

    def test_extracts_tempo(self):
        midi = pretty_midi.PrettyMIDI(initial_tempo=140.0)
        path = _write_midi(midi)

        song = SongData.from_file(path)

        assert song.bpm == pytest.approx(140.0, abs=0.1)

    def test_default_tempo_is_120(self):
        midi = pretty_midi.PrettyMIDI()
        path = _write_midi(midi)

        song = SongData.from_file(path)

        assert song.bpm == pytest.approx(120.0, abs=0.1)

    def test_drum_tracks_are_excluded(self):
        midi = pretty_midi.PrettyMIDI()
        drums = pretty_midi.Instrument(program=0, is_drum=True)
        drums.notes.append(pretty_midi.Note(velocity=100, pitch=36, start=0.0, end=0.5))
        melody = pretty_midi.Instrument(program=0)
        melody.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=0.0, end=1.0))
        midi.instruments.append(drums)
        midi.instruments.append(melody)
        path = _write_midi(midi)

        song = SongData.from_file(path)

        assert len(song.notes) == 1
        assert song.notes[0].note == "C"

    def test_total_duration(self):
        midi = pretty_midi.PrettyMIDI()
        inst = pretty_midi.Instrument(program=0)
        inst.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=0.0, end=1.0))
        inst.notes.append(pretty_midi.Note(velocity=100, pitch=64, start=1.0, end=3.5))
        midi.instruments.append(inst)
        path = _write_midi(midi)

        song = SongData.from_file(path)

        assert song.total_duration == pytest.approx(3.5, abs=0.01)

    def test_total_duration_empty_midi(self):
        midi = pretty_midi.PrettyMIDI()
        path = _write_midi(midi)

        song = SongData.from_file(path)

        assert song.total_duration == 0.0

    def test_midi_extension_also_works(self):
        midi = pretty_midi.PrettyMIDI()
        inst = pretty_midi.Instrument(program=0)
        inst.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=0.0, end=1.0))
        midi.instruments.append(inst)
        path = tempfile.mktemp(suffix=".midi")
        midi.write(path)

        song = SongData.from_file(path)

        assert len(song.notes) == 1


class TestSongDataQuery:
    def _make_song(self, notes_data: list[tuple]) -> SongData:
        from riff.audio.song import SongNote

        notes = [SongNote(note=n, octave=o, start=s, duration=d) for n, o, s, d in notes_data]
        return SongData(notes=notes)

    def test_notes_at_empty_when_no_notes_playing(self):
        song = self._make_song([("C", 4, 0.0, 1.0)])

        result = song.notes_at(2.0)

        assert result == []

    def test_notes_at_returns_playing_note(self):
        song = self._make_song([("E", 4, 1.0, 2.0)])

        result = song.notes_at(1.5)

        assert len(result) == 1
        assert result[0].note == "E"

    def test_notes_at_excludes_ended_note(self):
        song = self._make_song([("C", 4, 0.0, 1.0)])

        result = song.notes_at(1.0)

        assert result == []

    def test_notes_at_returns_overlapping_notes(self):
        song = self._make_song(
            [
                ("C", 4, 0.0, 2.0),
                ("E", 4, 0.5, 2.0),
                ("G", 4, 3.0, 1.0),
            ]
        )

        result = song.notes_at(1.0)

        assert len(result) == 2
        assert {n.note for n in result} == {"C", "E"}

    def test_notes_between_returns_notes_in_range(self):
        song = self._make_song(
            [
                ("C", 4, 0.0, 1.0),
                ("D", 4, 1.0, 1.0),
                ("E", 4, 2.0, 1.0),
                ("F", 4, 3.0, 1.0),
            ]
        )

        result = song.notes_between(1.0, 3.0)

        assert [n.note for n in result] == ["D", "E"]

    def test_notes_between_excludes_outside_range(self):
        song = self._make_song(
            [
                ("C", 4, 0.0, 1.0),
                ("G", 4, 5.0, 1.0),
            ]
        )

        result = song.notes_between(1.0, 4.0)

        assert result == []

    def test_note_at_or_before_returns_most_recent(self):
        song = self._make_song(
            [
                ("C", 4, 0.0, 0.5),
                ("D", 4, 1.0, 0.5),
                ("E", 4, 2.0, 0.5),
            ]
        )

        result = song.note_at_or_before(1.8)

        assert result is not None
        assert result.note == "D"

    def test_note_at_or_before_returns_none_when_too_early(self):
        song = self._make_song([("C", 4, 5.0, 1.0)])

        result = song.note_at_or_before(2.0)

        assert result is None


class TestSongTracker:
    def _make_song(self, notes_data: list[tuple], bpm: float = 120.0) -> SongData:
        from riff.audio.song import SongNote

        notes = [SongNote(note=n, octave=o, start=s, duration=d) for n, o, s, d in notes_data]
        return SongData(notes=notes, bpm=bpm)

    def test_position_is_zero_before_start(self):
        from riff.audio.song import SongTracker

        song = self._make_song([("C", 4, 0.0, 1.0)])
        tracker = SongTracker(song)

        assert tracker.position == 0.0

    def test_position_advances_after_start(self):
        from riff.audio.song import SongTracker

        song = self._make_song([("C", 4, 0.0, 1.0)])
        now = [0.0]
        tracker = SongTracker(song, clock=lambda: now[0])

        tracker.start()
        now[0] = 2.5

        assert tracker.position == pytest.approx(2.5)

    def test_current_notes_returns_playing_notes(self):
        from riff.audio.song import SongTracker

        song = self._make_song(
            [
                ("C", 4, 0.0, 2.0),
                ("E", 4, 1.0, 2.0),
                ("G", 4, 4.0, 1.0),
            ]
        )
        now = [0.0]
        tracker = SongTracker(song, clock=lambda: now[0])
        tracker.start()
        now[0] = 1.5

        result = tracker.current_notes

        assert len(result) == 2
        assert {n.note for n in result} == {"C", "E"}

    def test_upcoming_notes_returns_future_notes(self):
        from riff.audio.song import SongTracker

        song = self._make_song(
            [
                ("C", 4, 0.0, 1.0),
                ("D", 4, 1.0, 1.0),
                ("E", 4, 2.0, 1.0),
                ("F", 4, 3.0, 1.0),
                ("G", 4, 4.0, 1.0),
            ]
        )
        now = [0.0]
        tracker = SongTracker(song, clock=lambda: now[0])
        tracker.start()
        now[0] = 1.5

        result = tracker.upcoming_notes(3)

        assert [n.note for n in result] == ["E", "F", "G"]

    def test_is_finished_true_after_song_ends(self):
        from riff.audio.song import SongTracker

        song = self._make_song([("C", 4, 0.0, 1.0)])
        now = [0.0]
        tracker = SongTracker(song, clock=lambda: now[0])
        tracker.start()
        now[0] = 2.0

        assert tracker.is_finished is True

    def test_is_finished_false_during_playback(self):
        from riff.audio.song import SongTracker

        song = self._make_song([("C", 4, 0.0, 5.0)])
        now = [0.0]
        tracker = SongTracker(song, clock=lambda: now[0])
        tracker.start()
        now[0] = 2.0

        assert tracker.is_finished is False

    def test_position_freezes_after_pause(self):
        from riff.audio.song import SongTracker

        song = self._make_song([("C", 4, 0.0, 5.0)])
        now = [0.0]
        tracker = SongTracker(song, clock=lambda: now[0])
        tracker.start()
        now[0] = 2.0
        tracker.pause()
        now[0] = 5.0

        assert tracker.position == pytest.approx(2.0)

    def test_position_resumes_from_pause_point(self):
        from riff.audio.song import SongTracker

        song = self._make_song([("C", 4, 0.0, 10.0)])
        now = [0.0]
        tracker = SongTracker(song, clock=lambda: now[0])
        tracker.start()
        now[0] = 2.0
        tracker.pause()
        now[0] = 5.0
        tracker.resume()
        now[0] = 6.0

        assert tracker.position == pytest.approx(3.0)

    def test_pause_twice_is_idempotent(self):
        from riff.audio.song import SongTracker

        song = self._make_song([("C", 4, 0.0, 10.0)])
        now = [0.0]
        tracker = SongTracker(song, clock=lambda: now[0])
        tracker.start()
        now[0] = 2.0
        tracker.pause()
        now[0] = 5.0
        tracker.pause()

        assert tracker.position == pytest.approx(2.0)

    def test_resume_without_pause_is_noop(self):
        from riff.audio.song import SongTracker

        song = self._make_song([("C", 4, 0.0, 10.0)])
        now = [0.0]
        tracker = SongTracker(song, clock=lambda: now[0])
        tracker.start()
        now[0] = 2.0
        tracker.resume()

        assert tracker.position == pytest.approx(2.0)

    def test_default_speed_is_1(self):
        from riff.audio.song import SongTracker

        song = self._make_song([("C", 4, 0.0, 5.0)])
        tracker = SongTracker(song)

        assert tracker.speed == 1.0

    def test_position_at_half_speed(self):
        from riff.audio.song import SongTracker

        song = self._make_song([("C", 4, 0.0, 10.0)])
        now = [0.0]
        tracker = SongTracker(song, clock=lambda: now[0])
        tracker.set_speed(0.5)
        tracker.start()
        now[0] = 4.0

        assert tracker.position == pytest.approx(2.0)

    def test_position_at_double_speed(self):
        from riff.audio.song import SongTracker

        song = self._make_song([("C", 4, 0.0, 10.0)])
        now = [0.0]
        tracker = SongTracker(song, clock=lambda: now[0])
        tracker.set_speed(2.0)
        tracker.start()
        now[0] = 3.0

        assert tracker.position == pytest.approx(6.0)

    def test_speed_change_mid_playback_preserves_position(self):
        from riff.audio.song import SongTracker

        song = self._make_song([("C", 4, 0.0, 20.0)])
        now = [0.0]
        tracker = SongTracker(song, clock=lambda: now[0])
        tracker.start()
        now[0] = 4.0
        pos_before = tracker.position
        tracker.set_speed(0.5)
        now[0] = 6.0

        assert pos_before == pytest.approx(4.0)
        assert tracker.position == pytest.approx(5.0)

    def test_is_paused_property(self):
        from riff.audio.song import SongTracker

        song = self._make_song([("C", 4, 0.0, 5.0)])
        now = [0.0]
        tracker = SongTracker(song, clock=lambda: now[0])
        tracker.start()

        assert tracker.is_paused is False
        tracker.pause()
        assert tracker.is_paused is True
        tracker.resume()
        assert tracker.is_paused is False


class TestSongState:
    def test_song_note_in_snapshot(self):
        state = AppState()
        state.update(song_note="E", song_octave=4)

        snap = state.snapshot()

        assert snap["song_note"] == "E"
        assert snap["song_octave"] == 4

    def test_song_position_in_snapshot(self):
        state = AppState()
        state.update(song_position=12.5)

        assert state.snapshot()["song_position"] == 12.5

    def test_song_bpm_in_snapshot(self):
        state = AppState()
        state.update(song_bpm=140.0)

        assert state.snapshot()["song_bpm"] == 140.0

    def test_song_upcoming_in_snapshot(self):
        state = AppState()
        state.update(song_upcoming=["D4", "E4", "F4"])

        assert state.snapshot()["song_upcoming"] == ["D4", "E4", "F4"]

    def test_song_finished_in_snapshot(self):
        state = AppState()
        state.update(song_finished=True)

        assert state.snapshot()["song_finished"] is True

    def test_song_waveform_in_snapshot(self):
        state = AppState()
        state.update(song_waveform=[0.1, 0.5, 0.3])

        assert state.snapshot()["song_waveform"] == [0.1, 0.5, 0.3]

    def test_song_db_in_snapshot(self):
        state = AppState()
        state.update(song_db=-30.0)

        assert state.snapshot()["song_db"] == -30.0


class TestSongUpdater:
    def _make_song(self, notes_data: list[tuple], bpm: float = 120.0) -> SongData:
        from riff.audio.song import SongNote

        notes = [SongNote(note=n, octave=o, start=s, duration=d) for n, o, s, d in notes_data]
        return SongData(notes=notes, bpm=bpm)

    def test_writes_song_note_to_state(self):
        from riff.audio.song import SongTracker, SongUpdater

        song = self._make_song([("E", 4, 0.0, 2.0)], bpm=100.0)
        now = [0.0]
        tracker = SongTracker(song, clock=lambda: now[0])
        state = AppState()

        tracker.start()
        now[0] = 0.5
        updater = SongUpdater(state, tracker)
        updater.tick()

        snap = state.snapshot()
        assert snap["song_note"] == "E"
        assert snap["song_octave"] == 4

    def test_writes_song_upcoming_to_state(self):
        from riff.audio.song import SongTracker, SongUpdater

        song = self._make_song(
            [
                ("C", 4, 0.0, 1.0),
                ("D", 4, 1.0, 1.0),
                ("E", 4, 2.0, 1.0),
            ]
        )
        now = [0.0]
        tracker = SongTracker(song, clock=lambda: now[0])
        state = AppState()

        tracker.start()
        now[0] = 0.5
        updater = SongUpdater(state, tracker)
        updater.tick()

        snap = state.snapshot()
        assert snap["song_upcoming"] == ["D4", "E4"]

    def test_writes_song_finished_when_done(self):
        from riff.audio.song import SongTracker, SongUpdater

        song = self._make_song([("C", 4, 0.0, 1.0)])
        now = [0.0]
        tracker = SongTracker(song, clock=lambda: now[0])
        state = AppState()

        tracker.start()
        now[0] = 5.0
        updater = SongUpdater(state, tracker)
        updater.tick()

        assert state.snapshot()["song_finished"] is True

    def test_writes_song_bpm(self):
        from riff.audio.song import SongTracker, SongUpdater

        song = self._make_song([("C", 4, 0.0, 1.0)], bpm=95.0)
        now = [0.0]
        tracker = SongTracker(song, clock=lambda: now[0])
        state = AppState()

        tracker.start()
        updater = SongUpdater(state, tracker)
        updater.tick()

        assert state.snapshot()["song_bpm"] == pytest.approx(95.0)

    def test_waveform_from_audio_at_loud_position(self):
        from riff.audio.song import SongTracker, SongUpdater

        song = self._make_song([("A", 4, 0.0, 2.0)])
        now = [0.0]
        tracker = SongTracker(song, clock=lambda: now[0])
        state = AppState()
        audio = np.concatenate(
            [
                np.sin(np.linspace(0, 100, 44100)).astype(np.float32),
                np.zeros(44100, dtype=np.float32),
            ]
        )

        tracker.start()
        now[0] = 0.5
        updater = SongUpdater(state, tracker, audio=audio)
        updater.tick()

        wf = state.snapshot()["song_waveform"]
        assert len(wf) == 48
        assert any(v > 0 for v in wf)

    def test_waveform_silent_in_silent_section(self):
        from riff.audio.song import SongTracker, SongUpdater

        song = self._make_song([("A", 4, 0.0, 1.0)])
        now = [0.0]
        tracker = SongTracker(song, clock=lambda: now[0])
        state = AppState()
        audio = np.concatenate(
            [
                np.zeros(44100, dtype=np.float32),
                np.sin(np.linspace(0, 100, 44100)).astype(np.float32),
            ]
        )

        tracker.start()
        now[0] = 0.5
        updater = SongUpdater(state, tracker, audio=audio)
        updater.tick()

        wf = state.snapshot()["song_waveform"]
        assert all(v == 0.0 for v in wf)

    def test_db_loud_in_loud_section(self):
        from riff.audio.song import SongTracker, SongUpdater

        song = self._make_song([("A", 4, 0.0, 2.0)])
        now = [0.0]
        tracker = SongTracker(song, clock=lambda: now[0])
        state = AppState()
        audio = np.sin(np.linspace(0, 100, 88200)).astype(np.float32)

        tracker.start()
        now[0] = 0.5
        updater = SongUpdater(state, tracker, audio=audio)
        updater.tick()

        assert state.snapshot()["song_db"] > -10.0

    def test_db_silent_in_silent_section(self):
        from riff.audio.song import SongTracker, SongUpdater

        song = self._make_song([("A", 4, 5.0, 1.0)])
        now = [0.0]
        tracker = SongTracker(song, clock=lambda: now[0])
        state = AppState()
        audio = np.zeros(88200, dtype=np.float32)

        tracker.start()
        now[0] = 0.5
        updater = SongUpdater(state, tracker, audio=audio)
        updater.tick()

        assert state.snapshot()["song_db"] <= -80.0

    def test_waveform_silence_without_audio(self):
        from riff.audio.song import SongTracker, SongUpdater

        song = self._make_song([("A", 4, 0.0, 2.0)])
        now = [0.0]
        tracker = SongTracker(song, clock=lambda: now[0])
        state = AppState()

        tracker.start()
        now[0] = 0.5
        updater = SongUpdater(state, tracker)
        updater.tick()

        wf = state.snapshot()["song_waveform"]
        assert all(v == 0.0 for v in wf)
        assert state.snapshot()["song_db"] <= -80.0


class TestRenderAudio:
    def test_render_audio_returns_numpy_array(self):
        midi = pretty_midi.PrettyMIDI()
        inst = pretty_midi.Instrument(program=0)
        inst.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=0.0, end=1.0))
        midi.instruments.append(inst)
        path = _write_midi(midi)
        song = SongData.from_file(path)

        audio = song.render_audio()

        assert isinstance(audio, np.ndarray)

    def test_render_audio_non_empty_for_notes(self):
        midi = pretty_midi.PrettyMIDI()
        inst = pretty_midi.Instrument(program=0)
        inst.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=0.0, end=1.0))
        midi.instruments.append(inst)
        path = _write_midi(midi)
        song = SongData.from_file(path)

        audio = song.render_audio()

        assert len(audio) > 0

    def test_render_audio_empty_for_no_notes(self):
        midi = pretty_midi.PrettyMIDI()
        path = _write_midi(midi)
        song = SongData.from_file(path)

        audio = song.render_audio()

        assert len(audio) == 0

    def test_render_audio_length_matches_duration(self):
        midi = pretty_midi.PrettyMIDI()
        inst = pretty_midi.Instrument(program=0)
        inst.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=0.0, end=2.0))
        midi.instruments.append(inst)
        path = _write_midi(midi)
        song = SongData.from_file(path)

        audio = song.render_audio()

        expected_min = int(2.0 * 44100)
        assert len(audio) >= expected_min


class TestSongPlayer:
    def test_stores_rendered_audio(self):
        from riff.audio.song import SongPlayer

        audio = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        player = SongPlayer(audio)

        assert len(player.audio) == 3

    def test_stop_does_not_raise_when_not_started(self):
        from riff.audio.song import SongPlayer

        audio = np.array([0.1], dtype=np.float32)
        player = SongPlayer(audio)

        player.stop()

    def test_empty_audio_does_not_raise_on_start(self):
        from riff.audio.song import SongPlayer

        audio = np.array([], dtype=np.float32)
        player = SongPlayer(audio)

        player.start()

    def test_pause_without_start_does_not_raise(self):
        from riff.audio.song import SongPlayer

        audio = np.array([0.1], dtype=np.float32)
        player = SongPlayer(audio)

        player.pause()

    def test_resume_without_start_does_not_raise(self):
        from riff.audio.song import SongPlayer

        audio = np.array([], dtype=np.float32)
        player = SongPlayer(audio)

        player.resume(position=1.0)


class TestValidation:
    def test_unsupported_extension_raises_valueerror(self):
        path = tempfile.mktemp(suffix=".txt")
        with open(path, "w") as f:
            f.write("not music")

        with pytest.raises(ValueError, match="Unsupported"):
            SongData.from_file(path)
