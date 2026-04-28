---
name: Overnight processor — vault_activity cascade bug
description: 2026-04-19 diagnosis. Overnight_processor appeared to "never write DLY" but was actually still running. Real bug is vault_activity feedback loop + stale state cursor. Fix plan + Haiku prompt documented.
type: project
originSessionId: continued-from-d779d3e3
---

# Overnight Processor — vault_activity Cascade Bug (2026-04-19)

## Original report (incorrect diagnosis)
User thought overnight_processor.py was silently failing to write DLY files at line 212. Evidence cited: log went silent at 08:38:04, no "Daily note updated" marker, no "complete" marker.

## Actual root cause
The process is **still running**, not crashed. PID 20697 from 08:20 AM continued logging past the user's tail-read time. What's broken is a **feedback loop in `daily_vault_activity.py`** that makes each run take progressively longer.

### The cascade

1. **`days=1` is silently ignored.** In `run_vault_activity()` lines 717-727, when `state.json` has `last_run`, the caller's `days` parameter is discarded. Only used as fallback when state is empty.

2. **State only saves at end-of-run.** If a run is killed or hangs, `last_run` never advances. Next run re-does everything plus whatever's new.

3. **Tag enrichment modifies mtime of the files being scanned.** Each run rewrites frontmatter on enriched files → mtime advances → next run sees them as "new" → re-enriches.

4. **Plaud backdating amplifies volume.** `_get_file_date()` routes Plaud `-Full.md` files to their frontmatter `date:` (often months/years old). One recently-touched Plaud file creates one old-date bucket, each bucket = glossary + tags + action-items LLM calls.

### Smoking gun from 2026-04-19 log
```
08:20:48  Scanning 2026-04-17 to 2026-04-19
08:20:53  Found 91 files across 34 dates   ← 34 distinct DLY files to update
```
At pace of ~3 LLM calls × ~25s per file × 91 files, total ~60-120 min before write step.

The 2026-04-17 23:00 cron run never completed (no log marker). Killed or hung, state not advanced, cascaded into 04-18 and 04-19.

## Fix plan — three edits to daily_vault_activity.py

Haiku-level mechanical edits (all in one file, ~15 lines total):

1. **Honor `days` as ceiling, not floor.** Replace lines 720-727 with `max(last_run_dt, end_dt - timedelta(days=days))`. Strip timezone from `last_run_dt` before compare.
2. **Save state per-date-bucket.** Call `_save_state()` inside the `for date_str in sorted(...)` loop, not only at end-of-run. Kill-resilient.
3. **Progress logging.** `log.info(f"Processing {date_str} (N of M, X files)")` instead of bare `Processing {date_str}`.

Full Haiku prompt is preserved in this session's transcript — reuse verbatim when handing off.

## Deferred (don't build preemptively)
- Content-hash de-dupe — only if the feedback loop persists after the three fixes above. Sonnet-level change.
- Investigation of why 91 files were touched — transcript_repair shows "all files OK" for 10+ prior runs, so not the culprit. Most likely the loop itself: vault_activity → frontmatter rewrite → next-run re-pickup.

## What the user should do

1. Let PID 20697 finish. Don't kill it — killing leaves state un-advanced and re-creates the backlog.
2. After it finishes, verify `.vault_activity_state.json` has `last_run` advanced to today.
3. Hand the Haiku prompt for the three edits.
4. Monitor for one week after fix lands. If tag-enrichment is still rewriting the same files nightly, escalate to content-hash de-dupe (Sonnet).

## Diagnostic traps to avoid next time
- **Don't trust a tail read of a still-running log.** `tail -60` caught a 30-second gap between LLM calls and looked like silence. Check `ps aux | grep` for active PID before concluding "crashed."
- **Don't assume `days=N` means what it says.** Read the code path. Fallback-only parameters are a silent anti-pattern.
- **Cron overlap is a real failure mode.** If a 23:00 run doesn't complete by 23:00 next day, the new run inherits broken state. Add a lock file or pgrep check.
