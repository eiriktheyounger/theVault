---
name: Key file locations in theVault
description: Authoritative files and where to find them — use before searching
type: reference
---

| File | Path | Purpose |
|------|------|---------|
| RAG server entry | `System/Scripts/RAG/llm/server.py` | FastAPI app, start with uvicorn from ~/theVault root |
| Start script | `System/Scripts/start_server.sh` | Starts RAG server; accepts port arg, default 5055 |
| NAS check (Mac Mini) | `System/Scripts/check_nas.sh` | Verifies /Volumes/home/MacMiniStorage mount |
| Laptop preflight | `System/Scripts/check_vault_laptop.sh` | 7-section check: symlinks, venv, Obsidian, git, env vars |
| Morning workflow | `System/Scripts/Workflows/morning_workflow.py` | _step_organize_files disabled; _step_update_tocs EOL'd 2026-03-25 |
| Evening workflow | `System/Scripts/Workflows/evening_workflow.py` | Fully self-contained, no missing deps |
| Overnight processor | `System/Scripts/overnight_processor.py` | Fixed 2026-03-28: Captures regex (end-of-file), sys.path, docstring (10→11 PM) |
| JD Analyzer | `ResumeEngine/jd_analyzer.py` | Haiku parse+score, Sonnet generate. Single: `--jd file.txt`. Batch: `--batch` processes all in `ResumeEngine/jds/`, moves to `jds/processed/` or `jds/failed/`. |
| Reminders sync | `System/Scripts/task_reminders_sync.py` | Fixed 2026-03-28: _upsert_reminder, "Do Today!!!!" list name, check() API. Production-tested. |
| Reminders sync shortcut | `System/Scripts/sync_reminders_now.sh` | Manual trigger script; wire to Shortcuts app for keyboard shortcut |
| Plaud processor | `System/Scripts/clean_md_processor.py` | Built 2026-03-25. Inbox → Vault/Notes. Public API: `run_orchestration()` |
| FAISS indexer | `System/Scripts/RAG/retrieval/indexer.py` | Builds/updates vector index |
| Embedding repair | `System/Scripts/RAG/repair_embeddings.py` | Finds orphan chunks missing FAISS vectors, re-embeds them. --dry-run first. |
| Content classifier | `System/Scripts/Workflows/classify_content.py` | Haiku-powered file classification with learning DB. EXISTS (689 lines). Path bug fixed 2026-04-02. Hostname-aware NAS check added 2026-04-10 (works on laptop). |
| Laptop setup guide | `LAPTOP_SETUP_GUIDE.md` | MacBook Air setup: symlinks, memory sync, what works on laptop vs Mac Mini. Rewritten 2026-04-10. |
| Services manager | `System/Scripts/Services/` | start_all.py, stop_all.py, emergency_kill.py — manages Ollama + RAG server (built 2026-04-02) |
| Orchestration entry | `System/Scripts/orchestration_system_start.py` | Triggers Plaud + email ingest pipelines; wired into `/ingest/start` API (built 2026-04-02) |
| Daily dashboard | `System/Scripts/generate_daily_dashboard.py` | Aggregates open tasks + vault activity into TimeTracking/ (built 2026-04-02) |
| Query endpoint | `System/Scripts/RAG/routes/query.py` | Unified `/api/query` endpoint; replaces /fast and /deep for new code; multi-model (Ollama+Claude API) |
| Claude API client | `System/Scripts/RAG/llm/claude_client.py` | Async Anthropic API client for /api/query; loads .env with override=True |
| Classification DB | `System/Scripts/RAG/rag_data/classification.db` | Separate from chunks.sqlite3. Decisions, rules, directory tree tables. |
| Classification manifest | `Vault/System/ClassificationReview.md` | Overwritten each --scan. Edit in Obsidian/VS Code, then --apply. |
| Session state sync | `System/Scripts/sync_session_state.sh` | Auto-syncs CLI memory → `.agents/SESSION_STATE.md`. Triggered by hooks + Stop. |
| Session state (shared) | `.agents/SESSION_STATE.md` | Auto-generated consolidated view for all instances. Do not edit manually. |
| Email Thread Ingester | `System/Scripts/email_thread_ingester/` | 12-module package. Exchange+Gmail via AppleScript, threading, job tracker, daily backlinks. Run: `python -m System.Scripts.email_thread_ingester --start-date YYYY-MM-DD --dry-run` |
| Vault Activity Tracker | `System/Scripts/daily_vault_activity.py` | Scan vault changes → glossary → tags → daily note injection. Run: `python System/Scripts/daily_vault_activity.py --dry-run --days 7` |
| SQLite DB | `System/Scripts/RAG/rag_data/chunks.sqlite3` | 47,496 chunks, FTS5 |
| FAISS index | `System/Scripts/RAG/rag_data/chunks_hnsw.bin` | 768-dim FAISS (IndexIDMap2/IndexFlatIP), 53,381 vectors (95.8% coverage, rebuilt 2026-03-30) |
| Glossary | `Vault/Glossary/glossary.md` | Only active glossary; backups archived |
| Operations index | `Vault/System/OPERATIONS-INDEX.md` | Production reference doc (created 2026-03-24) |
| Workflow map | `Vault/System/WORKFLOW-MAP.md` | Full workflow + script inventory with Mermaid diagrams |
| System audit | `Vault/System/SYSTEM-AUDIT-2026-03-25.md` | Complete MISSING/BROKEN/WORKING/ORPHANED audit; CLAUDE.md requires reading before modifying scripts |
| Tag spec | `Vault/System/Specifications/OutputSpec_Tags.md` | Tag generation rules |
| Archive (docs) | `Vault/_archive/system-cleanup-2026-03-24/` | 128 archived NeroSpicy-era files |
| Archive (EOL scripts) | `Vault/_archive/eol-scripts/` | EOL'd scripts; toc_generator.py.eol-2026-03-25 here |
