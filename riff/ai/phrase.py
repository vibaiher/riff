from __future__ import annotations

import random

from riff.audio.chords import _CHORD_RE, _ENHARMONIC, _SUFFIX_MAP, CHROMATIC, Chord
from riff.audio.song import SongNote

_MIN_OCTAVE = 3
_MAX_OCTAVE = 5

_RHYTHM_PATTERNS = [
    [(0.0, 2.0)],
    [(0.0, 1.5), (1.5, 0.5)],
    [(0.0, 1.0), (1.0, 1.0)],
    [(0.0, 1.0), (1.0, 0.5), (1.5, 0.5)],
    [(0.0, 0.5), (0.5, 1.5)],
    [(0.0, 1.0)],
]

_REST_PROBABILITY = 0.10


def _canonical(note: str) -> str:
    return _ENHARMONIC.get(note, note)


def _chromatic_index(note: str) -> int:
    return CHROMATIC.index(_canonical(note))


def _pick_chord_tone(chord: Chord) -> str:
    return random.choice(chord.notes)


def _pick_scale_tone(chord: Chord, prev_note: str | None) -> str:
    scale = chord.scale_notes
    if prev_note is None:
        return random.choice(scale)
    prev_idx = _chromatic_index(prev_note)
    weights = []
    for n in scale:
        dist = abs(_chromatic_index(n) - prev_idx)
        dist = min(dist, 12 - dist)
        weights.append(10.0 / (1.0 + dist))
    return random.choices(scale, weights=weights, k=1)[0]


def _pick_octave(prev_octave: int | None, note: str, prev_note: str | None) -> int:
    if prev_octave is None:
        return 4
    prev_midi = _chromatic_index(prev_note or "C") + 12 * (prev_octave + 1)
    best_oct = prev_octave
    best_dist = 999
    for oct in range(_MIN_OCTAVE, _MAX_OCTAVE + 1):
        midi = _chromatic_index(note) + 12 * (oct + 1)
        dist = abs(midi - prev_midi)
        if dist < best_dist:
            best_dist = dist
            best_oct = oct
    return best_oct


def _generate_motif(chord: Chord, length: int, prev_note: str | None) -> list[str]:
    motif = []
    note = prev_note
    for i in range(length):
        if i == 0:
            note = _pick_chord_tone(chord)
        else:
            note = _pick_scale_tone(chord, note)
        motif.append(note)
    return motif


def _vary_motif(motif: list[str], chord: Chord) -> list[str]:
    varied = list(motif)
    if len(varied) >= 2:
        idx = random.randint(1, len(varied) - 1)
        varied[idx] = _pick_scale_tone(chord, varied[idx - 1])
    varied[0] = _pick_chord_tone(chord)
    return varied


class PhraseEngine:
    name = "phrase"

    def generate(self, chords: list[Chord], bars: int = 4, bpm: int = 120) -> list[SongNote]:
        beat_dur = 60.0 / bpm
        beats_per_chord = bars

        rhythm = random.choice(_RHYTHM_PATTERNS)

        notes: list[SongNote] = []
        prev_note: str | None = None
        prev_octave: int | None = None
        motif: list[str] | None = None
        time = 0.0

        for chord_idx, chord in enumerate(chords):
            chord_end = time + beats_per_chord * beat_dur

            if chord_idx % 4 in (0, 2):
                motif = _generate_motif(chord, length=min(bars, 4), prev_note=prev_note)
            else:
                motif = _vary_motif(motif, chord)

            motif_idx = 0
            beat_time = time
            is_first_beat = True
            while beat_time < chord_end - 0.001:
                if not is_first_beat and random.random() < _REST_PROBABILITY:
                    beat_time += beat_dur
                    continue

                if is_first_beat:
                    strum_dur = beat_dur * 2
                    strum_dur = min(strum_dur, chord_end - beat_time)
                    octave = _pick_octave(prev_octave, chord.root, prev_note)
                    for chord_note in chord.notes:
                        notes.append(
                            SongNote(
                                note=chord_note,
                                octave=octave,
                                start=round(beat_time, 4),
                                duration=round(strum_dur, 4),
                            )
                        )
                    prev_note = chord.root
                    prev_octave = octave
                else:
                    for offset_frac, dur_frac in rhythm:
                        note_start = beat_time + offset_frac * beat_dur
                        note_dur = dur_frac * beat_dur
                        if note_start >= chord_end - 0.001:
                            break
                        note_dur = min(note_dur, chord_end - note_start)

                        if motif and motif_idx < len(motif):
                            note_name = motif[motif_idx]
                        else:
                            note_name = _pick_scale_tone(chord, prev_note)

                        octave = _pick_octave(prev_octave, note_name, prev_note)

                        notes.append(
                            SongNote(
                                note=note_name,
                                octave=octave,
                                start=round(note_start, 4),
                                duration=round(note_dur, 4),
                            )
                        )

                        prev_note = note_name
                        prev_octave = octave
                        motif_idx += 1

                beat_time += beat_dur
                is_first_beat = False

            time = chord_end

        notes.sort(key=lambda n: n.start)
        return notes

    def generate_timed(self, timed_chords: list, bpm: int = 120) -> list[SongNote]:

        beat_dur = 60.0 / bpm
        rhythm = random.choice(_RHYTHM_PATTERNS)

        notes: list[SongNote] = []
        prev_note: str | None = None
        prev_octave: int | None = None
        motif: list[str] | None = None

        for chord_idx, tc in enumerate(timed_chords):
            chord = _parse_chord_str(tc.chord)
            if chord is None:
                continue

            chord_start = tc.start
            chord_end = tc.start + tc.duration
            motif_len = max(1, min(4, int(tc.duration / beat_dur)))

            if chord_idx % 4 in (0, 2):
                motif = _generate_motif(chord, length=motif_len, prev_note=prev_note)
            else:
                motif = _vary_motif(motif, chord)

            motif_idx = 0
            beat_time = chord_start
            is_first_beat = True
            while beat_time < chord_end - 0.001:
                if not is_first_beat and random.random() < _REST_PROBABILITY:
                    beat_time += beat_dur
                    continue

                for offset_frac, dur_frac in rhythm:
                    note_start = beat_time + offset_frac * beat_dur
                    note_dur = dur_frac * beat_dur
                    if note_start >= chord_end - 0.001:
                        break
                    note_dur = min(note_dur, chord_end - note_start)

                    if is_first_beat and motif_idx == 0:
                        note_name = _pick_chord_tone(chord)
                    elif motif and motif_idx < len(motif):
                        note_name = motif[motif_idx]
                    else:
                        note_name = _pick_scale_tone(chord, prev_note)

                    octave = _pick_octave(prev_octave, note_name, prev_note)

                    notes.append(
                        SongNote(
                            note=note_name,
                            octave=octave,
                            start=round(note_start, 4),
                            duration=round(note_dur, 4),
                        )
                    )

                    prev_note = note_name
                    prev_octave = octave
                    motif_idx += 1

                beat_time += beat_dur
                is_first_beat = False

        notes.sort(key=lambda n: n.start)
        return notes


def _parse_chord_str(text: str) -> Chord | None:
    m = _CHORD_RE.match(text)
    if not m:
        return None
    root, suffix = m.group(1), m.group(2)
    quality = _SUFFIX_MAP[suffix]
    return Chord(root=root, quality=quality)
