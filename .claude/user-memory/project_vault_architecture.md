---
name: theVault system architecture
description: Ports, services, key paths, and technical stack for theVault RAG/knowledge system
type: project
---

**Active project directory:** `~/theVault` (migrated from `~/NeroSpicy` on ~2026-03-17)

**Services:**
- RAG server: FastAPI, port 5055, started via `bash System/Scripts/start_server.sh`
- LLM server: FastAPI, port 5111 (Ollama proxy) — separate service per CLAUDE.md
- Ollama: port 11434 (v0.20.7), models: `gemma4:e4b` (FAST+DEEP, 9.6GB), `nomic-embed-text` (embeddings, 274MB). Legacy still installed: `qwen2.5:7b`, `gemma3:4b` (can be removed). Upgraded 2026-04-14.
- Services manager: `System/Scripts/Services/` — `start_all.py`, `stop_all.py`, `emergency_kill.py` (built 2026-04-02)

**Database:**
- SQLite FTS5: `System/Scripts/RAG/rag_data/chunks.sqlite3`
- FAISS vector index: `System/Scripts/RAG/rag_data/chunks_hnsw.bin` (768-dim, IndexIDMap2/IndexFlatIP)
- Despite the filename `chunks_hnsw.bin`, backend is FAISS — do NOT import hnswlib
- Query log: `System/Scripts/RAG/rag_data/query_log.sqlite3` (cost tracking, added 2026-04-02)

**Paths:**
- Vault: `~/theVault/Vault` → symlink to `/Volumes/home/MacMiniStorage/Vault`
- Inbox: `~/theVault/Inbox` → NAS symlink
- Processed: `~/theVault/Processed` → NAS symlink
- RAG routes: `System/Scripts/RAG/routes/` (chat.py, fast.py, query.py [added 2026-04-02])
- Workflows: `System/Scripts/Workflows/`
- Daily notes: `Vault/Daily/YYYY/MM/YYYY-MM-DD-DLY.md`

**Chunk/vector counts (as of 2026-04-13):** 61,903 chunks in SQLite / 61,903 vectors in FAISS (100% coverage). EMBED_CTX=512, PROGRESS_EVERY=16, timeout=180s.

**Multi-machine setup (COMPLETE 2026-04-10):**
- Mac Mini M4: production server, cron jobs, NAS-connected, FAISS index, Ollama
- MacBook Air (lap3071): development, Obsidian management, Claude Code Desktop (Opus)
- Sync: Git (code + memory) + Obsidian Sync (vault content). No overlap.
- User memory: `~/.claude/projects/-Users-emanches-theVault/memory/` (23 files) synced to git via `theVault/.claude/user-memory/` + `sync_memory_to_repo.sh`
- `check_nas.sh` is hostname-aware: skips NAS check on non-Mac-Mini machines, validates Vault symlink instead
- `classify_content.py` also made hostname-aware (2026-04-10): same `scutil --get ComputerName` pattern
- Laptop Vault symlink: `~/theVault/Vault → /Users/emanches/NeroSpicy/Vault` (Obsidian Sync delivers here)
- Laptop Inbox/Processed: local stub directories (not NAS symlinks) — `mkdir -p Inbox/Plaud/MarkdownOnly Processed/Plaud`
- API key: set in `~/.zshrc` + `~/theVault/.env`
- E2E validation: 12/12 functional tests passing (2026-04-10)
- Setup guide: `LAPTOP_SETUP_GUIDE.md` (rewritten 2026-04-10)
- Migration plan (reference): `.agents/LAPTOP_MIGRATION_PLAN.md`

**Why:** Local-first AI knowledge management; NAS-backed vault for persistence and Obsidian sync.

**How to apply:** Always start server from `~/theVault` root with full package path. Never use hnswlib. Use absolute paths for NAS traversal. On laptop, run `check_nas.sh` first — it auto-detects machine type.
