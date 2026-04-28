---
name: Autonomous Operation Hardening (2026-04-15)
description: Mac Mini M4 unattended-operation system — preflight.sh, app cleanup, NAS auto-mount, DLY auto-create, Ollama tuning. Built so cron jobs work while Eric travels.
type: project
originSessionId: d779d3e3-81e8-4d10-bd15-33a7d93732e7
---
# Autonomous Operation Hardening — 2026-04-15

**Goal**: Mac Mini M4 must run all daily workflows (overnight, morning, reminders sync, backup) with zero human intervention while Eric travels or forgets to close apps.

## What was built

### preflight.sh — `System/Scripts/preflight.sh`
One script every cron job calls FIRST. Five steps:
1. **Close heavy GUI apps** via `osascript "quit"` (graceful, NOT pkill). Closes: Chrome, Safari, Firefox, Slack, Discord, Spotify, Zoom, Teams, Preview, TextEdit, Numbers, Pages, Keynote. Keeps: Finder, Mail (needed for email fetch), Reminders, Calendar, Obsidian, Claude.
2. **Mount NAS** if `/Volumes/home/MacMiniStorage` missing. Uses `mount_smbfs` + macOS Keychain (updated 2026-04-17 — old `open smb://` triggered GUI prompt). After both mount and already-mounted branches, runs a live write-check.
3. **NAS write-check** (added 2026-04-18): appends a canary line to `Vault/System/Logs/Touch/NAS Check.md`. Proves mount is alive and writable, not just present as a directory. Aborts if write fails (catches stale/hung mounts). Log visible in Obsidian.
4. **Validate symlinks** (Vault, Inbox, Processed) point to NAS. Aborts if broken.
4. **Start Ollama** via `brew services start ollama` if not running.
5. **Create today's DLY** from inline template if missing — NEVER overwrites existing.
6. **Source .env** so workflows have ANTHROPIC_API_KEY + Ollama tuning vars.

Logs every step to `System/Logs/preflight.log`. Exit 0 success / 1 failure.

### Cron updated
All 3 entries (overnight 11pm, reminders 4x daily, backup 11am) now chain `bash preflight.sh && ...` instead of `bash check_nas.sh && ...`.

### Ollama tuning in .env
- `OLLAMA_FLASH_ATTENTION=1` — Metal-optimized attention
- `OLLAMA_NUM_PARALLEL=1` — predictable memory
- `OLLAMA_MAX_LOADED_MODELS=2` — gemma4:e4b + nomic-embed together
- `OLLAMA_KEEP_ALIVE=5m` — auto-unload to free RAM

## Mail.app must stay open
macOS only fetches new mail when Mail.app is running. Mail is NOT in the heavy_apps quit list. ~130MB cost is fine.

## Reminders/Calendar apps NOT required
- `task_normalizer` uses PyRemindKit (Reminders framework, not the app)
- `calendar_daily_injector.py` uses EventKit framework (not Calendar.app)
- Both can be closed safely. Apps are not in the quit list to avoid surprising the user, but closing them frees ~200MB.

## Tag enrichment fixes (daily_vault_activity.py)
- Bootstrap: enrich even when tags.yaml is empty (was chicken-and-egg)
- Send actual content (1500 chars) not just title (was 200 chars)
- Protect source-type tags via PROTECTED_TAGS = {plaud, meeting, transcript, email, email-thread, daily, weekly, monthly, summary} — these never get stripped by LLM enrichment
- Prompt now includes "STRONGLY prefer reusing tags from approved list, fuzzy match"
- Cap at 10 tags after merge

## Email backlinks now relative
`markdown_writer.py:147` strips everything up to and including `/Vault/` so wikilinks render properly in Obsidian (e.g., `Notes/Email/Job Search/...` instead of `/Users/.../Vault/Notes/Email/...`).

## RAM reality on Mac Mini M4 16GB
- Gemma 4 E4B loaded: ~5.5GB → free RAM drops to ~60MB
- macOS handles via memory compression (works fine, ~15% pressure during inference)
- KEEP_ALIVE=5m frees the 5.5GB after last request
- Chrome with many tabs (3-4GB) + Gemma 4 (5.5GB) = tight but won't hard-hang. Will slow down (timeouts possible).
- preflight.sh closes Chrome before workflows run → eliminates the risk

## Known issues NOT fixed (deferred)
- Anthropic JSON parse errors in summarizer → fixed 2026-04-18 (see project_email_ingester.md)
- Incremental indexer count_mismatch RuntimeError → couldn't reproduce in current code (line 148 already passes ok=True). May have been stale .pyc — cleared cache.
- NAS symlink corruption from laptop migration is now mitigated by preflight Step 2 validation
