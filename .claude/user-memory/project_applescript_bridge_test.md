---
name: AppleScript Bridge Test Results (2026-03-31)
description: Test results for Mail.app extraction via AppleScript in email_thread_ingester. Gmail ✅, Exchange ✅ (resolved via --start-date + --limit early-exit).
type: project
---

## Test History

### Round 1 — 2026-03-31 (Haiku session)
- Gmail _VAULT_IMPORT: ✅ 4/4 messages, ~5s
- Exchange Inbox: ❌ Timeout @ 240s, 2,327 messages, root cause Mail.app iteration overhead

### Round 2 — 2026-03-31 (Sonnet CLI, condescending-mccarthy)
After adding `--start-date`, `--end-date`, `--limit` with AppleScript early-exit optimization:

**Gmail** `--start-date 2026-03-01 --end-date 2026-03-31`:
- ✅ 48 messages extracted → 29 threads, 0 errors, ~1:12 extraction

**Exchange** `--start-date 2026-03-01 --limit 200`:
- ✅ 106 messages extracted → 23 threads, 0 errors, ~1:50 total (well under 240s timeout)
- Early-exit on `start_date` stopped iteration once messages older than 2026-03-01 were hit

**Both accounts** `--start-date 2026-03-01`:
- ✅ 188 messages → 61 threads, 0 errors, ~18 min total (Ollama summarization dominant)

## Resolution

Exchange timeout **RESOLVED** via date filter + AppleScript early-exit (2026-03-31):
- `_build_exchange_script()` now injects `startDate` variable
- Mail.app returns messages newest-first → `if msgDate < startDate then exit repeat` stops at the date boundary
- `--limit N` adds a counter-based hard cap as secondary safety
- `_build_gmail_script()` and `_build_job_script()` also support date filter (no early-exit; ordering not guaranteed)

**How to apply:** Always use `--start-date` for production Exchange runs. `--start-date 2026-03-01 --limit 200` is a safe default for monthly batches.

## Data Structure Validation (Round 1)
✅ All required keys present: `message_id`, `subject`, `sender`, `recipients`, `date_received`, `in_reply_to`, `headers`, `body`, `account`

## Files Modified
- `applescript_bridge.py` — replaced static script strings with `_build_exchange_script()`, `_build_gmail_script()`, `_build_job_script()` builder functions; `_as_date_var()` helper for locale-safe AppleScript dates
- `__main__.py` — added `--start-date`, `--end-date`, `--limit` CLI args; passed through to all extraction calls
