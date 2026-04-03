# Shared Context — Cross-Session Sync

_All Claude sessions (Desktop Opus/Sonnet/Haiku + CLI) should read this at start and append before ending._

## Active Work

| Session | Working On | Files Touched | Updated |
|---------|-----------|---------------|---------|
| CLI Opus (naughty-shaw) | **Idle** — Last: memory/context sync + ANTHROPIC_API_KEY fix (crontab, .bash_profile, .env). Daily Vault Activity Tracker built. Email ingester patched. | daily_vault_activity.py, .env, crontab, memory files | 2026-04-01 |
| CLI Sonnet (condescending-mccarthy) | **Idle** — Last: morning_workflow.py ANTHROPIC_API_KEY fix (_load_dotenv() added). clean_md_processor.py --reprocess flag added. Memory/SHARED_CONTEXT sync. | System/Scripts/Workflows/morning_workflow.py, System/Scripts/clean_md_processor.py, memory files | 2026-04-03 |
| CLI Haiku (silly-gauss) | **Active** — overnight_processor.py API key fix (logger init order). Overnight run for 2026-04-02 SUCCESS: Haiku summary generated, 9 tasks normalized, reminders synced. | System/Scripts/overnight_processor.py, SHARED_CONTEXT | 2026-04-03 08:14 |
| Sonnet Desktop | **Idle/Unknown** — Last known: building classify_content.py (2026-03-30). | System/Scripts/Workflows/classify_content.py, rag_data/classification.db | 2026-03-30 |

## Decisions Made

- **2026-03-26**: Gmail pipeline remaining build work → Sonnet Desktop (Pro plan, not CLI API). Full context at `Vault/System/DesktopClaudeCode/gmail_pipeline_context.md`
- **2026-03-30**: Post-ingest file organization DONE — 47 files organized from Notes/ into HarmonicInternal/, Personal/, Knowledge/, Reference/
- **2026-03-30**: Content classifier (classify_content.py) design locked — Haiku API, SQLite DB, markdown manifest review, learning feedback loop
- **2026-03-30**: repair_embeddings.py built — fixes ~5,200 orphan chunks missing FAISS vectors. Run from ~/theVault: `python3 -m System.Scripts.RAG.repair_embeddings --dry-run`
- **2026-03-30**: Vault file organization pattern established: `Space/FocusedSpace/[data-driven breakdown]/file`. HarmonicInternal uses `HarmonicInternal/{Client}/{Project}/`
- **2026-03-30**: RAG full rebuild DONE — 53,381 vectors in FAISS (up from 42,293, +26%). Coverage 95.8% (passes threshold). batch_reindex.py 10/10 batches. Q/A gate still missing (rag_qa_agent.py not found).
- **2026-03-30**: OPERATIONS-INDEX.md updated — added Ingest section, RAG Indexing section, File Classification section; marked classify_content.py live, toc_generator.py EOL'd.

- **2026-03-30**: Auto-sync system built — `sync_session_state.sh` + PostToolUse/Stop hooks auto-generate `.agents/SESSION_STATE.md` from CLI memory. Desktop sessions read SESSION_STATE.md for consolidated view.
- **2026-03-30**: Email Thread Ingester architecture complete (Opus CLI). Plan at `ResumeEngine/.claude/worktrees/naughty-shaw/.claude/plans/delegated-questing-lagoon.md`. Build prompt at `.agents/email_ingester_build_prompt.md`. Covers: Exchange+Gmail via AppleScript, thread grouping with fork detection, job-specific bulk import (`--job`), daily note backlinks, Haiku API summarizer. Assigned to Sonnet for build, Haiku for extraction testing.
- **2026-03-31**: Email Thread Ingester BUILT by Sonnet CLI (condescending-mccarthy). All 12 modules at `System/Scripts/email_thread_ingester/`. Gmail verified OK. Exchange AppleScript times out on large inboxes (known, workaround: tag fewer at a time). Needs `ANTHROPIC_API_KEY` for Haiku; Ollama qwen2.5:7b fallback works.
- **2026-03-31**: Email batch tagging decision — Start with Gmail-only extraction (avoids Exchange timeout). Tag Exchange emails in smaller batches (~100 at a time) once Gmail pipeline validated. First production run: Gmail-only, no Exchange extraction.
- **2026-03-31**: Exchange AppleScript timeout RESOLVED — `--start-date`/`--end-date`/`--limit` added to all three extraction functions. Exchange uses AppleScript early-exit (`if msgDate < startDate then exit repeat`) since Mail.app returns newest-first. Both accounts tested clean: 188 msgs → 61 threads, 0 errors. Ready for production run (drop `--dry-run`). Goal: set `ANTHROPIC_API_KEY` so Haiku summarizer runs instead of Ollama fallback.
- **2026-04-01**: Email Thread Ingester FIRST PRODUCTION RUN — 156 extracted, 53 threads written, 0 errors. Summarizer: Ollama qwen2.5:7b (ANTHROPIC_API_KEY not set). Output: Vault/Notes/Email/Job Search/{TCGplayer,DraftKings,Nebius,General}, Finance, Work, General. All _Index.md files created. Daily note 2026-04-01-DLY.md updated with ## Email Activity. Flags: --start-date 2026-03-01 --limit 200.
- **2026-04-01**: Email ingester output moved to `Vault/Notes/Email/` (was `Vault/Email/`). Config change: `config.EMAIL_DIR = VAULT_ROOT / "Notes" / "Email"`. All downstream paths auto-update. Added existing-thread vault_path check in `_process_thread()` — threads land in same directory on updates.
- **2026-04-01**: Daily Vault Activity Tracker BUILT (`System/Scripts/daily_vault_activity.py`). Three phases: SCAN (mtime-based, Plaud date backdating) → POST-PROCESS (glossary extraction + central merge, LLM tag enrichment, action item extraction) → INJECT (`## Vault Activity` section in DLY files). Dual-LLM: Haiku API → Ollama qwen2.5:7b. Wired into overnight_processor.py and morning_workflow.py. CLI: `--dry-run --days N --no-tags --no-tasks`. Bug found+fixed: `TypeError` from LLM returning ints in tasks list.
- **2026-04-01**: ANTHROPIC_API_KEY added to crontab (top-level var), .bash_profile (already existed), ~/theVault/.env (new), ~/theVault/ResumeEngine/.env (new). All cron jobs and scripts now have access. Tonight's 11 PM overnight run should use Haiku instead of Ollama fallback.

## Handoffs

- ~~**Email Thread Ingester → Sonnet CLI or Desktop**~~: **COMPLETE** (2026-03-31). First production run 2026-04-01: 156→53 threads, 0 errors. ANTHROPIC_API_KEY now set for Haiku.
- ~~**Gmail pipeline → Sonnet Desktop**~~: **SUPERSEDED** by Email Thread Ingester. Old context at `gmail_pipeline_context.md` is reference only.
- **classify_content.py → Sonnet Desktop**: Full build spec provided in chat. DB at rag_data/classification.db, manifest at Vault/System/ClassificationReview.md. Status unknown since 2026-03-30.
