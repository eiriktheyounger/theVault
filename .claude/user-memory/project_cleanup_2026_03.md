---
name: Vault documentation cleanup March 2026
description: What was archived, what's canonical, and known gaps discovered during the March 2026 cleanup — updated as gaps are closed
type: project
---

**Cleanup executed:** 2026-03-24/25. Archive location: `Vault/_archive/system-cleanup-2026-03-24/`

**128 files archived** — all NeroSpicy-era docs, outdated specs, old proposals (01–14), glossary backups, UI build docs, ChatGPT conversation exports, training docs, tag_registry.yaml (dead artifact — tags live in SQLite/Obsidian frontmatter, zero code references found).

**Canonical documentation after cleanup:**
- `Vault/System/OPERATIONS-INDEX.md` — all production services, morning/evening workflows, quick-reference commands
- `Vault/System/WORKFLOW-MAP.md` — full workflow inventory, script inventory (64 Python + 3 shell), cross-reference table, Mermaid diagrams
- `Vault/System/SYSTEM-AUDIT-2026-03-25.md` — complete script audit: MISSING/BROKEN/WORKING/ORPHANED with per-script analysis
- `Vault/System/Specifications/OutputSpec_Tags.md` — tag generation rules (fixed "NeroSpicy" → "theVault" on line 7)
- `Vault/Glossary/glossary.md` — the only active glossary file

**Gaps status as of 2026-03-25:**
- `System/Scripts/clean_md_processor.py` — ✅ BUILT 2026-03-25. Processes Plaud inbox → Vault/Notes Full.md files. See ref_key_files.md.
- `System/Scripts/Workflows/toc_generator.py` — ✅ EOL'd 2026-03-25. Archived to `Vault/_archive/eol-scripts/toc_generator.py.eol-2026-03-25`. Original kept until 2026-04-25. `_step_update_tocs` in morning_workflow.py commented out.
- `System/Scripts/Services/start_all.py` — ❌ STILL MISSING. Entire `Services/` directory absent. Blocks morning_workflow Step 1 and all `/services/` API endpoints.
- `System/Scripts/Calendar/sync_calendar.py` — ❌ STILL MISSING. Blocks morning_workflow Step 2.
- `System/Scripts/generate_daily_dashboard.py` — ❌ STILL MISSING. Blocks morning_workflow Step 3.
- `orchestration_system_start.py` — ❌ STILL MISSING. Imported by `routes/ingest.py:147`; crashes `/ingest/start` background task with ImportError at runtime.
- `morning_workflow.py` line 611: `_step_organize_files` is **disabled** (commented out)
- `System/Scripts/Plaud/` directory exists but is empty

**Why:** 166+ vault docs still referenced NeroSpicy paths after the March 17 migration. Cleanup establishes theVault as the single source of truth.

**How to apply:** Start from OPERATIONS-INDEX.md and WORKFLOW-MAP.md for system docs. Check SYSTEM-AUDIT-2026-03-25.md before modifying any script (CLAUDE.md enforces this). Don't reference archived NeroSpicy docs as current.
