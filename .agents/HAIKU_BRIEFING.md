# Haiku Session Briefing — RAG Incremental Fix + Ops Docs

**Date:** 2026-04-14
**Prepared by:** Opus (orchestrator)
**Your role:** Three mechanical tasks. Do them in order.

---

## Task 1: Fix RAG Incremental Indexing Default

### Problem

`reindex()` in `System/Scripts/RAG/retrieval/indexer.py` defaults to `incremental=False`, causing full rewrites when users just want to update new/changed files.

### Changes Needed

**File: `System/Scripts/RAG/retrieval/indexer.py`**
- Line 39: Change `incremental: bool = False` → `incremental: bool = True`
- Add a `full: bool = False` parameter that overrides incremental when explicitly requested
- If `full=True`, force `incremental=False` behavior

**File: `System/Scripts/RAG/routes/ingest.py`**
- Find where `reindex()` is called — ensure it passes `incremental=True` (should now be default)
- Add a query parameter or body field `full_rebuild: bool = False` that passes through

**File: `System/Scripts/batch_reindex.py`**
- This script should do a FULL rebuild (it's the explicit "rebuild everything" tool)
- Update its call to `reindex(incremental=False)` or `reindex(full=True)` to be explicit

**File: `System/Scripts/RAG/retrieval/indexer.py` (CLI)**
- Find the `if __name__ == "__main__"` block at the bottom
- Add `--full` flag alongside `--incremental`
- `--incremental` should remain for backward compat but is now the default
- `--full` forces full rebuild

### Verify

- `python System/Scripts/RAG/retrieval/indexer.py` → incremental (default)
- `python System/Scripts/RAG/retrieval/indexer.py --full` → full rebuild
- `python System/Scripts/RAG/retrieval/indexer.py --incremental` → incremental (explicit, same as default)
- All Python files parse OK after changes

### Constraints

- Do NOT run the actual reindex — just fix the code
- Do NOT touch the FAISS index file
- Keep changes minimal — no refactoring

---

## Task 2: Update OPERATIONS-INDEX.md

**File:** `Vault/System/OPERATIONS-INDEX.md`

The current doc is significantly out of date. Update these sections:

### Model References (throughout)
- Replace all `qwen2.5:7b` references → `gemma4:e4b`
- Replace all `llama3.1:8b` references → remove (no longer installed)
- Replace all `gemma3:4b` references → remove (no longer installed)
- Update model dropdown section: Fast=gemma4:e4b, Deep=gemma4:e4b, Claude=API fallback
- Update `/health/ollama` example: models_available should show `["gemma4:e4b", "nomic-embed-text"]`

### Chunk/Vector Counts
- Replace `41,976` → `61,903`
- Update any references to coverage percentages → `100%`

### Ollama Version
- Add note: Ollama 0.20.7, ollama Python pkg 0.6.1

### Service Management
- Add memory optimization env vars (OLLAMA_FLASH_ATTENTION=1, etc.)
- Update `ollama pull` example to use `gemma4:e4b`

### Daily Operations — Ingest Workflow
- Add note that incremental indexing is now default
- Add `--full` flag reference for full rebuilds

### Performance Tuning
- Update FAISS chunk count
- Update context windows: /fast=4096, /deep=16384, /api/query=32768
- Note: `_strip_thinking()` handles Gemma 4 code fences

### Evening/Overnight
- Update model references in overnight_processor description
- Add Reminders sync (runs 4x daily: midnight, 6am, noon, 6pm)
- Add daily_vault_activity.py reference

---

## Task 3: Create QUICK-REFERENCE.md

**File:** `Vault/System/QUICK-REFERENCE.md`

A one-page cheat sheet of the basic/base commands for daily operations. NOT all options — just the command you'd run for the common case. Include a brief one-line description for each.

### Format

```markdown
# theVault Quick Reference

## Startup & Health
[commands]

## Morning Process
[commands]

## Ingest & Indexing
[commands]

## Evening & Overnight
[commands]

## Reminders Sync
[commands]

## Email Ingestion
[commands]

## Plaud Processing
[commands]

## File Classification
[commands]

## RAG Quality Check
[commands]

## Service Management
[commands]

## Troubleshooting
[commands]
```

### Commands to Include (base calls only)

All commands assume `cd ~/theVault && source .venv/bin/activate` first.

- NAS check: `bash System/Scripts/check_nas.sh`
- Start server: `python3 -m uvicorn System.Scripts.RAG.llm.server:app --host 0.0.0.0 --port 5055`
- Morning workflow: `python3 System/Scripts/Workflows/morning_workflow.py`
- Evening workflow: `python3 System/Scripts/Workflows/evening_workflow.py`
- Overnight processor: `python3 System/Scripts/overnight_processor.py`
- Incremental reindex: `python3 System/Scripts/RAG/retrieval/indexer.py`
- Full reindex: `python3 System/Scripts/RAG/retrieval/indexer.py --full`
- Plaud processing: `python3 System/Scripts/clean_md_processor.py`
- Plaud dry-run: `python3 System/Scripts/clean_md_processor.py --dry-run`
- Email ingestion: `python3 -m System.Scripts.email_thread_ingester --start-date YYYY-MM-DD`
- Email dry-run: `python3 -m System.Scripts.email_thread_ingester --dry-run`
- File classify scan: `python3 System/Scripts/Workflows/classify_content.py --scan`
- File classify apply: `python3 System/Scripts/Workflows/classify_content.py --apply`
- Vault activity: `python3 System/Scripts/daily_vault_activity.py --dry-run --days 1`
- Reminders sync: `python3 System/Scripts/task_reminders_sync.py`
- RAG Q/A check: `python3 System/Scripts/rag_qa_agent.py`
- Service start all: `python3 System/Scripts/Services/start_all.py`
- Service stop all: `python3 System/Scripts/Services/stop_all.py`
- Ollama status: `ollama ps`
- Health check: `curl -s http://localhost:5055/healthz | jq .`

### Constraints

- Keep it to ONE page — no explanations beyond one-line descriptions
- Use consistent formatting
- Include the `cd ~/theVault && source .venv/bin/activate` prerequisite at the top

---

## When Done

Update `.agents/SHARED_CONTEXT.md` after all three tasks complete.

## Context Files

- SHARED_CONTEXT: `.agents/SHARED_CONTEXT.md`
- Current OPERATIONS-INDEX: `Vault/System/OPERATIONS-INDEX.md`
- indexer.py: `System/Scripts/RAG/retrieval/indexer.py`
- ingest.py: `System/Scripts/RAG/routes/ingest.py`
- batch_reindex.py: `System/Scripts/batch_reindex.py`
