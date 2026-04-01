# Shared Context — Cross-Session Sync

_All Claude sessions (Desktop Opus/Sonnet/Haiku + CLI) should read this at start and append before ending._

## Active Work

| Session | Working On | Files Touched | Updated |
|---------|-----------|---------------|---------|
| CLI Opus (naughty-shaw) | **Daily Vault Activity Tracker BUILT** — `daily_vault_activity.py` (scan→glossary→tags→daily injection). Email ingester patched: output to `Vault/Notes/Email/`, existing-thread location check. Wired into overnight_processor.py + morning_workflow.py. | daily_vault_activity.py, email_thread_ingester/config.py, email_thread_ingester/__main__.py, overnight_processor.py, morning_workflow.py | 2026-04-01 |
| CLI Sonnet (condescending-mccarthy) | **Email Thread Ingester COMPLETE** — 12 modules built + Exchange timeout fixed via `--start-date`/`--limit`/early-exit. Tests: Gmail 48→29 threads, Exchange 106→23 threads, Both 188→61 threads, 0 errors. Memory + SHARED_CONTEXT synced. | System/Scripts/email_thread_ingester/applescript_bridge.py, __main__.py | 2026-03-31 |
| CLI Haiku (silly-gauss) | **Idle** — Last work: AppleScript testing 2026-03-31 (Gmail ✅, Exchange timeout). Exchange since fixed by Sonnet. | — | 2026-03-31 |
| Sonnet Desktop | **Building classify_content.py** | System/Scripts/Workflows/classify_content.py, rag_data/classification.db | 2026-03-30 |

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
- **2026-04-01**: Email ingester output moved to `Vault/Notes/Email/` (was `Vault/Email/`). Config change: `config.EMAIL_DIR = VAULT_ROOT / "Notes" / "Email"`. All downstream paths auto-update. Added existing-thread vault_path check in `_process_thread()` — threads land in same directory on updates.
- **2026-04-01**: Daily Vault Activity Tracker BUILT (`System/Scripts/daily_vault_activity.py`). Three phases: SCAN (mtime-based, Plaud date backdating) → POST-PROCESS (glossary extraction + central merge, LLM tag enrichment, action item extraction) → INJECT (`## Vault Activity` section in DLY files). Dual-LLM: Haiku API → Ollama qwen2.5:7b. Wired into overnight_processor.py and morning_workflow.py. CLI: `--dry-run --days N --no-tags --no-tasks`. Bug found+fixed: `TypeError` from LLM returning ints in tasks list.

## Handoffs

- ~~**Email Thread Ingester → Sonnet CLI or Desktop**~~: **COMPLETE** (2026-03-31). All 12 modules built at `System/Scripts/email_thread_ingester/`. Dry-run verified. Run: `python -m System.Scripts.email_thread_ingester --dry-run`. Needs `ANTHROPIC_API_KEY` env var for Haiku; Ollama fallback works without it. Exchange AppleScript times out on large inboxes.
- **Gmail pipeline → Sonnet Desktop**: SUPERSEDED by Email Thread Ingester above. Old context at `gmail_pipeline_context.md` is still useful reference but the new ingester handles both Exchange + Gmail with threading.
- **classify_content.py → Sonnet Desktop**: Full build spec provided in chat. DB at rag_data/classification.db, manifest at Vault/System/ClassificationReview.md. See prompt in Opus CLI session for full spec.
