"""Tests for MIDI/song parsing into common note representation."""

import tempfile

import numpy as np
import pretty_midi
import pytest

from riff.audio.song import SongData


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
