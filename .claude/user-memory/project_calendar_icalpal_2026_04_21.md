---
name: Calendar icalPal fallback integration
description: icalPal Ruby gem wired in as TCC-bypass fallback for EventKit calendar fetches. Parent process needs FDA; no Calendar permission dialogs.
type: project
originSessionId: d779d3e3-81e8-4d10-bd15-33a7d93732e7
---
# Calendar icalPal Fallback (2026-04-21)

## What shipped

Unified calendar access layer with EventKit primary + icalPal fallback. Triggered by the research-first rule after repeated TCC permission walls on EventKit fetches from bash/cron contexts.

### New file
- `System/Scripts/calendar_icalpal.py` — Python wrapper around the `icalPal` Ruby binary. Shells out via `subprocess`, parses JSON output, normalizes to a shared event dict.

### Modified files
- `System/Scripts/calendar_forward_back.py` — `fetch_events_in_range()` now routes through `_fetch_via_eventkit()` → `_fetch_via_icalpal()` based on `THEVAULT_CALENDAR_BACKEND`.
- `System/Scripts/calendar_daily_injector.py` — Same pattern applied to `fetch_events_for_date()`.

### Gem install (one-time)

```bash
export PATH="/opt/homebrew/opt/ruby/bin:$PATH"
export GEM_HOME="$HOME/.gem"
export GEM_PATH="$HOME/.gem"
mkdir -p "$GEM_HOME"
gem install icalPal
```

Installed version: 4.1.1. Binary at `~/.gem/bin/icalPal`. The `--user-install` flag alone did not work — dependencies (e.g. `logger`) tried to write to Homebrew's gem dir. Explicit `GEM_HOME` is the fix.

## Backend selection

Environment variable `THEVAULT_CALENDAR_BACKEND`:
- `auto` (default) — try EventKit; fall back to icalPal if EK is unauthorized or returns 0 events and icalPal is available
- `eventkit` — EventKit only
- `icalpal` — icalPal only

Auto-mode avoids forcing icalPal when EventKit is already working (e.g. when Claude Code Desktop runs inside an app with Calendar permission).

## Full Disk Access requirement

icalPal reads `~/Library/Group Containers/group.com.apple.calendar/Calendar.sqlitedb` directly. This bypasses EventKit's per-app Calendar TCC dialog, but it DOES require macOS Full Disk Access granted to whichever parent process spawns the Ruby binary:
- Terminal / iTerm2 (for manual runs)
- `/bin/bash` + Ruby (for launchd-spawned scheduled runs — see launchd migration below)
- Claude Code CLI (if running in a sandbox — this is the one that was failing)

To grant FDA:
```
open 'x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles'
```

Then in the FDA pane, click `+`, press `Cmd+Shift+G` to type a path, and add:
- `/bin/bash` — the shell that launchd spawns
- `/opt/homebrew/Cellar/ruby/4.0.2/bin/ruby` — the Ruby binary icalPal runs under (resolves the `/opt/homebrew/opt/ruby/bin/ruby` symlink)
- `/Users/ericmanchester/.pyenv/versions/3.12.5/bin/python3.12` — the Python interpreter that the venv uses (reads Calendar sqlite via the icalPal wrapper)

> `/usr/sbin/cron` canNOT be added via the FDA UI on Sequoia. That is why we migrated the three theVault scheduled jobs from cron to launchd on 2026-04-21 — each launchd agent inherits FDA from the binaries it spawns, which CAN be granted.

## launchd migration — ATTEMPTED and REVERTED (2026-04-21)

**Outcome**: Rolled back. Cron is canonical. Three plists archived at `System/Archive/launchd-plists-2026-04-21/`.

### Why reverted — the TCC test matrix

A minimal `com.ericmanchester.tcctest` LaunchAgent with `RunAtLoad=true` produced:

| Test | Action | Result | Implication |
|------|--------|--------|-------------|
| A | `touch /tmp/...` | ✅ PASS | launchd basically works |
| B | `touch $HOME/...` | ✅ PASS | local user-home writes fine |
| C | `touch Vault/System/Logs/Touch/...md` (Vault → /Volumes/home SMB) | ❌ FAIL, EPERM | launchd blocked on network volumes |
| D | `touch /Volumes/home/MacMiniStorage/Vault/...md` (direct) | ❌ FAIL, EPERM | confirms C — symlink-agnostic |
| E | `ls ~/Library/Mail/` | ❌ FAIL, EPERM | **launchd has NO FDA** |
| F | `ls ~/Library/Group Containers/group.com.apple.calendar/Calendar.sqlitedb` | ✅ PASS | Calendar sqlite IS readable under launchd |

### Root cause

TCC assigns responsibility to the process that spawned the binary. For a LaunchAgent:
- Parent = `launchd` (PID 1 in the user's Aqua session)
- Child = `/bin/bash`
- TCC looks at `launchd` as responsible process → no FDA → child inherits nothing

Adding `/bin/bash` to the FDA UI does NOT help. The grant only applies when Terminal (or another FDA-granted app) is the responsibility chain parent. SIP-protected binaries like `/bin/bash` can be added to FDA but the grant only activates when the responsibility chain includes an FDA-granted parent.

### Why cron was working all along

`/usr/sbin/cron` has some grandfathered TCC state (possibly set automatically by the system when user enabled cron via `crontab -e`, or carried over from pre-Sequoia) that gives it network-volume access. That's why overnight+reminders+backup have been writing to NAS successfully for weeks. The ORIGINAL motivation for the launchd migration — "cron can't be added to the FDA UI on Sequoia" — turned out to be a non-issue because **cron doesn't actually need FDA for NAS writes, just for a few specific protected paths like ~/Library/Mail**. And icalPal's `Calendar.sqlitedb` is NOT one of those protected paths (test F proved this).

### What this means for the future

- **Keep using cron** for everything that touches the NAS.
- **icalPal already works from cron** — Calendar sqlite is readable without FDA. The `calendar_icalpal.py` wrapper + `THEVAULT_CALENDAR_BACKEND=auto` fallback chain is unchanged.
- **If a future job only needs local writes + Calendar reads** (no NAS), launchd is viable. Plists archived at `System/Archive/launchd-plists-2026-04-21/` as templates.
- **If launchd ever becomes necessary for NAS writes**, the path forward is a signed app bundle (so TCC has a responsible bundle ID to grant) — not worth it for hobbyist use.

### Crontab state post-revert
Fully restored from `Vault/System/Logs/crontab.pre-launchd-20260421.bak`. Three entries:
- `0 23 * * *` → overnight_processor.py
- `0 0,6,12,18 * * *` → task_normalizer
- `0 11 * * *` → overnight_processor.py $YESTERDAY (backup)

---

## launchd migration (DETAILS — historical reference)

Cron was replaced by three LaunchAgents on 2026-04-21 (since reverted). All three used `preflight.sh` → venv → Python, matching the old crontab recipe exactly, but launchd re-runs jobs missed during sleep/wake.

| Label | Plist | Schedule | Python command |
|-------|-------|----------|---------------|
| `com.ericmanchester.thevault.overnight` | `~/Library/LaunchAgents/com.ericmanchester.thevault.overnight.plist` | 23:00 daily | `python3 System/Scripts/overnight_processor.py` |
| `com.ericmanchester.thevault.reminders-sync` | `~/Library/LaunchAgents/com.ericmanchester.thevault.reminders-sync.plist` | 00:00, 06:00, 12:00, 18:00 | `python3 -m System.Scripts.task_normalizer` |
| `com.ericmanchester.thevault.backup` | `~/Library/LaunchAgents/com.ericmanchester.thevault.backup.plist` | 11:00 daily | `YESTERDAY=$(date -v-1d +%Y-%m-%d) && python3 System/Scripts/overnight_processor.py $YESTERDAY` |

Each plist embeds:
- `EnvironmentVariables.PATH` with `~/.gem/bin:/opt/homebrew/opt/ruby/bin` first (so icalPal resolves)
- `GEM_HOME=$HOME/.gem` and `GEM_PATH=$HOME/.gem` (so icalPal finds its gems without Homebrew-perm conflicts)
- `THEVAULT_CALENDAR_BACKEND=auto`
- `RunAtLoad=false` (do NOT run on reboot — the 23:00 schedule handles it)

### Operate

```bash
UID_N=$(id -u)
# Status
launchctl print "gui/$UID_N/com.ericmanchester.thevault.overnight" | head -20

# Run now (smoke test)
launchctl kickstart -k "gui/$UID_N/com.ericmanchester.thevault.overnight"

# Reload after editing a plist
launchctl bootout "gui/$UID_N/com.ericmanchester.thevault.overnight"
launchctl bootstrap "gui/$UID_N" ~/Library/LaunchAgents/com.ericmanchester.thevault.overnight.plist

# Disable temporarily
launchctl disable "gui/$UID_N/com.ericmanchester.thevault.overnight"
# Re-enable
launchctl enable "gui/$UID_N/com.ericmanchester.thevault.overnight"
```

### Crontab state
Crontab retained only the `ANTHROPIC_API_KEY` header and a migration-note comment. Backup of the pre-migration crontab saved at `Vault/System/Logs/crontab.pre-launchd-20260421.bak`.

### First smoke test (2026-04-21 13:10)
`launchctl kickstart` of reminders-sync exited code 1 — preflight aborted at the NAS write-check (`Operation not permitted` on `Vault/System/Logs/Touch/NAS Check.md`). This is the expected TCC wall for launchd-spawned `/bin/bash` writing to the SMB-mounted NAS. Resolves after granting FDA to `/bin/bash` per the list above.

## Libraries evaluated

| Library | Lang | Last updated | Solves TCC? | Tradeoffs | Decision |
|---------|------|--------------|-------------|-----------|----------|
| PyObjC EventKit | Python | Active (current) | ❌ Still needs Calendar TCC | Native, well-integrated, ships with PyObjC | Keep as primary |
| icalBuddy | ObjC CLI | 2014 (dead) | Partial | Unmaintained, broken on modern macOS | Reject |
| icalPal | Ruby gem | 2026 (active) | ✅ Reads sqlite directly | Requires FDA on parent; Ruby subprocess overhead | Adopt as fallback |
| Direct sqlite read (Python) | — | DIY | ✅ | Reinventing icalPal's schema handling | Reject (use icalPal instead) |
| caldav Python libs | Python | Varies | ❌ Requires server credentials | Doesn't fit local-first model | Reject |

Decision: **EventKit primary + icalPal fallback**. Keeps the zero-install common path (PyObjC already in venv) while giving cron/sandbox runs a TCC-free escape hatch.

## Normalized event shape

Both `_fetch_via_eventkit` and `_fetch_via_icalpal` return dataclass instances (`RangeEvent` in forward_back, `CalendarEvent` in daily_injector) with identical public fields:

```
title, start, end, calendar_name, location, attendees, all_day
# RangeEvent adds: notes, url
```

icalPal JSON fields mapped in `calendar_icalpal._normalize_row()`:
- `sdate` / `start_date` → `start`
- `edate` / `end_date` → `end`
- `title` (icalPal renames `CalendarItem.summary` → `title` in its SQL)
- `calendar` → `calendar_name`
- `location` + `address` → joined `location`
- `notes` (icalPal renames `CalendarItem.description` → `notes`)
- `attendees` (JSON array of display names)
- `all_day` (0/1 → bool)
- `url`

Datetimes returned as naive local time (tz stripped via `.astimezone().replace(tzinfo=None)`) to match EventKit's shape.

## Verification (2026-04-21)

Tested in-sandbox (expected TCC denial on both backends):
- `icalpal_available()` → True
- `fetch_events_in_range(now, now+1d)` → `[]`, backend logs show "EventKit returned 0 events; cross-checking with icalPal" → "icalPal permission denied"
- Env override `THEVAULT_CALENDAR_BACKEND=eventkit` / `=icalpal` — both respected

Production verification pending Eric granting FDA to the cron runner and re-running overnight/morning workflows.

## Anti-patterns avoided

- Did NOT parse icalPal's default/ANSI output with regex. Used `--output json`.
- Did NOT hardcode the gem binary path. Discovery falls through env override → PATH → known gem bin dirs.
- Did NOT require Ruby/gem on non-macOS dev machines. `icalpal_available()` returns False gracefully.
- Did NOT force a subprocess call on every fetch. Auto-mode only invokes icalPal when EventKit returns 0 and icalPal is available.

## Dedup fix — multi-account / multi-day all-day events (2026-04-22)

**Problem**: DLY `🎯 Today — Forward-Back` sections showed all-day events duplicated 3–5× per block. Two causes:
1. Shared family CalDAV calendars appear under multiple account stores → icalPal emits one row per store, all sharing the same UUID.
2. Multi-day all-day events are pre-expanded by icalPal into per-day rows sharing the same UUID and same `sseconds`/`eseconds`.

**Fix** (display-layer only; did NOT touch overnight_processor.py or injector logic):

- `calendar_icalpal.py` `_normalize_row()` — now propagates `UUID` → `uid` in the returned dict.
- `calendar_forward_back.py`:
  - `RangeEvent` gained `uid: str = ""` field.
  - `_fetch_via_eventkit()` captures `calendarItemExternalIdentifier()` (fallback `calendarItemIdentifier()`).
  - `_fetch_via_icalpal()` passes through `row.get("uid", "")`.
  - New `_dedupe_events()` helper keyed on **UID first**, falling back to `(title, start.isoformat(), end.isoformat(), all_day)` when UID is empty. Applied at every return path in `fetch_events_in_range()`.

**Verification**:
- 04-05 test: 5× Passover → 1×, 3× Residence Inn → 1× inside forward-back block.
- Backfill 2026-04-01 through 2026-04-21 via `inject_recent_context.py` — all 21 DLYs re-injected, dedup collapsed 5–10 duplicate rows per window.

**Why not also dedup at the icalPal layer**: Both backends benefit from the same collapse logic, so the dedup lives at the unified `fetch_events_in_range` seam where UID + tuple fallback give identical behavior across backends.

## Known gaps / follow-ups

1. **FDA prompt**: First time Eric runs from a new cron context, icalPal will fail silently (logged as warning). Need to grant FDA to `/usr/sbin/cron` or the wrapping process.
2. **Parity test in production**: Once FDA granted, compare EventKit vs icalPal output for the same day to verify no field drift (especially recurring events).
3. **Timezone edge cases**: icalPal emits ISO 8601 with offset. The wrapper converts to local naive datetime. If the user travels across timezones, verify event times remain correct.
4. **Reminders**: icalPal also supports Reminders (`tasks` command). Not wired in — the theVaultPilot Reminders sync already works. Could be a future fallback if that path ever hits TCC.
