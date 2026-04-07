# Learn mode

Learn is the pedagogical core of Riff. It is built around a living learning plan organized around real songs you choose, with deliberate practice sessions leading up to each one.

For the full pedagogical framework behind Learn, see [docs/product/pedagogy.md](../product/pedagogy.md).

---

## The living plan

The first time you enter Learn, Riff asks what you want to achieve. It generates a selection of songs suited to your level and plays a short fragment of each so you can decide with your ears. From your selection it builds a plan: songs ordered as transfer tasks, with deliberate practice sessions between them, calibrated to your available time.

On subsequent visits, today's session is already prepared. No decisions required.

You can adjust the plan at any time by telling Riff in natural language what changed. It regenerates everything while preserving your history and accumulated progress.

The plan is stored in SQLite and treated as a first-class entity — not a static document but a living structure that evolves with your progress.

---

## Session structure

Every Learn session follows the same structure.

**Briefing.** Riff tells you where you are in the plan, what skill today's session works on and why, and what fragment of the target song you'll play at the end. Generated from your session history — never generic, never repeated.

**Practice.** The tab is rendered measure by measure in the terminal. The current measure is always fully visible. Before you play any fragment, Riff plays it with electric guitar sound so your ear knows where it's going. Then it's your turn. The cursor advances when you hit the correct note and waits if you miss — no penalty, no time pressure.

A fixed line below the tab shows relevant theoretical context in real time, rotating between: what scale this riff uses, what chord is underneath, and why this note works here.

**Transfer fragment.** Every session ends by playing a fragment of the target song. The destination is always visible.

**Post-session summary.** Appears automatically when the session ends, skippable with Escape. Covers what went well, what error pattern keeps appearing, the theory behind the mistake, and a concrete exercise for the next session.

---

## The turn principle

Riff never plays and listens at the same time. Every exercise has two sequential and exclusive phases: Riff plays, then you play. The cursor is not active while Riff is reproducing audio. See [docs/decisions/003-turn-principle.md](../decisions/003-turn-principle.md).

---

## Chord challenge

Accessible from the Learn menu. Riff proposes a chord, listens, and validates. If you miss it, Riff passes without blocking you but logs the chord for spaced repetition. Feedback indicates which finger is probably misplaced, inferred by crossing the detected notes against the expected chord fingering map.

---

## Chord transitions

Accessible from the Learn menu. Select two chords, set a two-minute timer, and alternate between them. A real-time ASCII graph tracks each transition: each attempt is a point, the curve drops as your transition time improves. Results are stored for spaced repetition.

---

## What runs invisibly

**Spaced repetition.** Riff tracks when you last worked on each chord, pattern, and technique. It reintroduces them silently just before you'd forget them — through the briefing and content selection. It never announces this.

**Optimal difficulty.** Riff monitors your error rate in real time. Above 40% failure it simplifies — reduces tempo or switches to monophonic. Below 15% it raises the bar — introduces a variation or increases complexity. The target zone is 20–30% failure. It never tells you it's doing this.

**Personal style engine.** Riff observes what you complete, what you abandon, and what you repeat voluntarily. It also accepts an optional 1–5 rating at the end of each session. Both signals feed the plan and the generated exercises over time.

**Silent recording.** Riff saves a representative 30-second fragment from each session without announcing it. The fragment is selected by highest note variety combined with lowest error rate. Stored in `~/.riff/recordings/`. Use Flashback to hear your before and after.

**Daily discovery.** At the end of each session, Riff presents something unexpected: a musical curiosity, a piece of rock history, or a small challenge connected to what you just played. Never repeated.

---

## Flashback

Flashback shows your progress over time in two parts: ASCII graphs of weekly accuracy, transfer tasks cleared, and chord transition times; followed by something you struggled with weeks ago, played live now so you feel the difference in your own hands.

---

## Content

Tabs are sourced automatically from Ultimate Guitar — the same process you'd follow manually. Riff searches, downloads, and prepares the tab for the session. Guitar Pro format is preferred; plain text tab is the fallback.

Tabs are converted internally to MIDI for audio reproduction. If a downloaded tab is above your current level, Riff adapts it automatically and tells you it has done so. The original is preserved.

All audio reproduction uses FluidSynth with an electric guitar soundfont. See [docs/decisions/004-fluidsynth.md](../decisions/004-fluidsynth.md).

---

## Session persistence

Riff saves session progress in real time. If you close mid-session, the next time you open Learn it detects the incomplete session and asks whether to resume or start fresh.