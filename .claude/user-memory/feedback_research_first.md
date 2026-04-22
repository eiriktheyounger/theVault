---
name: Research-first rule for new resources and persistent issues
description: Before building against a new external resource or when a current approach has persistent issues, research existing Python libraries and CLI tools first. Document alternatives considered.
type: feedback
originSessionId: d779d3e3-81e8-4d10-bd15-33a7d93732e7
---
# Research-first rule (added 2026-04-21)

## When to apply

Two triggers:

1. **New resource**: About to touch a macOS framework, system database, third-party API, file format, or any external integration we haven't already solved. Examples: Calendar.app, Reminders, HealthKit, a new LLM provider, a new document format.

2. **Persistent issue**: Current approach is hitting a wall that keeps recurring. Examples:
   - TCC permission denials (Calendar, Contacts, Reminders, FullDiskAccess)
   - Rate limits we keep bumping against
   - Brittle AppleScript that breaks each macOS update
   - Undocumented API that requires repeated reverse-engineering
   - Anything where we're writing "workaround" code more than once

## What to do

Before writing code, search for:

- **PyPI**: `pip search` is dead but https://pypi.org has a working search
- **GitHub**: search for topic + "awesome" lists, filter by `stars:>100` and `pushed:>2025`
- **Recent blog posts** (< 12 months): real-world usage reports
- **Stack Overflow / HN**: "best way to X in 2026"

Compare candidates on:
- **Actively maintained** (commit in last 12 months)
- **Avoids the pain point** (e.g. reads DB directly instead of going through TCC-gated API)
- **Structured output** (JSON/CSV > stringly-typed text)
- **License-compatible** (MIT/Apache/BSD > GPL for our use)
- **Dependency footprint** (pure Python > requires Ruby/Go/node sidecar, unless the non-Python option is dramatically better)

## What to record

Add a `## Libraries evaluated` heading to the relevant project memory file with:

| Library | Lang | Last updated | Solves our issue? | Tradeoffs | Decision |
|---------|------|--------------|-------------------|-----------|----------|

Future sessions look here before re-researching. Document the decision even when you chose to stick with the current approach — negative results save time too.

## Why this exists (2026-04-21 precedent)

Calendar extraction: we've been running on PyObjC EventKit bindings. When manual runs from bash hit TCC permission walls, the default reaction was to add workarounds and assume cron would have permission. Better approach: research alternatives. Ruby's `icalPal` reads the Calendar.app sqlite DB directly, bypassing TCC entirely. Worth evaluating as a fallback path instead of accepting the permission wall as a constraint.

## Anti-patterns to avoid

- "I'll just write a quick AppleScript wrapper" — usually becomes a maintenance burden
- "The docs say we need permission X, let me try to grant it" — sometimes the tool you need just doesn't need permission X
- "This library hasn't been updated since 2022, but it should still work" — it usually doesn't, on modern macOS
- "Let me just parse the CLI text output with regex" — if the tool has JSON output, use it
