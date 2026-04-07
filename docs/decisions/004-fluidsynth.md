# ADR-004: FluidSynth with electric guitar soundfont for audio reproduction

## Decision

All audio reproduction in Riff uses FluidSynth with an electric guitar SF2 soundfont. The existing MIDI playback infrastructure is wrapped or replaced with this stack.

## Context

Riff reproduces audio in several contexts: demonstrating a tab fragment before the user plays it, playing back generated exercises, and previewing song candidates during plan generation. The quality and character of this audio matters — it should sound like an electric guitar, not a generic synthesizer.

## Alternatives considered

**Default MIDI synthesizer** — the path of least resistance. Most systems have a default MIDI synth available, but the output sounds like a keyboard or generic instrument. For a guitar learning tool, this creates a disconnect between what the user hears and what they're trying to reproduce on their guitar.

**Pre-recorded samples per song** — high audio quality but impractical. It would require curating a sample library for every song in the catalog, with no path to generalization.

**Web Audio API or browser-based synthesis** — not applicable. Riff is a terminal application.

**Custom synthesis engine** — unnecessary complexity. FluidSynth is a mature, well-maintained, cross-platform SF2 player with Python bindings available.

## Rationale

FluidSynth with a high-quality electric guitar SF2 soundfont produces realistic guitar audio from MIDI data with minimal overhead. It integrates cleanly into a Python application, runs locally without network access, and produces output that sounds close enough to a real electric guitar for the user's ear to make the connection between what they hear and what they're trying to play.

The soundfont choice matters as much as FluidSynth itself. A realistic distorted or clean electric guitar SF2 — not a nylon string or acoustic — should be selected and bundled with the application.

## Consequences

FluidSynth becomes a system dependency. The SF2 soundfont file is bundled with Riff or downloaded on first run. All MIDI-to-audio reproduction goes through this stack consistently — there is no fallback to a system synthesizer. Audio quality is uniform across platforms.