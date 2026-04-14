---
name: Gemma 4 Integration Planning
description: Gemma 4 E4B integration into theVault — Session 0 planning complete (9 docs), 6 build sessions planned. Memory optimizations (flash attention, dynamic num_ctx), PDF vision processing post-build.
type: project
---

## Gemma 4 Integration — Session 0 COMPLETE (2026-04-12)

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

**Build sessions:** 6 total, ~$1.16, ~3-4 hours wall-clock
- Sessions 1-2: Sonnet (infrastructure + core server)
- Sessions 3-5: Haiku (routes, batch scripts, UI)
- Session 6: Opus (validation)
- Sessions 2+4 can run in parallel

**Post-build:** PDF/PowerPoint vision processing via E4B (Sonnet, 1-2 hrs, after Sessions 1-6)

**Why:** E4B benchmarks higher than both current models. 128K context (up from 4096 silent truncation). Native vision + audio. Apache 2.0.

**How to apply:** All build session prompts are in build-plan.md. Hand Session 1 prompt to Sonnet first. Check SHARED_CONTEXT.md before starting any session.
