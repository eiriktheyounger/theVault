# Haiku Session Briefing — Gemma 4 Session 4: Batch Scripts

**Date:** 2026-04-14
**Prepared by:** Opus (orchestrator)
**Your role:** Execute Session 4 of the Gemma 4 integration build plan (can start after Session 1 completes).

## Dependency

**Wait for Session 1 (Sonnet) to complete first.** Check `.agents/SHARED_CONTEXT.md` — Session 1 must be marked complete before you begin. If it's not done yet, report back and wait.

## What You're Doing

Mechanical find-replace of hardcoded model names in 5 batch/workflow scripts. Change `qwen2.5:7b` → `gemma4:e4b` and `gemma3:4b` → `gemma4:e4b` where they appear as model references.

## Full Build Plan

Read the complete Session 4 spec here:
`Vault/Sessions/gemma4-integration/build-plan.md` → Section "Session 4: Batch Scripts"

## Scope

The 5 scripts with hardcoded model names (verify these against the build plan):
1. `System/Scripts/clean_md_processor.py`
2. `System/Scripts/daily_vault_activity.py`
3. `System/Scripts/overnight_processor.py`
4. `System/Scripts/Workflows/evening_workflow.py`
5. `System/Scripts/Workflows/morning_workflow.py`

For each file:
- Search for `qwen2.5:7b` and `gemma3:4b` references
- Replace with `gemma4:e4b` (or use the config constant if Session 2 has defined one)
- Do NOT change any logic, structure, or formatting — model name swaps only

## Critical Constraints

- **FAISS canary** — verify hash: `3275127b89e8987863324d6467035b7aca6097d4759bafa587dc130ff7ecc527`
- **Mechanical changes only** — no refactoring, no logic changes
- **Check SHARED_CONTEXT before starting** — make sure no other session is editing these files
- **If Session 2 has created a config constant for model names**, use that instead of hardcoding `gemma4:e4b`

## When Done

1. Update `.agents/SHARED_CONTEXT.md` — mark Session 4 complete, list all files changed
2. Note any files that didn't match the expected pattern

## Context Files

- Build plan: `Vault/Sessions/gemma4-integration/build-plan.md`
- SHARED_CONTEXT: `.agents/SHARED_CONTEXT.md`
- CLAUDE.md: `~/theVault/CLAUDE.md`
