# Vault Architecture — Memory Topic File
# Last updated: 2026-04-10

## Core Stack
- Python 3.12.5, FastAPI, SQLite + FAISS (768-dim, nomic-embed-text)
- Obsidian vault on Synology DS1621+ NAS (16TB free) — Mac Mini; Obsidian Sync copy on laptop
- Ollama for local LLM (qwen2.5:7b fast, gemma3:4b fastest, nomic-embed-text embeddings). llama3.1:8b removed 2026-04-02.
- Claude API for quality work (Haiku extraction, Sonnet coding, Opus planning)
- React/Vite UI on port 5173

## What Works
- RAG server (port 5055) — all search/chat endpoints, unified /api/query (multi-model: Ollama+Claude)
- Task pipeline — 6 modules, cron at 11 PM, syncs to macOS Reminders
- Bidirectional Reminders sync — Reminders done->Obsidian, new Reminders->DLY, Obsidian done->delete Reminder. 4x daily.
- Evening workflow — self-contained, 4 steps, no external deps. Production tested Apr 4-8.
- Overnight processor — runs task pipeline + chat summary + Plaud transcript repair. Fixed Apr 9.
- Morning workflow — loads .env for API key, runs daily vault activity + Plaud ingest
- clean_md_processor.py — Plaud inbox pipeline (built 2026-03-25, 48+ sessions processed). --reprocess mode added.
- orchestration_system_start.py — triggers Plaud + email ingest pipelines (built 2026-04-02)
- Services/ — start_all.py, stop_all.py, emergency_kill.py (built 2026-04-02)
- generate_daily_dashboard.py — aggregates open tasks + vault activity into TimeTracking/ (built 2026-04-02)
- Email Thread Ingester — 12-module package, production run 2026-04-01: 156 msgs -> 53 threads, 0 errors
- Daily Vault Activity Tracker — scan->glossary->tags->daily injection (built 2026-04-01)
- Content classifier (classify_content.py) — Haiku-powered, 98 files classified, hostname-aware NAS check
- JD Analyzer — ResumeEngine/jd_analyzer.py, Haiku parse+Sonnet generate
- CLI tools — batch_reindex, rag_healthcheck, rag_query, rag_vacuum
- daily_chat_exporter.py — exports Claude chat history

## Multi-Machine Architecture (COMPLETE 2026-04-10)
- Mac Mini M4: production, cron jobs, NAS, Ollama, FAISS, RAG server
- MacBook Air (lap3071): development, Obsidian Sync, Claude Code Desktop (Opus), script testing
- Vault symlink: `~/theVault/Vault` on both machines (Mac Mini -> NAS; laptop -> /Users/emanches/NeroSpicy/Vault)
- Inbox/Processed: NAS symlinks on Mac Mini; local stub dirs on laptop
- Sync: Git (code + memory) + Obsidian Sync (vault content)
- check_nas.sh + classify_content.py: hostname-aware (scutil --get ComputerName)
- E2E validation: 12/12 functional tests passing on laptop

## Architecture Decisions (Permanent)
- No Docker — blocks Metal/GPU on Apple Silicon
- No PostgreSQL — SQLite is sufficient for personal scale
- No ChromaDB — raw FAISS + SQLite FTS5
- NAS for storage, local SSD for compute/databases
- Symlinks connect local project to NAS/Obsidian Sync content
- One monolithic FastAPI app, not microservices

## Hardware
- Mac Mini M4 base model (budget, purchased after job loss)
- MacBook Air (lap3071) — secondary, development + capture
- Can run Claude Code Desktop + Cowork (Apple Silicon)
- Accepted: cloud APIs for quality, local models for basics/offline
