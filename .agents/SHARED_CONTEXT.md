# Shared Context — Cross-Session Sync

_All Claude sessions (Desktop Opus/Sonnet/Haiku + CLI) should read this at start and append before ending._

## Active Work

| Session | Working On | Files Touched | Updated |
|---------|-----------|---------------|---------|
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
