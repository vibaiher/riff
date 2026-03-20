"""Magenta MelodyRNN-based melodic generator for RIFF.

Uses a pre-trained MelodyRNN bundle (e.g., attention_rnn.mag) to
generate the next note in a sequence conditionally.
"""

import os
import threading
from typing import List, Optional

import numpy as np
try:
    import note_seq
    from magenta.models.melody_rnn import melody_rnn_sequence_generator
    MAGENTA_AVAILABLE = True
except ImportError:
    MAGENTA_AVAILABLE = False


class MagentaMelodyGen:
    """Wrapper around Magenta's MelodyRnnSequenceGenerator."""

    def __init__(self, bundle_path: str = "attention_rnn.mag") -> None:
        if not MAGENTA_AVAILABLE:
            raise ImportError(
                "Magenta and note-seq must be installed to use MagentaMelodyGen. "
                "Try running: pip install magenta note-seq"
            )

        self.bundle_path = bundle_path
        self._generator = None
        self._lock = threading.Lock()
        
    def warmup(self) -> None:
        """Initialize the TensorFlow graph to avoid latency on the first note."""
        with self._lock:
            if self._generator is not None:
                return

            if not os.path.exists(self.bundle_path):
                raise FileNotFoundError(f"Magenta bundle not found: {self.bundle_path}")

            bundle = melody_rnn_sequence_generator.get_bundle()
            # Map filenames to their canonical string names
            # 'attention_rnn.mag' -> 'attention_rnn'
            bundle_name = os.path.basename(self.bundle_path).split(".")[0]
            if bundle_name not in melody_rnn_sequence_generator.get_generator_map():
                # Fallback to basic approach
                bundle_name = "attention_rnn"

            self._generator = melody_rnn_sequence_generator.get_generator_map()[
                bundle_name
            ](checkpoint=None, bundle=self.bundle_path)
            self._generator.initialize()
            
            # Run a dummy inference to build the graph
            primer = note_seq.NoteSequence()
            primer.notes.add(pitch=60, start_time=0.0, end_time=0.25, velocity=80)
            primer.total_time = 0.25
            
            # from note_seq.protobuf import generator_pb2
            import note_seq.protobuf.generator_pb2 as generator_pb2
            gen_options = generator_pb2.GeneratorOptions()
            gen_options.args['temperature'].float_value = 1.0
            gen_options.generate_sections.add(start_time=0.25, end_time=0.5)
            
            self._generator.generate(primer, gen_options)

    def generate(
        self,
        root_note: str,
        mode: str,
        history: List[str],
        user_octave: int = 4,
        last_interval: Optional[int] = None,
        chords: Optional[List[str]] = None,
    ) -> tuple[str, int, int]:
        """Generate the next note using MelodyRNN.
        
        Args:
            root_note: The latest note played by the user.
            mode: Musical mode (e.g. BLUES, ROCK). Used for temperature scaling, 
                  but MelodyRNN is mostly context-driven.
            history: List of past generated notes.
            user_octave: The user's current octave.
            last_interval: (Ignored for Magenta, required by interface).
            chords: (Not strictly enforced by basic MelodyRNN but could condition).
            
        Returns:
            (note_name, octave, interval_chosen)
        """
        # Ensure graph is ready
        if self._generator is None:
            self.warmup()

        # Build a NoteSequence primer from history + root_note
        import note_seq
        from note_seq.protobuf import generator_pb2
        import librosa

        primer = note_seq.NoteSequence()
        primer.tempos.add(qpm=120)
        
        # Add history as 8th notes
        time_cursor = 0.0
        step_dur = 0.25  # eighth note at 120 bpm is 0.25s
        
        # Combine past history + current input note as the primer context
        context_notes = history + [root_note]
        for past_note in context_notes:
            # We assume a fixed octave (e.g., 4) for the context if unprovided.
            # In a real setup, we'd record exact MIDI pitches.
            try:
                pitch = librosa.note_to_midi(f"{past_note}{user_octave}")
                primer.notes.add(
                    pitch=pitch, 
                    start_time=time_cursor, 
                    end_time=time_cursor + step_dur * 0.9, 
                    velocity=80
                )
            except Exception:
                pass
            time_cursor += step_dur
        primer.total_time = time_cursor

        # Prepare generation options (ask for 1 step duration out)
        gen_options = generator_pb2.GeneratorOptions()
        # Control 'creativity' via temperature. Mode could influence this
        temps = {"FREE": 1.2, "ROCK": 1.0, "JAZZ": 1.1, "BLUES": 0.9, "AMBIENT": 0.8}
        temp = temps.get(mode.upper(), 1.0)
        gen_options.args['temperature'].float_value = temp
        
        gen_options.generate_sections.add(
            start_time=time_cursor,
            end_time=time_cursor + step_dur
        )

        with self._lock:
            try:
                generated_seq = self._generator.generate(primer, gen_options)
            except Exception:
                # Fallback to current note if inference fails
                return root_note, user_octave, 0

        # Extract the new note from the generated sequence
        # We look for the first note that starts AT or AFTER time_cursor
        new_pitch = librosa.note_to_midi(f"{root_note}{user_octave}") # default fallback
        for note in generated_seq.notes:
            if note.start_time >= time_cursor - 0.01:
                new_pitch = note.pitch
                break

        # Convert back to symbol and octave
        new_note_str = librosa.midi_to_note(new_pitch)  # e.g., "C#4"
        
        # Basic parsing: 'C#4' -> 'C#', 4
        if len(new_note_str) > 1 and new_note_str[1] in ('#', 'b'):
            name = new_note_str[:2]
            oct_str = new_note_str[2:]
        else:
            name = new_note_str[:1]
            oct_str = new_note_str[1:]
            
        try:
            octave = int(oct_str)
        except ValueError:
            octave = user_octave
            
        return name, octave, 0
