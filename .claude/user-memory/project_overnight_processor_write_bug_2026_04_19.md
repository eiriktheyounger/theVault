---
name: Overnight Processor Write Bug — 2026-04-19
description: Critical — results never written to DLY file despite successful processing
type: bug
priority: P0
assignee: Opus
originSessionId: 4bc5104f-958f-4f24-aee1-414fc3ed9bec
---
## Problem Statement

The `overnight_processor.py` executes successfully but **fails to write output to the DLY file**. All processing runs (task extraction, summarization, task normalization, Reminders sync, vault activity tracking), but the user sees no results.

**Impact**: DLY files have empty "Overnight Results" and "Overnight Processing" sections despite the processor running.

## Evidence

### Affected Dates
- April 17: DLY empty (processor skipped because no captures)
- April 18: DLY empty (NAS check failed during cron run; manual run at 08:20 on 04-19 had same issue)
- April 19: DLY empty (manual run at 08:20)

### Manual Test Run (April 19, 08:20)
```bash
cd ~/theVault && source .venv/bin/activate && python3 System/Scripts/overnight_processor.py 2026-04-18
```

**Logs show execution succeeded:**
- 08:20:00 — Loaded daily note (17,256 chars)
- 08:20:00 — Processing 460 chars of captures ✅
- 08:20:34 — **Tasks extracted: 3 lines** ✅
- 08:20:37 — **Summary generated: 505 chars** ✅
- 08:20:37 — Running task normalizer ✅
- 08:20:42 — Found 159 tasks across 26 files ✅
- 08:20:44 — **117 tasks normalized** ✅
- 08:20:46 — **Synced 7 tasks to Apple Reminders** ✅
- 08:20:54 — daily_vault_activity started ✅
- 08:38:02 — daily_vault_activity still processing ✅
- **08:38:04** — **Last log entry (HTTP request, no "Daily note updated")**

### Critical Finding

**Missing from logs:**
```
"Daily note updated: /Users/ericmanchester/theVault/Vault/Daily/2026/04/2026-04-18-DLY.md"
"=== Overnight processing complete ==="
```

These should appear at lines 213 and 229 of overnight_processor.py, but never do.

### File State

**Before run:**
- DLY file: 87 lines, Email Activity section populated, Overnight sections empty

**After run:**
- DLY file: 166 lines, Email Activity unchanged, **Overnight sections STILL EMPTY**

Grep result:
```bash
$ grep -i "tasks extracted\|day summary\|processing log" /Volumes/home/MacMiniStorage/Vault/Daily/2026/04/2026-04-18-DLY.md
(no output)
```

## Root Cause Analysis

### Code Flow (overnight_processor.py)
1. **Lines 120-136**: Load DLY, read captures — ✅ **Works**
2. **Lines 138-147**: Extract tasks, generate summary — ✅ **Works**
3. **Lines 149-159**: Task normalizer — ✅ **Works** (117 tasks normalized logged)
4. **Lines 161-169**: `run_vault_activity()` — ✅ **Works** (logs show processing)
5. **Lines 171-186**: Transcript repair — **Unknown** (no logs after 08:38:02)
6. **Lines 189-202**: Build overnight_content — **Never reached?**
7. **Lines 205-213**: Write section + log — **NEVER EXECUTED** (no log message)
8. **Line 229**: Log "complete" — **NEVER EXECUTED** (no log message)

### Hypothesis

The process either:
1. **Hangs during vault activity** (line 164 `run_vault_activity()`) — but logs continue, so unlikely
2. **Silent exception** after line 169 that's caught but not logged
3. **Process exits** without reaching lines 212-213
4. **Vault activity returns late**, and the write step times out or fails silently

## Questions for Opus

1. Is there an exception handler catching errors silently after line 169?
2. Does `run_vault_activity()` return cleanly? (Check for hanging threads/subprocesses)
3. Does the write at line 212 have any guards that might skip it?
4. Is there a timeout or signal being sent that terminates the process?
5. Should there be a try-except around the write to log failures?

## Key Files

- **overnight_processor.py**: `/Users/ericmanchester/theVault/System/Scripts/overnight_processor.py`
- **overnight.log**: `/Users/ericmanchester/theVault/System/Logs/overnight.log`
- **Test DLY**: `/Volumes/home/MacMiniStorage/Vault/Daily/2026/04/2026-04-18-DLY.md`
- **daily_vault_activity.py**: `/Users/ericmanchester/theVault/System/Scripts/daily_vault_activity.py`
- **task_normalizer.py**: `/Users/ericmanchester/theVault/System/Scripts/task_normalizer.py`

## Workaround

Currently: None. Results are lost.

## Next Steps

Opus should:
1. Add logging after each major section (esp. after line 169)
2. Add exception handler around vault_activity (line 164) with full stack trace
3. Add exception handler around write (line 212) with full stack trace
4. Check if vault_activity returns properly or has hanging threads
5. Test with a simple date to isolate the issue
6. Run overnight_processor with `--debug` or verbose logging

---

**Haiku note**: This is a blocking issue preventing daily DLY population. All processing infrastructure works, but output is invisible to the user.
