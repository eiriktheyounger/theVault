---
name: theVault V2 Rebuild Proposal
description: Architecture vision for rebuilding theVault as a proper multi-agent system. Proposal #19 saved 2026-04-17. Phase 0 recommended next step.
type: project
---

Eric proposed rebuilding theVault on a cleaner architecture. Opus analyzed the vision and saved a structured proposal.

**Proposal location:** `Vault/System/Proposals/19-theVault-V2-Rebuild-Plan.md`

## What V2 covers
- **Multi-model token routing** — Opus 4.6 for orchestration/checkpoints, Sonnet for heavy generation, Haiku/E4B for mechanical tasks. Model routing is explicit and cost-optimized.
- **Offline toggle + deferred queue** — System continues to accept work (notes, tasks, captures) when internet or NAS is unavailable. Queue flushes when connectivity restores.
- **Opus checkpoint protocol** — Major decisions (ingest decisions, architectural calls, priority conflicts) route to Opus before execution. Prevents compounding errors in overnight runs.
- **Multi-system sync design** — Cleaner design for syncing Obsidian vault, Apple Reminders, Apple Calendar, and email threads. Current system has ad-hoc bridges; V2 treats sync as a first-class concern.
- **Scope**: carry over working components (RAG, Plaud pipeline, email ingester), rebuild orchestration layer.
- **Five key risks** documented in proposal.

## Status
This is a vision/planning doc, **not active work**. Phase 0 (scope validation + risk review) is the recommended first step before any coding.

**Note:** Eric mentioned "Opus 4.7" during the session — corrected to Opus 4.6 (current top model as of 2026-04-17).

**Why:** If Eric revisits this, the proposal has already been written — no need to re-analyze the architecture. Refer him to proposal #19.

**How to apply:** When Eric brings up theVault V2 or system rebuild, point to proposal #19 and ask whether he wants to start Phase 0. Don't begin any rebuild work without explicit go-ahead.
