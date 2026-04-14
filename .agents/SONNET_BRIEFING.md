# Sonnet Session Briefing — Gemma 4 Session 1: Infrastructure

**Date:** 2026-04-14
**Prepared by:** Opus (orchestrator)
**Your role:** Execute Session 1 of the Gemma 4 integration build plan.

## What You're Doing

Upgrade Ollama and pull the Gemma 4 E4B model. This is infrastructure-only — do NOT modify any Python source files.

## Full Build Plan

Read the complete Session 1 spec here:
`Vault/Sessions/gemma4-integration/build-plan.md` → Section "Session 1: Infrastructure"

## Quick Summary of Session 1 Steps

1. Record current Ollama state (`ollama list`, `ollama --version`)
2. Test existing models before upgrade (gemma3:4b, qwen2.5:7b, nomic-embed-text)
3. Upgrade Ollama from 0.12.9 to 0.20.4+
4. Configure memory optimizations (flash attention, parallel limits, keep-alive)
5. Verify existing models still work post-upgrade
6. Pull `gemma4:e4b`
7. Verify Gemma 4 E4B inference works via CLI
8. Update `ollama` Python package in venv
9. Install Tailscale on Mac Mini

## Critical Constraints

- **FAISS canary** — verify hash hasn't changed: `3275127b89e8987863324d6467035b7aca6097d4759bafa587dc130ff7ecc527` at `System/Scripts/RAG/rag_data/chunks_hnsw.bin`
- **No Python source changes** — Session 2 handles config.py/server.py
- **If existing models break after upgrade** — STOP. Do not proceed. Report to SHARED_CONTEXT.md
- **Rollback plan**: `brew install ollama@0.12.9` (or reinstall from backup)

## When Done

1. Update `.agents/SHARED_CONTEXT.md` — mark Session 1 complete, record Ollama version + model list
2. Note any surprises or blockers for Session 2

## Context Files

- Build plan: `Vault/Sessions/gemma4-integration/build-plan.md`
- Pre-flight snapshot: `Vault/Sessions/gemma4-integration/preflight-snapshot.md`
- SHARED_CONTEXT: `.agents/SHARED_CONTEXT.md`
- CLAUDE.md: `~/theVault/CLAUDE.md`
