# Forward-Back / Past 7 / Recent Context — Phase 1b SHIPPED (2026-04-20)

## What it does

ADHD/OOSOOM-first temporal context section injected into every DLY. Three
blocks, stack order fixed:

1. `## 🎯 Today — Forward-Back` — 14-day calendar lookahead, all calendars
   mixed per day and sorted by start time, calendar group as italic `_(Group)_`
   suffix.
2. `## 📅 Past 7 Days` — `- **Day MM-DD** — entry1 | entry2 | entry3 · [[WKY]]`
   (entries ≤30 chars, newest-created first, one WKY link per week spanned).
3. `## Recent Context` — last completed WKY + last completed MTH, compressed.

Each section has its own idempotent marker pair
(`<!-- forward-back-start/end -->`, `<!-- past-7-start/end -->`,
`<!-- recent-context-start/end -->`). Insertion anchors cascade so re-injection
preserves order.

## Files

- **NEW** `System/Scripts/calendar_forward_back.py` (~440 LOC) — range fetcher,
  per-calendar extraction rules, VC detection, Gemma4-local notes summarizer,
  gap detector, renderers.
- **EXTENDED** `System/Scripts/inject_recent_context.py` — now a 3-section
  injector. Public API: `run_inject(target_date, dry_run, verbose, use_gemma, sections)`.
  CLI: `--dry-run`, `--verbose`, `--date`, `--no-gemma`, `--no-forward-back`,
  `--no-past-7`, `--no-recent-context`.
- **WIRED** `System/Scripts/Workflows/morning_workflow.py` — `_step_sync_calendar`
  calls `run_inject()` immediately after `inject_calendar_for_date`.
- **WIRED** `System/Scripts/overnight_processor.py` — calls `run_inject()`
  at end of run, after `daily_vault_activity`, before monthly summary.

## Per-calendar extraction rules (Eric's spec, locked)

| Calendar | Priority | Extract | Group |
|---|---|---|---|
| eric.manchester@gmail.com | P0 | full (title/time/location/notes/attendees) | Eric Personal |
| ExchangeCalendar | P0 | full | Eric Work |
| Rachel | P1 | title+time+note | Rachel |
| Alyssa Manchester + Lulu (merged) | P1 | title+time+note | Alyssa |
| Class Schedule | P1 | 40-char truncated title + time | Alyssa Classes |
| Bella | P1 | title+time | Bella |
| Holidays in United States | — | SKIP | — |

## VC handling (locked)

- Detects Zoom / Teams / Meet / Webex / BlueJeans / GoToMeeting / Hangouts.
- Pure VC boilerplate in notes → drop + add "VC URL: True" flag.
- Real notes >200 chars → Gemma4-local one-line summary (`gemma4:e4b` via
  Ollama at localhost:11434). **Never Haiku** per Eric. Hard-truncate fallback
  when Ollama unavailable.
- Dedup: if VC name already shows in header location, suppress it in notes suffix.

## Gap detection (72h threshold, Eric-accepted)

`detect_prep_gap(event, today, dly_reader, lookback_days=14, gap_window_hours=72)`:

- Only flags P0 events within 72h.
- Extracts "distinctive terms" from event: title tokens ≥4 chars + attendee
  last names ≥3 chars.
- Filesystem grep over last 14 DLY files (no RAG server dependency).
- Zero mentions → injects inline:
  `⚠️ **Gap detected** — no prep mentions in last 14 DLYs` + today-dated
  prep task (`- [ ] Block 30 min today to prep 📅 <today>`).

Tests PASS on synthetic fixtures:
- P0/no-prep flagged ✓
- P0/with-prep not flagged ✓
- P1 never flagged ✓
- P0 outside 72h not flagged ✓

## Live verification

Eric confirmed live-fire check against EventKit passed (2026-04-20). Cron
paths (morning_workflow + overnight_processor) inherit Calendar permission
from the existing `calendar_daily_injector.py` path which has been stable for
months.

## Deferred items from Phase 1 roadmap

- **#3 Entity-anchored temporal queries** — "what's the latest on Nebius"
  scopes RAG to entity + time window. Not started.
- **#6 Supersession awareness** — newer content about same entity downranks
  older contradictory chunks. Not started.
- **Rolling Dashboard** — separate plan (`project_rolling_dashboard_2026_04_19.md`),
  unified past/present/future aggregation layer over WKY + MTH + DLY + calendar.
  Phase 1 = pure aggregation (no LLM), Phase 2 = Haiku synthesis.

## Cross-reference

- Design prototype: `Vault/System/Prototypes/today-forward-back-sample.md`
- Rolling dashboard plan: `project_rolling_dashboard_2026_04_19.md`
- Phase 1 bug fix (unblocker): `project_overnight_processor_bug_2026_04_19.md`
