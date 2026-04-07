# ADR-001: SQLite for local persistence

## Decision

All session data, the learning plan, user profile, and spaced repetition state are stored locally in SQLite at `~/.riff/riff.db`.

## Context

Riff is a single-user local application. It needs to persist session history, track progress over time, and support queries across sessions — for example, when calculating spaced repetition intervals or generating a personalized briefing.

## Alternatives considered

**JSON flat files** — simple to implement, but querying across multiple sessions becomes fragile quickly. Sorting, filtering, and aggregating data requires loading everything into memory.

**No persistence** — not viable. The living plan, spaced repetition, and the personal style engine all depend on accumulated history across sessions.

**Remote database** — adds infrastructure, requires connectivity, and introduces privacy concerns. Riff is intentionally local-first.

## Rationale

SQLite is the right tool for a local, single-user application with relational data. It supports complex queries, handles concurrent writes safely, requires no server, and produces a single portable file. The schema starts minimal and evolves as features demand — there is no pressure to design it completely upfront.

## Consequences

Session data, plan state, spaced repetition intervals, style profile, and recording metadata all live in `~/.riff/riff.db`. Configuration lives separately in `~/.riff/config.toml`. Audio recordings live in `~/.riff/recordings/`.