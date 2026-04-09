---
name: Task management — stale cleanup rule + bidirectional Reminders sync
description: Rules for converting stale tasks and plan for completing bidirectional Obsidian↔Reminders sync
type: project
---

## Stale Task Cleanup Rule (APPLIED 2026-04-04)

Tasks in vault files older than 10 days are converted from Obsidian checkbox format to plain bullet:

```
BEFORE: - [ ] Task text 📅 2026-03-05 #work
AFTER:  -- Task text 📅 2026-03-05 #work
```

**Date determination (in priority order):**
1. DLY files (`YYYY-MM-DD-DLY.md`): use filename date
2. Non-DLY files with `MM-DD` prefix (e.g., `03-10 Meeting-Full.md`): parse as `2026-MM-DD`
3. All other files: fall back to mtime
- Completed tasks (`- [x]`) are never touched
- Do NOT use inline `📅` date — the system assigns a default +3 week due date which makes inline dates misleading

**Excluded directories:** System/, Templates/, .trash/, _archive/, Generic_Notes/

**Run 2026-04-04 (pass 1):** 112 tasks across 20 DLY files converted (cutoff: before 2026-03-25).
**Run 2026-04-04 (pass 2):** 464 tasks across 56 non-DLY files converted using MM-DD filename date logic. Total: 576 tasks across 76 files.

**Ongoing:** Should be wired into clean_md_processor.py — when building output for a session whose file date is >10 days old, write extracted action items as `-- text` instead of `- [ ] text`.

**Why:** Obsidian Tasks plugin queries show all unchecked tasks vault-wide. Stale tasks from old daily notes flood the view and can't be meaningfully completed.

**How to apply:** If Eric asks to clean up tasks or reduce tasks in the plugin view, use this rule. Script is a one-liner Python scan — rerun with updated cutoff date as needed.

---

## Bidirectional Reminders Sync — COMPLETE + PRODUCTION TESTED 2026-04-04

**Current state:** COMPLETE + PRODUCTION TESTED 2026-04-04. Fully bidirectional sync confirmed working:
- **Step 7.5** `sync_completions_from_reminders()` — Reminders completed → Obsidian `- [x] ✅ date`. Walks completed "Vault" reminders with Key → matches via `_task_key()` → flips line in source file.
- **Step 7.6** `sync_new_tasks_from_reminders()` — New Reminders tasks (no Key) → today's DLY `## From Reminders` section. Tags reminder with Source+Key after write so it joins normal sync loop.
- **Step 7.7** `sync_completions_to_reminders()` — Obsidian `- [x]` → **deletes** reminder from Reminders app (Obsidian is source of truth). Walks open "Vault" reminders with Source+Key, reads source file, deletes if task is now `- [x]`. Works regardless of incremental scan state.
- All three run even in early-return path (when nothing needs normalization).
- Cron: runs 4x daily at 0,6,12,18 via task_normalizer.py.

**PyRemindKit:** Available in venv (0.1.0). Confirmed working. Reminders lists: Vault, Do Today!!!!, Groceries, Daddy-Doo List. Completed reminders have `notes` field with `Source: /path/to/file.md` and `Key: {12-char-sha1}`.

**Phase 1 — completions Reminders → Obsidian (PROPOSED):**
1. Query completed reminders from "Vault" list with `Key:` in notes
2. Parse `Source:` (full file path) and `Key:` hash
3. Open source file, scan `- [ ]` lines, recompute `_task_key(text, source_file)` for each
4. On match → replace `- [ ]` with `- [x]` + append ` ✅ YYYY-MM-DD` (using reminder `modified_date`)
5. Call BEFORE outbound push in task_normalizer.py (so completed tasks aren't re-created)

**Phase 2 — new tasks Reminders → Obsidian (DEFERRED):**
- Tasks created directly in Reminders (no Key in notes)
- Would append to today's DLY note under `## From Reminders`
- Lower priority, blocked on Phase 1 validation

**Cron:** task_normalizer runs at 0,6,12,18 daily → logs to System/Logs/reminders_sync.log

**Why:** User marks tasks done in Reminders on mobile/iOS but vault files don't update. Also tested two new tasks created directly in Reminders — Phase 2 handles those.

**How to apply:** When Eric asks to fix the sync or "build Phase 1", implement `sync_completions_from_reminders()` in task_reminders_sync.py using the plan above.
