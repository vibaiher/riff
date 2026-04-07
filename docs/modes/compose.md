# Compose mode

Compose is Riff's creative mode. It listens to you play — live or from an audio recording you load — stores what it hears, and when you're ready, it composes something back.

---

## How it works

When you enter Compose, Riff starts listening. It detects and internally stores the notes it hears: their pitch, duration, and relationship to each other. You don't see this process. You just play.

You can feed Compose in two ways:

- **Play live** — pick up the guitar and play directly into the microphone
- **Load a recording** — provide an audio file of something you've already played

Both inputs go through the same pipeline. Riff doesn't distinguish between them once the notes are stored.

When you press `G`, Riff analyzes everything it has accumulated and composes a melody that musically accompanies what you gave it. It respects your key, your rhythm, your character. It is built from your material — not a generic backing track, not a pre-recorded loop.

The result plays back immediately with electric guitar sound. You can listen to it, repeat it, play over it, or clear the session and start fresh with something new.

---

## What "compose" means here

Riff doesn't generate a full arrangement. It composes a melodic response — something that makes musical sense alongside what you played. Think of it as a conversation: you say something, Riff says something back.

The result is sometimes predictable, sometimes surprising. There is no correct output. The point is the response itself — a musical reaction to what came from your hands.

---

## Session memory

Compose accumulates notes across everything you play in a session until you clear it or exit. If you play several fragments in sequence, Riff composes from all of them combined. If you want it to respond only to the last thing you played, clear the session first and play again.

Session data is not persisted between Compose sessions. When you exit, the accumulated notes are gone.