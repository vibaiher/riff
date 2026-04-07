# ADR-003: The turn principle — listen and play never overlap

## Decision

Riff never reproduces audio while listening to the user. Every exercise has two sequential and exclusive phases: Riff plays, then the user plays. The cursor is not active during playback. Playback is not active during detection.

## Context

Riff needs to demonstrate what the user is about to play — following the Suzuki principle that the ear must internalize a sound before the hands can reproduce it. At the same time, Riff needs to detect what the user plays and validate it against the expected notes. Both of these require audio input and output, which creates a potential conflict.

## Alternatives considered

**Play simultaneously** — Riff plays alongside the user in real time, like a backing track. This is how most Rocksmith-style tools work. The problem is that Riff's audio output bleeds into the microphone input, corrupting pitch detection. It also contradicts the Suzuki principle: the user should be reproducing something they've already heard, not trying to match something playing in parallel.

**No demonstration** — skip playback entirely and rely on the tab display. This removes the auditory reference and forces the user to read before they can hear. For a beginner learning to translate tab notation into sound, this significantly slows learning.

## Rationale

The turn principle solves both problems. Riff plays the fragment completely — the user hears it, internalizes it, and only then is the microphone activated for detection. There is no audio bleed, no distraction, and no conflict between the two phases. The user always knows whose turn it is.

This also aligns with how good human teachers work: they demonstrate, they wait, and then they listen.

## Consequences

Every exercise in Learn mode follows the same two-phase structure without exception. The UI must clearly indicate which phase is active. The tempo control — which allows slowing down the demonstration — must be accessible before the user's turn begins, not during playback.

This principle applies to all audio reproduction in Learn: chord demonstrations, song fragments, generated exercises, and transition drills.