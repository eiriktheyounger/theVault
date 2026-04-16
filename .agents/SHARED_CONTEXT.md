# Shared Context — Cross-Session Sync

_All Claude sessions (Desktop Opus/Sonnet/Haiku + CLI) should read this at start and append before ending._

## Active Work

| Session | Working On | Files Touched | Updated |
|---------|-----------|---------------|---------|
| CLI Opus | **ResumeEngine Phase 4 COMPLETE (2026-04-16)** — Anti-fabrication overhaul: (1) `_canonical.yaml` ground-truth manifest (8 roles, 7+4 patents, 4 Emmys, affiliations, education, 21 banned_claims); (2) Two-stage generator: Stage A = Sonnet tailors ONLY bullets+summary (JSON), Stage B = Python assembles from canonical (titles/patents/awards/contact/education never LLM-generated); (3) `sanitize_tailored_content()` strips banned claims from Stage A output before assembly; (4) `scan_fabrications.py` post-generation validator (10 check categories, caught 69 violations in old output, 0-1 in new); (5) `render_docx.py` module for .docx output alongside .md; (6) `--legacy` flag preserves old single-stage path for rollback; (7) Fixed TWC 2012-2017 context file ("independent architect" → "lead architect and IC"). **End-to-end validated** on Akamai JD: correct contact, titles, all 11 patents, all 4 Emmys, Television Academy membership, no fabricated certs, no fabricated degree. Phase 1-3 resilience code preserved. API credits exhausted — batch re-run pending credit reload. | ResumeEngine/jd_analyzer.py, ResumeEngine/render_docx.py (NEW), ResumeEngine/scan_fabrications.py (NEW), ResumeEngine/context/_canonical.yaml (NEW), ResumeEngine/context/roles/time-warner-cable-2012-2017.md | **2026-04-16** |
| CLI Opus | **Autonomous Operation Hardening COMPLETE (2026-04-15)** — Built preflight.sh (RAM cleanup, NAS auto-mount, Ollama auto-start, DLY auto-create, env source), wired all 3 cron entries through it. Fixed: ViewLift glossary entries (3), tag enrichment (bootstrap when empty + send actual content + protect source-type tags + fuzzy-match prompt), stop_all.py (clean brew services stop), .env (Ollama tuning vars), QUICK-REFERENCE.md (indexer module path + reminders sync entry + preflight entry), email backlinks (relative wikilinks). Cleared stale indexer pyc cache. | System/Scripts/preflight.sh (NEW), Vault/System/glossary.md, System/Scripts/daily_vault_activity.py, System/Scripts/Services/stop_all.py, .env, Vault/System/QUICK-REFERENCE.md, System/Scripts/email_thread_ingester/markdown_writer.py, crontab | **2026-04-15** |
| CLI Opus | **Gemma 4 Session 6 COMPLETE** — Full validation passed. Post-build report written. CLAUDE.md updated. All 52 capabilities verified, 0 regressions. | CLAUDE.md, post-build-report.md, SHARED_CONTEXT.md | **2026-04-14** |
| **Sonnet Desktop** | **Tasks 1+2 COMPLETE** — rag_qa_agent.py (18 tests, Haiku grader, markdown report, exit 0/1/2), calendar integration (calendar_daily_injector.py, generate_weekly_summary.py, calendar_mapper.py updated, morning_workflow.py Steps 2+6, evening_workflow.py Sunday WKY trigger, overnight_processor.py 1st-of-month MTH trigger). | System/Scripts/rag_qa_agent.py, System/Scripts/calendar_daily_injector.py, System/Scripts/generate_weekly_summary.py, System/Scripts/Workflows/calendar_mapper.py, System/Scripts/Workflows/morning_workflow.py, System/Scripts/Workflows/evening_workflow.py, System/Scripts/overnight_processor.py | **2026-04-14** |
| **CLI Haiku** | **HAIKU_BRIEFING Tasks 1+2+3 COMPLETE** — Fixed RAG incremental indexing defaults, updated OPERATIONS-INDEX.md (models, chunks, versions), created QUICK-REFERENCE.md. All 3 tasks done. | System/Scripts/RAG/retrieval/indexer.py, System/Scripts/batch_reindex.py, Vault/System/OPERATIONS-INDEX.md, Vault/System/QUICK-REFERENCE.md, SHARED_CONTEXT.md | **2026-04-14** |

## Current System State (2026-04-14)

- **All P0/P1/P2 priorities COMPLETE** — overnight processor, email ingester, vault activity tracker, Reminders sync, file classification, RAG rebuild (100% coverage)
- **RAG index**: 61,903 chunks, 100% coverage, EMBED_CTX=512 (production config locked)
- **Ollama models**: gemma4:e4b (9.6GB), gemma3:4b (3.3GB), qwen2.5:7b (4.7GB), nomic-embed-text (274MB)
- **Ollama version**: **0.20.7** (upgraded from 0.12.9 on 2026-04-14)
- **ollama Python pkg**: **0.6.1** (upgraded from 0.3.3 on 2026-04-14)
- **Memory with E4B**: 15G used (12G wired), 74MB free — tight but inference runs cleanly. No thinking tags observed in simple queries.
- **FAISS canary**: `8e49a6f4901335532a9f9e1cf58189cfdd546295e7a30c62695f94785dda6ac4` (updated: post-rebuild 2026-04-13)
- **Tailscale**: Installed (1.96.4) — needs Eric to run `tailscale up` interactively (requires sudo + browser auth)
- **starlette**: Pinned to 0.37.2 (downgraded from 1.0.0 — ollama 0.6.1 upgrade pulled in incompatible version)
- **Server branch**: `gemma4/session-2-core-server` (auto-committed)

<<<<<<< HEAD
- **2026-03-30**: Auto-sync system built — `sync_session_state.sh` + PostToolUse/Stop hooks auto-generate `.agents/SESSION_STATE.md` from CLI memory. Desktop sessions read SESSION_STATE.md for consolidated view.
- **2026-03-30**: Email Thread Ingester architecture complete (Opus CLI). Plan at `ResumeEngine/.claude/worktrees/naughty-shaw/.claude/plans/delegated-questing-lagoon.md`. Build prompt at `.agents/email_ingester_build_prompt.md`. Covers: Exchange+Gmail via AppleScript, thread grouping with fork detection, job-specific bulk import (`--job`), daily note backlinks, Haiku API summarizer. Assigned to Sonnet for build, Haiku for extraction testing.
- **2026-03-31**: Email Thread Ingester BUILT by Sonnet CLI (condescending-mccarthy). All 12 modules at `System/Scripts/email_thread_ingester/`. Gmail verified OK. Exchange AppleScript times out on large inboxes (known, workaround: tag fewer at a time). Needs `ANTHROPIC_API_KEY` for Haiku; Ollama qwen2.5:7b fallback works.
- **2026-03-31**: Email batch tagging decision — Start with Gmail-only extraction (avoids Exchange timeout). Tag Exchange emails in smaller batches (~100 at a time) once Gmail pipeline validated. First production run: Gmail-only, no Exchange extraction.
- **2026-03-31**: Exchange AppleScript timeout RESOLVED — `--start-date`/`--end-date`/`--limit` added to all three extraction functions. Exchange uses AppleScript early-exit (`if msgDate < startDate then exit repeat`) since Mail.app returns newest-first. Both accounts tested clean: 188 msgs → 61 threads, 0 errors. Ready for production run (drop `--dry-run`). Goal: set `ANTHROPIC_API_KEY` so Haiku summarizer runs instead of Ollama fallback.
- **2026-04-01**: Email Thread Ingester FIRST PRODUCTION RUN — 156 extracted, 53 threads written, 0 errors. Summarizer: Ollama qwen2.5:7b (ANTHROPIC_API_KEY not set). Output: Vault/Notes/Email/Job Search/{TCGplayer,DraftKings,Nebius,General}, Finance, Work, General. All _Index.md files created. Daily note 2026-04-01-DLY.md updated with ## Email Activity. Flags: --start-date 2026-03-01 --limit 200.
- **2026-04-01**: Email ingester output moved to `Vault/Notes/Email/` (was `Vault/Email/`). Config change: `config.EMAIL_DIR = VAULT_ROOT / "Notes" / "Email"`. All downstream paths auto-update. Added existing-thread vault_path check in `_process_thread()` — threads land in same directory on updates.
- **2026-04-01**: Daily Vault Activity Tracker BUILT (`System/Scripts/daily_vault_activity.py`). Three phases: SCAN (mtime-based, Plaud date backdating) → POST-PROCESS (glossary extraction + central merge, LLM tag enrichment, action item extraction) → INJECT (`## Vault Activity` section in DLY files). Dual-LLM: Haiku API → Ollama qwen2.5:7b. Wired into overnight_processor.py and morning_workflow.py. CLI: `--dry-run --days N --no-tags --no-tasks`. Bug found+fixed: `TypeError` from LLM returning ints in tasks list.
- **2026-04-01**: ANTHROPIC_API_KEY added to crontab (top-level var), .bash_profile (already existed), ~/theVault/.env (new), ~/theVault/ResumeEngine/.env (new). All cron jobs and scripts now have access. Tonight's 11 PM overnight run should use Haiku instead of Ollama fallback.
- **2026-04-03**: morning_workflow.py ANTHROPIC_API_KEY fix — added `_load_dotenv()` at module top; loads ~/theVault/.env into os.environ before any subprocess spawns. Uses `if not os.environ.get(key)` (not setdefault) to handle cron empty-string env vars. Fixes "No LLM service responded" errors in clean_md_processor + daily_vault_activity.
- **2026-04-03**: clean_md_processor.py `--reprocess` flag added — reads from Processed/Plaud/ instead of Inbox, sets force=True to overwrite -Full.md output, skips moving source files. Filtered to sessions with existing -Full.md directly in Vault/Notes/ (no subdirs). Allows re-summarization without manually moving originals back to inbox.
- **2026-04-04**: Plaud transcript enhancement — `format_srt_as_markdown()` now accepts `session_date` param, produces absolute datetime stamps (e.g., `2026-04-01 00:23 → 01:04`). `_extract_session_date()` derives YYYY-MM-DD from filename. Transcript appended as collapsible `<details>` section (starts collapsed). Quality gate: MIN_TRANSCRIPT_SEGMENTS=5 filters noise. RAG analysis: transcripts already indexed by current chunker (no `<details>` filtering); ~2% chunk growth, good ROI for temporal/speaker queries.
- **2026-04-04**: Plaud `--repair` mode added — `repair_missing_transcripts()` scans `Vault/Notes/*-Full.md`, finds missing transcript sections, matches SRT from `Processed/Plaud/`, appends with absolute timestamps. Idempotent. Wired into `overnight_processor.py` as nightly auto-repair. 4 existing files repaired immediately; all 5 Full.md now have transcripts. `overnight_processor.py` also got `sys.path` fix for `System/Scripts/` imports.
- **2026-04-04**: Repair expanded to recursive `Vault/**/*-Full.md` scan (excludes System/, Templates/, Daily/). Dry run: 458 files scanned, 80 would get transcripts appended (up from 5 with flat scan). Covers all files relocated to subdirectories during post-ingest organization.
- **2026-04-04**: classify_content.py `--apply` readiness verified by Sonnet. 98 rows, 94 will move, 4 REVIEW with empty Final skipped. All source files exist, special chars (commas, &, #) safe. ML learning loop confirmed: corrections → classification.db overrides → future Haiku prompt injection.
- **2026-04-10**: classify_content.py NAS check made hostname-aware (laptop fix). Uses `scutil --get ComputerName` — on non-Mac-Mini, validates `VAULT_ROOT.is_dir()` instead of `NAS_PATH.exists()`. Same pattern as check_nas.sh. No impact on Mac Mini behavior.
- **2026-04-10**: Laptop migration (MacBook Air lap3071) COMPLETE. Git pull (326 commits), Vault symlink → NeroSpicy/Vault, 23 memory files installed, API key set, Inbox/Processed local stubs, LAPTOP_SETUP_GUIDE.md rewritten, E2E validation 12/12 passing. All memory files updated.
- **2026-04-04**: Stale task cleanup APPLIED (2 passes) — 576 tasks across 76 files converted from `- [ ] text` → `-- text`. Rule: DLY files use filename date; non-DLY use MM-DD filename prefix as date (e.g., `03-10 Meeting-Full.md` → 2026-03-10); fall back to mtime. Do NOT use inline 📅 date (system assigns +3wk default, misleading). Cutoff: >10 days old (before 2026-03-25). Excluded: _archive/, System/, Templates/, .trash/, Generic_Notes/.
- **2026-04-04**: Bidirectional Reminders sync — Phase 1 PROPOSED (not built). `sync_completions_from_reminders()` in task_reminders_sync.py is a stub. Plan: query completed Vault reminders → parse Source/Key from notes → match `- [ ]` line in source file by recomputing key → flip to `- [x] ✅ date`. Phase 2 (new Reminders → Obsidian) deferred. PyRemindKit confirmed available in venv.
- **2026-04-04**: Full bidirectional Reminders↔Obsidian sync COMPLETE + PRODUCTION TESTED (condescending-mccarthy). Step 7.5: Reminders done → Obsidian `- [x] ✅ date`. Step 7.6: new Reminders tasks (no Key) → today's DLY `## From Reminders`. Step 7.7: Obsidian `- [x]` → DELETE reminder (Obsidian is source of truth). All run even on early-return path. Tested: 14 completions pulled, 3 new tasks imported, 14 reminders deleted. Runs 4x daily via cron.
- **2026-04-09**: evening_workflow.py Step 3 fix APPLIED — _step_highlight_tomorrow() now creates Evening_Review_{date}.md with template if missing (instead of failing). Fixed + verified Apr 4-8 workflow runs: all 4 steps complete, 0 total errors per date. Daily dashboards generated for backfill (missing prerequisite for Step 1).
- **2026-04-09**: Overnight processor April 8 discrepancy RESOLVED — concurrent runs at 07:53:25 caused race condition on file write (duplicate log entries, duplicate file loads). April 8 initially showed task extraction success in logs but file retained old error. Clean re-run at 07:57 successfully extracted 5 tasks + summary. Root cause: backgrounded processes from earlier manual runs + duplicate cron execution (both 11 PM daily and 11 AM daily cron jobs were active). April 4, 6, 8 now all have correct task extractions. Prevent future issue: avoid concurrent runs, monitor for duplicate log entries.
- **2026-04-09**: Evening workflow April 4-8 PRODUCTION RUN COMPLETE — All 5 dates processed successfully: 0 total errors. 4 steps executed per date (dashboard generation, task summaries, Evening_Review creation, job queue config). Evening_Review files created for Apr 4-8 at 07:59. Daily dashboards linked. Overnight jobs disabled by default (3 available per date). System ready for next scheduled 11 PM overnight processor run. All memory files updated.
- **2026-04-05**: Laptop migration prep COMPLETE (Opus CLI). User memory (23 files) synced to git-tracked `.claude/user-memory/`. `check_nas.sh` made hostname-aware (skips NAS on laptop, validates Vault symlink). `sync_memory_to_repo.sh` created + wired into PostToolUse hook. Migration plan at `.agents/LAPTOP_MIGRATION_PLAN.md` — 11 steps for Desktop Claude Code on laptop to execute.
=======
## Next Priority: Gemma 4 Integration

Planning complete (Session 0, 9 docs at `Vault/Sessions/gemma4-integration/`). Build plan: 6 sessions.

| Session | Model | Scope | Status |
|---------|-------|-------|--------|
| 1. Infrastructure | Sonnet | Ollama upgrade 0.12.9→0.20.4+, pull E4B, memory opts, Tailscale | **COMPLETE (2026-04-14)** |
| 2. Core Server | Sonnet | config.py, server.py, _strip_thinking() | **COMPLETE (2026-04-14)** |
| 3. Route Whitelist | Haiku | query.py, fast.py, deep.py, models metadata | **COMPLETE (2026-04-14)** |
| 4. Batch Scripts | Haiku | 5 scripts with hardcoded model names | **COMPLETE (2026-04-14)** |
| 5. UI + Cosmetic | Haiku | Chat.tsx, Settings.tsx, health.py, chat_cli.py | **COMPLETE (2026-04-14)** |
| 6. Validation | Opus | Full smoke test, quality comparison | **COMPLETE (2026-04-14)** |

**Dependency graph:** S1 → S2 → S3 → S5 → S6, S1 → S4 → S6

## Decisions Made (Recent)

- **2026-04-13**: All 7 worktrees pruned (beautiful-maxwell, condescending-mccarthy, keen-kapitsa, naughty-shaw, silly-gauss, silly-varahamihira, trusting-moore). All `claude/*` branches deleted. Clean slate.
- **2026-04-13**: RAG index rebuild COMPLETE — 61,903 chunks, 100% coverage. EMBED_CTX=512 is the key config. See `project_rag_index_rebuild_2026_04_13.md`.
- **2026-04-12**: Gemma 4 Session 0 planning COMPLETE — GO verdict. E4B for all 3 generation roles. Build plan at `Vault/Sessions/gemma4-integration/build-plan.md`.
>>>>>>> 858d9fb8f826d13fb70f8b7ce184173645b3d76b

## Handoffs

### Gemma 4 Integration (Sessions 1-6: COMPLETE)
- **Session 1 DONE** — Sonnet Desktop 2026-04-14. Ollama upgrade 0.12.9→0.20.7, E4B pulled, memory opts, Tailscale. All criteria met except Tailscale needs interactive auth.
- **Session 2 DONE** — Sonnet Desktop 2026-04-14. config.py + server.py updated (gemma4:e4b defaults, FAST/DEEP/QUERY/BATCH_CTX constants, _strip_thinking() with code-fence stripping, per-endpoint num_ctx + 180s timeout). starlette downgraded 1.0.0→0.37.2.
- **Session 3 DONE** — Haiku 2026-04-14. query.py, fast.py, deep.py updated. VALID_MODELS added gemma4:e4b, imports of context constants.
- **Session 4 DONE** — Haiku Desktop 2026-04-14. All 5 batch scripts updated (overnight_processor, clean_md_processor, daily_vault_activity, email_thread_ingester, task_categorizer). FAISS canary verified.
- **Session 5 DONE** — Haiku 2026-04-14. UI + health.py + chat_cli.py updated. DEFAULT_MODEL qwen2.5:7b→gemma4:e4b across Chat.tsx, Settings.tsx.
- **Session 6 DONE** — Opus CLI 2026-04-14. Full validation passed. All 52 capabilities verified, 0 regressions.

### HAIKU_BRIEFING (Tasks 1-3: COMPLETE)
- **Task 1: RAG Incremental Fix** — DONE 2026-04-14. System/Scripts/RAG/retrieval/indexer.py: `incremental: bool = False` → `True` (line 39), added `full: bool = False` parameter (line 40), updated CLI to `--full` flag (lines 237-249). System/Scripts/batch_reindex.py: call changed to `reindex(full=True)` (line 157). All Python files parse OK.
- **Task 2: OPERATIONS-INDEX.md Update** — DONE 2026-04-14. All qwen2.5:7b→gemma4:e4b, removed llama3.1:8b/gemma3:4b references. Chunks: 41,976→61,903 (100% coverage). Added Ollama 0.20.7, pkg 0.6.1. Updated context windows (/fast=4096, /deep=16384, /api/query=32768). Added Reminders sync 4x daily schedule, daily_vault_activity notes. Added memory optimization env vars section. Updated model dropdown and health endpoint examples.
- **Task 3: QUICK-REFERENCE.md Creation** — DONE 2026-04-14. Created Vault/System/QUICK-REFERENCE.md with 11 sections: Startup & Health, Morning, Ingest & Indexing (with --full note), Evening, Reminders, Email, Plaud, File Classification, RAG QA, Server Mgmt, Troubleshooting. One-page format with model+context info footer.

- **⚠️ Known issue**: Ollama usage tokens always 0 — /api/chat uses eval_count/prompt_eval_count, not usage{}. Pre-existing, not in scope.

## Prior Work (Archived — for reference only)

All prior decisions from March-April 2026 are preserved in memory files. Key completions:
- Email Thread Ingester: BUILT + production (156→53 threads)
- Daily Vault Activity Tracker: BUILT (glossary, tags, daily injection)
- Bidirectional Reminders sync: COMPLETE
- File classification: COMPLETE (67 files moved)
- Evening/overnight workflows: STABLE
- RAG rebuild: 100% coverage
