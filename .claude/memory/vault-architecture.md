# Vault Architecture — Memory Topic File

## Core Stack
- Python 3.12.5, FastAPI, SQLite + FAISS (768-dim, nomic-embed-text)
- Obsidian vault on Synology DS1621+ NAS (16TB free)
- Ollama for local LLM (qwen2.5:7b fast, llama3.1:8b deep)
- Claude API for quality work (Haiku extraction, Sonnet coding, Opus planning)
- React/Vite UI on port 5173

## What Works
- RAG server (port 5055) — all search/chat endpoints
- Task pipeline — 6 modules, cron at 10 PM, syncs to macOS Reminders
- Evening workflow — self-contained, 3 steps, no external deps
- Overnight processor — runs task pipeline + chat summary
- CLI tools — batch_reindex, rag_healthcheck, rag_query, rag_vacuum
- daily_chat_exporter.py — exports Claude chat history (434 lines, working)

## What's Broken/Missing
- Morning workflow steps 1-4 (scripts never built)
- clean_md_processor.py (core ingest — NEVER EXISTED)
- orchestration_system_start.py (API ingest trigger)
- Services/ directory (start/stop/kill scripts)
- Calendar/ directory (sync script)
- generate_daily_dashboard.py
- See: SYSTEM-AUDIT-2026-03-25.md for complete inventory

## Architecture Decisions (Permanent)
- No Docker — blocks Metal/GPU on Apple Silicon
- No PostgreSQL — SQLite is sufficient for personal scale
- No ChromaDB — raw FAISS + SQLite FTS5
- NAS for storage, local SSD for compute/databases
- Symlinks connect local project to NAS content
- One monolithic FastAPI app, not microservices

## Hardware Constraints
- Mac Mini M4 base model (budget, purchased after job loss)
- Can run Claude Code Desktop + Cowork (Apple Silicon)
- Cannot run heavy local AI workloads
- Accepted: cloud APIs for quality, local models for basics/offline
