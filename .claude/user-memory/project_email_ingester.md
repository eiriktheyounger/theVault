---
name: project_email_ingester
description: Email Thread Ingester — BUILT 2026-03-31. 12-module package at System/Scripts/email_thread_ingester/. Exchange+Gmail via AppleScript, threading, job tracker, daily backlinks.
type: project
---

Email Thread Ingester **BUILT** 2026-03-31 by Sonnet CLI (condescending-mccarthy worktree).

**Location**: `System/Scripts/email_thread_ingester/` (12 modules)
**Status**: Built + production-tested. AppleScript bridge tested 2026-03-31:
- ✅ Gmail: working. 48 msgs/29 threads with `--start-date 2026-03-01`
- ✅ Exchange: timeout RESOLVED 2026-03-31 via `--start-date` + AppleScript early-exit. 106 msgs/23 threads, ~1:50 (well under 240s)

**Modules built**:
- `config.py` — paths, TOPIC_RULES, DOMAIN_TO_ORG, JOB_RELATED_DOMAINS
- `tracking_db.py` — SQLite dedup (processed_messages, threads, contacts)
- `applescript_bridge.py` — Mail.app extraction for Exchange, Gmail, --job mode
- `email_parser.py` — clean_body(), strip_subject_prefixes(), html_to_text(), extract_email_address(), extract_name(), safe_filename()
- `thread_grouper.py` — EmailMessage + EmailThread dataclasses, threading algorithm
- `topic_router.py` — route_thread() with JOB_RELATED_DOMAINS check + Work/Job sub-routing
- `summarizer.py` — Haiku API (needs ANTHROPIC_API_KEY env) → Ollama qwen2.5:7b fallback → placeholder
- `markdown_writer.py` — YAML frontmatter, anchor links, participant table, full message thread
- `contact_tracker.py` — Create/update People/{Name}.md
- `job_tracker.py` — Create/update Job Search/{Company}/_Index.md
- `daily_note_writer.py` — Inject/replace ## Email Activity in daily note
- `__init__.py` + `__main__.py` — run_orchestration() + argparse CLI


**Run commands** (updated with date filter):
```bash
export ANTHROPIC_API_KEY="..."
cd ~/theVault && source .venv/bin/activate
python -m System.Scripts.email_thread_ingester --start-date 2026-03-01 --dry-run --verbose
python -m System.Scripts.email_thread_ingester --start-date 2026-03-01 --limit 200           # Exchange safe default
python -m System.Scripts.email_thread_ingester --account Gmail --start-date 2026-03-01
python -m System.Scripts.email_thread_ingester --job nebius.com --start-date 2026-03-01
```

**Date filter flags** (added 2026-03-31):
- `--start-date YYYY-MM-DD` — only process emails on/after this date; Exchange uses early-exit for fast stop
- `--end-date YYYY-MM-DD` — only process emails on/before this date
- `--limit N` — max messages per account (safety cap; default 99999)

**Known issues**:
- **LinkedIn spam filtering**: `email_parser.py` lacks LinkedIn/notification filtering. Email ingestion will pull LinkedIn notifications + job alerts. Consider adding regex filter for senders matching `*.linkedin.com` in topic router.
- ANTHROPIC_API_KEY must be set in env; Ollama fallback works without it

**Test results (2026-03-31)**:
- Gmail `--start-date 2026-03-01`: 48 messages → 29 threads, 0 errors ✅
- Exchange `--start-date 2026-03-01 --limit 200`: 106 messages → 23 threads, 0 errors ✅ (~1:50, no timeout)
- Both accounts `--start-date 2026-03-01`: 188 messages → 61 threads, 0 errors ✅ (~18 min, Ollama dominant)

**Why:** Supersedes `email_to_vault.py` (Gmail-only, broken token, no threading).

**How to apply:** Always use `--start-date` for Exchange runs. Set ANTHROPIC_API_KEY for Haiku summaries; Ollama fallback works without it. Run from ~/theVault with venv active.

**Production Run History:**
- **2026-04-01 (Sonnet CLI):** 156 extracted, 53 threads, 0 errors. Summarizer: Ollama qwen2.5:7b (ANTHROPIC_API_KEY not set). Flags: `--start-date 2026-03-01 --limit 200`. Output: `Vault/Notes/Email/`. Job indexes created for TCGplayer, DraftKings, Nebius, General. Daily note 2026-04-01-DLY.md updated.

**Next Steps**:
1. ✅ First production run DONE (2026-04-01)
2. Decide on LinkedIn spam filtering — add regex filter if needed
3. ✅ ANTHROPIC_API_KEY set in crontab + .bash_profile + .env (2026-04-01). Next run will use Haiku instead of Ollama.
4. Monthly cadence: re-run with `--start-date` of previous run date to catch new tagged emails
5. Old `Vault/Email/` directory still exists (pre-move data). Consider migrating or archiving.
