# ADR-002: Tabs as primary content source, MIDI as internal format

## Decision

Guitar tabs — sourced from Ultimate Guitar — are the primary content format. Tabs are converted internally to MIDI for audio reproduction. MIDI is not used as a download format.

## Context

Riff needs a way to represent songs that can be displayed in the terminal, played back as audio, and validated against what the user plays. The choice of source format affects what content is available, what information is preserved, and how the user experience feels.

## Alternatives considered

**MIDI as primary source** — widely available and structurally clean, but MIDI lacks guitar-specific information: which string a note is played on, fingering position, techniques like bends or slides. For a guitar learning tool this is a significant loss. MIDI also represents notes, not positions — two MIDI files for the same song may produce very different fingerings.

**Guitar Pro files (.gp5)** — contain rich guitar-specific data including string and fret positions, techniques, and fingering. However, parsing Guitar Pro files requires a complex binary format, and availability of free .gp5 files is more limited than plain tabs.

**Plain text tabs** — widely available, human-readable, and unambiguous about string and fret positions. Parsing is straightforward. The downside is that rhythm information is often approximate or missing entirely.

## Rationale

Tabs from Ultimate Guitar represent the same process a guitarist would follow manually — search, find, download. The content is user-contributed under fair use, widely available for rock songs, and already in the format guitarists are familiar with reading. Guitar Pro format is preferred when available because it includes rhythm data; plain text tab is the fallback.

MIDI is used internally because Riff already has MIDI playback infrastructure. Converting a tab to MIDI allows audio reproduction without building a separate synthesis pipeline. The conversion happens transparently — the user only ever sees and interacts with the tab.

## Consequences

Riff fetches tabs from Ultimate Guitar automatically as part of plan generation. The download is proactive — by the time a session starts, the tab is already available. If a tab is above the user's current level, Riff adapts it before loading. The original is preserved.

Rhythm accuracy depends on tab quality. Plain text tabs in particular may require inference. This is an accepted limitation given the availability and familiarity benefits.