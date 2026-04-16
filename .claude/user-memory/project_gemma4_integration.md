---
name: Gemma 4 Integration
description: Gemma 4 E4B integration COMPLETE 2026-04-14 — all 6 sessions done, 0 regressions, quality >= qwen2.5:7b. Post-build report at Vault/Sessions/gemma4-integration/post-build-report.md.
type: project
---

## Gemma 4 Integration — ALL 6 SESSIONS COMPLETE (2026-04-14)

**Verdict: GO** — gemma4:e4b replaces both gemma3:4b (FAST) and qwen2.5:7b (DEEP/INGEST). Single model avoids swap thrashing on 16GB.

**Planning artifacts:** `Vault/Sessions/gemma4-integration/` (9 documents)
- preflight-snapshot.md, preflight-pip-freeze.txt, capability-inventory-pre.md
- gemma4-research.md, code-analysis.md, mobile-integration-eval.md
- build-plan.md, SESSION-0-SUMMARY.md, Post-Gemma4-Integration.md

**Key decisions:**
- E4B for all 3 generation roles (FAST, DEEP, INGEST). E2B too weak, 26B A4B doesn't fit 16GB.
- Ollama 0.12.9 → 0.20.4+ (major jump, regression-tested in Session 1)
- Thinking tag stripping (`_strip_thinking()`) server-side — Ollama bug makes `think=false` unreliable
- FAISS canary hash enforced every session: `3275127b89e8...7ecc527`
- Mobile: Tailscale tunnel (15 min, full 52/52 capability access, zero code changes)

**Memory optimizations:**
- `OLLAMA_FLASH_ATTENTION=1` (2-4x KV cache reduction on M4)
- Dynamic num_ctx: /fast=4096, /deep=16384, /api/query=32768, batch=8192
- `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_LOADED_MODELS=2`

**Build sessions:** 6/6 COMPLETE (2026-04-14)
- S1 (Sonnet): Ollama 0.20.7, E4B pulled, memory opts, Tailscale installed
- S2 (Sonnet): config.py, server.py, _strip_thinking(), per-endpoint num_ctx
- S3 (Haiku): routes updated (query, fast, deep)
- S4 (Haiku): 5 batch scripts model names swapped
- S5 (Haiku): UI + health + chat_cli updated
- S6 (Opus): Full validation PASS — 52/52 capabilities, 0 regressions, quality >= qwen

**Post-build report:** `Vault/Sessions/gemma4-integration/post-build-report.md`

**Remaining:** PDF/PowerPoint vision processing via E4B (Sonnet, 1-2 hrs, deferred)

**Why:** E4B benchmarks higher than both current models. 128K context (up from 4096 silent truncation). Native vision + audio. Apache 2.0.

**How to apply:** All build session prompts are in build-plan.md. Hand Session 1 prompt to Sonnet first. Check SHARED_CONTEXT.md before starting any session.
