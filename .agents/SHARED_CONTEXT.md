# Shared Context — Cross-Session Sync

_All Claude sessions (Desktop Opus/Sonnet/Haiku + CLI) should read this at start and append before ending._

## Active Work

| Session | Working On | Files Touched | Updated |
|---------|-----------|---------------|---------|
| CLI Opus | **Orchestrator** — Cleaned all 7 stale worktrees + branches. Reset SHARED_CONTEXT. Prepped Sonnet + Haiku session briefings. | .agents/SHARED_CONTEXT.md, memory files | 2026-04-13 |
| **Sonnet Desktop** | **Gemma 4 Sessions 1+2 COMPLETE** — Ollama 0.20.7, E4B serving, config.py+server.py updated, _strip_thinking()+code-fence stripping, per-endpoint num_ctx+timeout, starlette pinned 0.37.2. /fast+/deep verified no think tags. | System/Scripts/RAG/config.py, llm/server.py | **2026-04-14** |
| CLI Haiku | **Available** — Ready for Gemma 4 Session 4 (batch scripts). | — | — |

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
| 3. Route Whitelist | Haiku | query.py, fast.py, deep.py, models metadata | Blocked on S2 |
| 4. Batch Scripts | Haiku | 5 scripts with hardcoded model names | **COMPLETE (2026-04-14)** |
| 5. UI + Cosmetic | Haiku | Chat.tsx, Settings.tsx, health.py, chat_cli.py | Blocked on S3 |
| 6. Validation | Opus | Full smoke test, quality comparison | Blocked on S3+S4+S5 |

**Dependency graph:** S1 → S2 → S3 → S5 → S6, S1 → S4 → S6

## Decisions Made (Recent)

- **2026-04-13**: All 7 worktrees pruned (beautiful-maxwell, condescending-mccarthy, keen-kapitsa, naughty-shaw, silly-gauss, silly-varahamihira, trusting-moore). All `claude/*` branches deleted. Clean slate.
- **2026-04-13**: RAG index rebuild COMPLETE — 61,903 chunks, 100% coverage. EMBED_CTX=512 is the key config. See `project_rag_index_rebuild_2026_04_13.md`.
- **2026-04-12**: Gemma 4 Session 0 planning COMPLETE — GO verdict. E4B for all 3 generation roles. Build plan at `Vault/Sessions/gemma4-integration/build-plan.md`.

## Handoffs

- **Gemma 4 Session 1 DONE** — Sonnet Desktop completed 2026-04-14. All success criteria met except Tailscale needs interactive auth (Eric to run `tailscale up` in terminal).
- **Gemma 4 Session 2 DONE** — Sonnet Desktop completed 2026-04-14. config.py + server.py updated (gemma4:e4b defaults, FAST/DEEP/QUERY/BATCH_CTX constants, _strip_thinking() with code-fence stripping, per-endpoint num_ctx + 180s timeout for /deep). starlette downgraded 1.0.0→0.37.2 (ollama pkg upgrade side-effect). /fast + /deep verified.
- **⚠️ Known issue**: Ollama usage tokens always 0 — /api/chat uses eval_count/prompt_eval_count, not usage{}. Pre-existing, not Session 2 scope.
- **Gemma 4 Session 3 → Haiku**: Read build-plan.md Section "Session 3: Route Whitelist". Update query.py VALID_MODELS + default model, fast.py num_ctx, deep.py Ollama URL, /models metadata. Prerequisite: S1+S2 complete ✅✅.
- **Gemma 4 Session 4 DONE** — Haiku Desktop completed 2026-04-14. Updated 5 batch scripts (overnight_processor, clean_md_processor, daily_vault_activity, email_thread_ingester/summarizer, task_categorizer). All imports OK, FAISS canary verified.

## Prior Work (Archived — for reference only)

All prior decisions from March-April 2026 are preserved in memory files. Key completions:
- Email Thread Ingester: BUILT + production (156→53 threads)
- Daily Vault Activity Tracker: BUILT (glossary, tags, daily injection)
- Bidirectional Reminders sync: COMPLETE
- File classification: COMPLETE (67 files moved)
- Evening/overnight workflows: STABLE
- RAG rebuild: 100% coverage
